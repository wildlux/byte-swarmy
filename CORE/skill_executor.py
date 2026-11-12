"""CORE/skill_executor.py — Generazione DIRETTA con skill (LLM SENZA tool).

Per modelli che non supportano il tool-calling: il loop ReAct del Worker
(write_file/lint_code come azioni del modello) e' sostituito da un ciclo
interamente lato HOST:

    prompt(skill + task) → risposta del modello → estrazione del blocco
    di codice → scrittura su disco → py_compile → VERIFICA RUNTIME
    (esecuzione reale: exit 0, niente traceback, marker NAME=value
    attesi presenti nel stdout) → se qualcosa fallisce:
    build_correction_prompt() → retry (fino a max_retries).

La verifica runtime (Fase 3) e' cio' che rende efficace il correction
loop sui fallimenti SEMANTICI: py_compile e' cieco sia sui crash a
runtime (NameError) sia sull'output sbagliato (SOMMA=55 invece di
5000050000) — l'esecuzione vede entrambi.

La skill qui vale DOPPIO: senza tool il modello non puo' "verificare",
quindi la ricetta (passi + template + DONE WHEN) e' l'unica bussola che
ha, e la verifica meccanica la fa il codice host (deterministica).

Usage CLI (test veloce, modello configurato in CONFIG/config.toml):
    python -m CORE.skill_executor "fammi un software di sommare 2 numeri" \
        --project project/PR_TEST_progetto --model worker_coder
"""

from __future__ import annotations

import logging
import os
import py_compile
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from CORE.code_map import check_code_names, render_map_section, symbols
from CORE.correction import build_correction_prompt
from CORE.skills import find_skill, format_skill_block

DEFAULT_FILENAME = "main.py"
MAX_CODE_CHARS = 20_000

# Runtime: timeout di esecuzione (GUI: il timeout e' successo) e cap stdout.
RUNTIME_TIMEOUT_S = 15
MAX_STDOUT_CHARS = 400

# Marker NAME=value nel testo del task: solo nomi MAIUSCOLI di >= 2 char
# (LEN=3, PALINDROMO=True, SOMMA=5000050000, TROVATO=12345). Esclude per
# design input tipo 'n=50' (minuscolo) e valori dentro liste/virgolette.
_MARKER_RE = re.compile(r"\b([A-Z][A-Z0-9_]{1,24})\s*=\s*([^\s,.;:)\]}]+)")
_MAX_MARKERS = 8

# Codice GUI: se contiene questi frammenti, il timeout del run e' il
# segno che il programma e' entrato nel loop eventi senza crash.
_GUI_HINTS = ("QApplication", "QGuiApplication", "app.exec", "mainloop", "Tk(")

# System prompt per la modalità diretta: vincolo SECCO sull'output +
# regole concrete contro i fallimenti semantici osservati nella suite
# (T3 elementi quottati, T4 punteggiatura, T5 match esatto, T9 range
# ridotto). Restano brevi e imperative: un 3B affoga nei discorsi lunghi.
SYSTEM_DIRECT = (
    "You are a code generator. Your response MUST START on the FIRST "
    "line with one fenced ```python code block containing the COMPLETE "
    "file content. NEVER write any text before or after the code block: "
    "no 'Okay', no explanations, no thinking, no notes.\n"
    "If a SKILL recipe is provided, follow it EXACTLY: fill ONLY the "
    "{{...}} placeholders and keep every other line unchanged. A "
    "{{...}} placeholder left in the code is a SYNTAX ERROR — replace "
    "EVERY one of them with real code.\n"
    "Rules:\n"
    "1. Implement EVERY function, method, class or exception the task "
    "names. Omit none.\n"
    "2. Use the EXACT numbers, names and ranges from the task. Never "
    "shrink the problem (from 1 to 100000 = sum(range(1, 100001))).\n"
    "3. Quoted items (even single letters like 'a') are STRING literals, "
    "never variable names.\n"
    "4. Palindromes: strip ALL punctuation AND spaces, lowercase.\n"
    "   Word counting: strip punctuation and lowercase, then split on "
    "spaces — NEVER join the words into one string.\n"
    "5. Searching a name means SUBSTRING match (Mario matches Mario "
    "Rossi) unless the task says exact equality.\n"
    "6. print() exactly the markers the task requests (e.g. SOMMA=...).\n"
    "7. Standard library only.\n"
    "8. If the PROJECT MAP shows a class, use an INSTANCE "
    "(obj = Class(); obj.method()) — never call methods directly on "
    "the class itself."
)

