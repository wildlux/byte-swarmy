"""CORE/skill_executor.py — Generazione DIRETTA con skill (LLM SENZA tool).

Per modelli che non supportano il tool-calling: il loop ReAct del Worker
(write_file/lint_code come azioni del modello) e' sostituito da un ciclo
interamente lato HOST:

    prompt(skill + task) → risposta del modello → estrazione del blocco
    di codice → scrittura su disco → py_compile → se fallisce:
    build_correction_prompt() → retry (fino a max_retries).

La skill qui vale DOPPIO: senza tool il modello non puo' "verificare",
quindi la ricetta (passi + template + DONE WHEN) e' l'unica bussola che
ha, e la verifica meccanica la fa il codice host (deterministica).

Usage CLI (test veloce, modello configurato in CONFIG/config.toml):
    python -m CORE.skill_executor "fammi un software di sommare 2 numeri" \
        --project project/PR_TEST_progetto --model worker_coder
"""

from __future__ import annotations

import logging
import py_compile
import re
from pathlib import Path
from typing import Optional

from CORE.correction import build_correction_prompt
from CORE.skills import find_skill, format_skill_block

DEFAULT_FILENAME = "main.py"
MAX_CODE_CHARS = 20_000

# System prompt per la modalità diretta: vincolo SECCO sull'output.
# I modelli piccoli senza tool devono produrre UN solo blocco di codice.
SYSTEM_DIRECT = (
    "You are a code generator. Output ONLY one fenced code block with the "
    "complete file content. No explanations, no text outside the code "
    "block. If a SKILL recipe is provided, follow it EXACTLY: fill ONLY "
    "the {{...}} placeholders and keep every other line unchanged."
)

_CODE_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S | re.I)


def extract_code(text: str) -> str:
    """Estrae il codice dalla risposta del modello.

    Preferisce il blocco rinchiuso piu' lungo (i modelli piccoli a volte
    aggiungono frammenti di esempio); se non ci sono fence ma il testo
    sembra codice puro, lo restituisce intiero.
    """
    raw = str(text or "")
    blocks = _CODE_FENCE_RE.findall(raw)
    if blocks:
        best = max(blocks, key=len).strip("\n")
        return best[:MAX_CODE_CHARS]
    stripped = raw.strip()
    # Codice puro senza fence: deve sembrare Python (keyword note o print).
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


def _build_direct_prompt(title: str, description: str,
                         skill_block: str) -> str:
    """Prompt diretto: task + (skill se presente) + regole di output."""
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
    parts += [
        "\n## OUTPUT RULES\n"
        "- Output ONE fenced code block (```python ... ```) with the "
        "COMPLETE file content.\n"
        "- No explanations before or after the code block.\n"
        "- Fill ONLY the {{...}} placeholders; keep every other line "
        "unchanged.\n"
    ]
    return "\n".join(parts)


def _default_client():
    """ModelClient dalla config standard (chiavi [models.*] del toml)."""
    import logging

    from CORE.ollama_client import ModelClient
    from CORE.orchestrator import load_config

    return ModelClient(load_config(), logging.getLogger("skill_executor"))


def run_direct(task: dict, project_root: str,
               model_key: str = "worker_coder",
               client=None,
               max_retries: int = 3,
               filename: str = DEFAULT_FILENAME) -> dict:
    """Esegue il task in modalita' diretta (modello SENZA tool).

    Args:
        task: dict con almeno 'title' (e opzionale 'description'; se la
            description e' un correction prompt di un retry, viene usata
            come prompt di correzione iniziale).
        project_root: cartella progetto dove scrivere il file.
        model_key: chiave in [models.*] di CONFIG/config.toml.
        client: ModelClient iniettabile (test); default auto-costruito.
        max_retries: tentativi totali (generazione + correzioni).
        filename: file di output (default main.py, come le skill).

    Returns:
        dict {ok, path, attempts, error, code?} — mai solleva.
    """
    title = str(task.get("title", ""))
    description = str(task.get("description", ""))
    root = Path(project_root)
    out_path = root / filename
    client = client if client is not None else _default_client()

    # Skill solo se il task e' fresco: in retry la description contiene
    # gia' la skill (correction.py la re-inietta) — niente duplicati.
    skill_block = ""
    if "## SKILL" not in description:
        try:
            sk = find_skill(title, description)
            if sk is not None:
                skill_block = format_skill_block(sk)
        except Exception:
            skill_block = ""  # fail-open

    attempts = 0
    error: Optional[str] = None
    code = ""
    previous_correction = ""

    while attempts < max(1, max_retries):
        attempts += 1
        if error:
            prompt = build_correction_prompt(
                title, code, error, previous_prompt=previous_correction)
            previous_correction = prompt
        else:
            prompt = _build_direct_prompt(title, description, skill_block)
        try:
            text = client.call(model_key, prompt, system=SYSTEM_DIRECT)
        except Exception as e:
            return {"ok": False, "path": None, "attempts": attempts,
                    "error": f"LLM call failed: {e}"}
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
                    "error": f"write failed: {e}"}
        error = verify_python(code)
        if error is None:
            return {"ok": True, "path": str(out_path), "attempts": attempts,
                    "error": None, "code": code[:MAX_CODE_CHARS]}
        # errore di compilazione → il loop rientra con il correction prompt

    return {"ok": False, "path": str(out_path), "attempts": attempts,
            "error": error}


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