_CODE_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S | re.I)


def extract_code(text: str) -> str:
    """Estrae il codice dalla risposta del modello.

    Preferisce il blocco rinchiuso piu' lungo (i modelli piccoli a volte
    aggiungono frammenti di esempio); se non ci sono fence ma il testo
    sembra codice puro, lo restituisce intiero — ma PRIMA tronca tutto
    cio' che precede la prima riga davvero-Python: i modelli piu' grandi
    a volte ignorano il system prompt e aprono con prosa ("Okay, let's
    tackle this problem..."), che altrimenti brucerebbe un tentativo di
    py_compile.
    """
    raw = str(text or "")
    blocks = _CODE_FENCE_RE.findall(raw)
    if blocks:
        best = max(blocks, key=len).strip("\n")
        return best[:MAX_CODE_CHARS]
    stripped = raw.strip()
    # Senza fence: cerco la prima riga che PUO' essere codice (import /
    # from / def / class / print( / @decoratore) e scarto la prosa prima
    # di essa. Le regex sono ancorate a inizio riga con spazio dopo la
    # keyword: "definitely…" NON matcha "def ".
    lines = stripped.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^(import |from |def |class |print\(|@)", line):
            if i > 0:
                stripped = "\n".join(lines[i:])
            break
    # Deve sembrare Python (keyword note o print).
    # Niente clausole con precedenza ambigua tipo `not x is False` —
    # il confronto resta esplicito e leggibile.
    looks_like_code = bool(
        stripped
        and (re.search(r"\b(import|def|class|from)\b", stripped)
             or re.search(r"\bprint\s*\(", stripped)
             or stripped.startswith(("#", "import ", "def ", "from ",
                                     "print ")))
    )
    if looks_like_code and len(stripped) < MAX_CODE_CHARS:
        return stripped
    return ""


def verify_python(code: str) -> Optional[str]:
    """Verifica meccanica host-side: py_compile. None = OK, altrimenti errore."""
    import tempfile

    tmp = Path(tempfile.mkstemp(suffix=".py")[1])
    try:
        tmp.write_text(code, encoding="utf-8")
        py_compile.compile(str(tmp), doraise=True)
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


def extract_expected_markers(text: str) -> list[tuple[str, str]]:
    """Marker di output atteso (NAME=value) dal testo del task.

    Solo nomi MAIUSCOLI >= 2 char: cattura LEN=3, HAS=True, TROVATO=12345,
    OVERFLOW=ok, SOMMA=5000050000; esclude 'n=50' (input, minuscolo) e
    valori con punteggiatura di lista. Dedup, max _MAX_MARKERS.
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for name, value in _MARKER_RE.findall(str(text or "")):
        if (name, value) not in seen:
            seen.add((name, value))
            out.append((name, value))
    return out[:_MAX_MARKERS]


def _normalize_eq(text: str) -> str:
    """'LEN= 3' → 'LEN=3': confronto robusto col marker (i modelli piccoli
    alternano `print("LEN=", x)` e `print(f"LEN={x}")`)."""
    return re.sub(r"\s*=\s*", "=", str(text or ""))


def verify_runtime(code: str, out_path: Path,
                   expected_markers: Optional[list[tuple[str, str]]] = None,
                   timeout: int = RUNTIME_TIMEOUT_S,
                   python: Optional[str] = None) -> tuple[Optional[str], str]:
    """Esegue il programma generato e verifica l'output REALE.

    Fail su: ① exit ≠ 0 ② traceback in stderr ③ marker NAME=value attesi
    mancanti nel stdout (confronto normalizzato). I marker sono quelli
    estratti dal testo del task: assenza di marker → solo exit/traceback.

    GUI (QApplication/mainloop nel codice): il timeout E' il successo —
    significa che il programma e' entrato nel loop eventi senza crash.
    Il run parte sempre con cwd = cartella progetto (i file relativi
    scritti dal programma finiscono nel progetto) e QT offscreen.

    Returns:
        (error, stdout): error None = OK, altrimenti messaggio compatto
        (<= ~400 char) pronto per il correction prompt.
    """
    code_src = str(code or "")
    is_gui = any(hint in code_src for hint in _GUI_HINTS)
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    python_cmd = python or sys.executable
    # Percorsi ASSOLUTI: il cwd del processo e' la cartella progetto —
    # con un path relativo il doppio incrocio genera project/../project…
    target = Path(out_path).resolve()
    try:
        proc = subprocess.run(
            [python_cmd, str(target)],
            capture_output=True, text=True, errors="replace",
            timeout=timeout, cwd=str(target.parent), env=env)
    except subprocess.TimeoutExpired:
        if is_gui:
            return None, ""  # entrato nel loop eventi: successo
        return (f"RUNTIME ERROR: timeout dopo {timeout}s "
                "(loop infinito o attesa input?)"), ""
    except Exception as e:  # permessi, interprete mancante, ...
        return f"RUNTIME ERROR: esecuzione impossibile: {e}", ""

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    # Python 3.13+ colora i traceback con ANSI: il correction prompt
    # deve restare pulito per un modello piccolo.
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    stdout = ansi.sub("", stdout)
    stderr = ansi.sub("", stderr)
    if proc.returncode != 0 or "Traceback (most recent call last)" in stderr:
        tail = [ln for ln in stderr.splitlines() if ln.strip()][-3:]
        return (f"RUNTIME ERROR exit={proc.returncode}: "
                f"{' | '.join(tail)[:400]}"), stdout
    # Marker attesi presenti? (confronto con '=' normalizzato)
    markers = expected_markers or []
    if markers:
        norm = _normalize_eq(stdout)
        missing = [f"{n}={v}" for n, v in markers
                   if f"{n}={v}" not in norm]
        if missing:
            got = _normalize_eq(stdout)[:200] or "(vuoto)"
            return ("RUNTIME ERROR: output atteso mancante: "
                    f"{', '.join(missing)}. Output ottenuto: {got}"), stdout
    return None, stdout


def _build_direct_prompt(title: str, description: str,
                         skill_block: str, map_section: str = "") -> str:
    """Prompt diretto: task + (skill se presente) + (mappa progetto) +
    regole di output."""
    # La description puo' essere fresca oppure un correction prompt di un
    # retry gia' fatto dal dispatcher: lo riconosciamo dalle sue sezioni
    # (in quel caso va incluso per intero, non rinchiudo in DESCRIPTION).
    is_correction = any(
        marker in description
        for marker in ("## ERROR", "## SKILL", "## PREVIOUS"))
    parts = [f"## TASK\n{title}"]
    if description and not is_correction:
        parts += [f"\n## DESCRIPTION\n{description[:500]}"]
    elif description:
        # Retry: la description e' un correction prompt completo
        parts += [f"\n{description[:2500]}"]
    if skill_block:
        parts += [f"\n{skill_block}"]
    if map_section:
        parts += [f"\n{map_section}"]
    parts += [
        "\n## OUTPUT RULES\n"
        "- Output ONE fenced code block (```python ... ```) with the "
        "COMPLETE file content.\n"
        "- No explanations before or after the code block.\n"
        "- Fill ONLY the {{...}} placeholders; keep every other line "
        "unchanged.\n"
    ]
    return "\n".join(parts)


def _default_client(cfg=None):
    """ModelClient dalla config (chiavi [models.*] del toml); cfg
    opzionale per riusare quella già caricata dal routing."""
    import logging

    from CORE.ollama_client import ModelClient
    from CORE.orchestrator import load_config

    return ModelClient(cfg if cfg is not None else load_config(),
                       logging.getLogger("skill_executor"))


def _is_real_client(client) -> bool:
    """True se il client è None (CLI) o il ModelClient reale (worker
    GUI) → routing attivo. Un client finto (test) lo spegne: i test
    devono restare deterministici."""
    if client is None:
        return True
    try:
        from CORE.ollama_client import ModelClient
        return isinstance(client, ModelClient)
    except Exception:
        return False


def run_direct(task: dict, project_root: str,
               model_key: str = "worker_coder",
               client=None,
               max_retries: int = 3,
               filename: str = DEFAULT_FILENAME,
               enable_routing: Optional[bool] = None) -> dict:
    """Esegue il task in modalita' diretta (modello SENZA tool).

    Args:
        task: dict con almeno 'title' (e opzionale 'description'; se la
            description e' un correction prompt di un retry, viene usata
            come prompt di correzione iniziale).
        project_root: cartella progetto dove scrivere il file.
        model_key: chiave in [models.*] di CONFIG/config.toml.
        client: ModelClient iniettabile; default auto-costruito. Con
            client None o ModelClient REALE il routing e' attivo
            (Fasi 6-7); con un client finto (test) resta OFF.
        max_retries: tentativi totali (generazione + correzioni).
        filename: file di output (default main.py, come le skill).
        enable_routing: forzatura esplicita del routing; None = auto.

    Returns:
        dict {ok, path, attempts, error, model, route?, code?, history}
        — mai solleva. `model` = chiave effettivamente usata (dopo il
        routing), `route` = decisione leggibile (solo live).
    """
    title = str(task.get("title", ""))
    description = str(task.get("description", ""))
    root = Path(project_root)
    out_path = root / filename

    # 🆕 Routing per complessità + IMPATTO (Fasi 6-7): livello = max
    # (keyword, grafo del code_map), con isteresi. Il risultato dice
    # QUALE modello ha lavorato e PERCHÉ (route).
    if enable_routing is None:
        enable_routing = _is_real_client(client)
    used_model = model_key
    route_reason = ""
    cfg = None
    if enable_routing:
        log = logging.getLogger("skill_executor")
        try:
            from CORE.orchestrator import load_config
            cfg = load_config()
        except Exception:
            cfg = None
        try:
            from CORE import model_knowledge as mk
            from CORE.routing import route_model_key
            installed = mk.installed_names()
            used_model, _level, route_reason = route_model_key(
                title, description, cfg, model_key, installed,
                project_root=str(root), exclude_files={filename})
            log.info("[routing] %s", route_reason)
        except Exception:
            route_reason = ""  # fail-open: resta il modello base
    client = client if client is not None else _default_client(cfg)

    # Skill solo se il task e' fresco: in retry la description contiene
    # gia' la skill (correction.py la re-inietta) — niente duplicati.
    is_fresh = "## SKILL" not in description
    skill_block = ""
    if is_fresh:
        try:
            sk = find_skill(title, description)
            if sk is not None:
                skill_block = format_skill_block(sk)
        except Exception:
            skill_block = ""  # fail-open

    # Marker di output attesi (NAME=value): estratti dal task FRESCO
    # (in retry la description e' il correction prompt, che contiene
    # comunque il task originale — userei doppioni: resta il titolo).
    expected_markers = extract_expected_markers(
        f"{title}\n{description}" if is_fresh else title)

    # 🆕 Mappa del codice del progetto (AST → SQLite): simboli esistenti
    # nel prompt + arricchimento degli errori statici. Fail-open totale.
    try:
        map_section = render_map_section(root, exclude_files={filename})
    except Exception:
        map_section = ""

    attempts = 0
    error: Optional[str] = None
    code = ""
    previous_correction = ""
    last_stdout = ""
    history: list[dict] = []

    while attempts < max(1, max_retries):
        attempts += 1
        if error:
            # l'errore e' quello dell'attempt precedente: lo registro
            # con il numero dell'attempt che l'ha prodotto
            history.append({"attempt": attempts - 1,
                            "error": str(error)[:200]})
        if error:
            prompt = build_correction_prompt(
                title, code, error, previous_prompt=previous_correction,
                direct=True)
            previous_correction = prompt
        else:
            prompt = _build_direct_prompt(title, description, skill_block,
                                          map_section)
        try:
            text = client.call(used_model, prompt, system=SYSTEM_DIRECT)
        except Exception as e:
            return {"ok": False, "path": None, "attempts": attempts,
                    "error": f"LLM call failed: {e}", "model": used_model,
                    "route": route_reason, "history": history}
        code = extract_code(text)
        if not code:
            error = "Response contained no usable code block."
            continue
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # newline finale: i fenced block arrivano senza \n di coda
            out_path.write_text(
                code if code.endswith("\n") else code + "\n",
                encoding="utf-8")
        except Exception as e:
            return {"ok": False, "path": str(out_path), "attempts": attempts,
                    "error": f"write failed: {e}", "model": used_model,
                    "route": route_reason, "history": history}
        error = verify_python(code)
        if error is not None:
            continue  # errore di compilazione → correction prompt
        # 🆕 Gate STATICO dei nomi: i NameError latenti (variabile mai
        # creata, refuso) vengono beccati SENZA eseguire, con i simboli
        # reali del progetto come suggerimento di correzione.
        try:
            unknown = check_code_names(code)
        except Exception:
            unknown = []
        if unknown:
            avail = ""
            try:
                names = sorted({s["name"] for s in symbols(root)})
                if names:
                    avail = (f" Simboli disponibili nel progetto: "
                             f"{', '.join(names[:12])}.")
            except Exception:
                pass
            error = ("STATIC CHECK: nomi usati ma mai definiti/importati: "
                     + ", ".join(f"{n} (riga {ln})" for n, ln in unknown)
                     + "." + avail
                     + " Definiscili o correggi il nome.")
            continue
        # Gate RUNTIME (Fase 3): il programma viene ESEGUITO. Vedra' i
        # crash rimasti e l'output sbagliato che py_compile non vede.
        runtime_error, last_stdout = verify_runtime(
            code, out_path, expected_markers=expected_markers)
        if runtime_error is None:
            return {"ok": True, "path": str(out_path), "attempts": attempts,
                    "error": None, "model": used_model,
                    "route": route_reason,
                    "code": code[:MAX_CODE_CHARS],
                    "stdout": last_stdout[:MAX_STDOUT_CHARS],
                    "history": history}
        error = runtime_error
        # fallimento runtime → il loop rientra con il correction prompt

    return {"ok": False, "path": str(out_path), "attempts": attempts,
            "error": error, "model": used_model, "route": route_reason,
            "code": code[:MAX_CODE_CHARS],
            "stdout": last_stdout[:MAX_STDOUT_CHARS], "history": history}


if __name__ == "__main__":
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(
        description="Generazione diretta con skill (LLM senza tool)")
    ap.add_argument("task", help="Titolo/descrizione del task")
    ap.add_argument("--project", default="project/PR_TEST_progetto",
                    help="Cartella progetto di destinazione")
    ap.add_argument("--model", default="worker_coder",
                    help="Chiave modello in CONFIG/config.toml [models.*]")
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--filename", default=DEFAULT_FILENAME)
    args = ap.parse_args()

    res = run_direct({"title": args.task}, args.project,
                     model_key=args.model, max_retries=args.max_retries,
                     filename=args.filename)
    print(json.dumps({k: v for k, v in res.items() if k != "code"},
                     indent=2, ensure_ascii=False))
    sys.exit(0 if res["ok"] else 1)
