"""
CORE/skill_proposer.py — M8: memoria dei fallimenti → skill suggerite.

Idea: il correction loop sa *cosa* è andato male (prosa senza fence,
placeholder copiato, try senza except, input() interattivo, marker
mancante, classe senza istanza, NameError…). Se una stessa "firma" di
fallimento si ripete N volte, il sistema genera una BOZZA di skill
basata sul skill più vicino e la mette in `state/skill_proposals/`
per approvazione umana — la libreria cresce sui TUOI errori ricorrenti.

Storage:
  - state/skill_proposals/failures.json  → contatori per firma
  - state/skill_proposals/<sig>_<n>.md   → bozze in attesa
Approvazione: `python -m CORE.skill_proposer --approve <id>` sposta
la bozza in `SKILLS/<name>.md` (dove il matcher la carica). Rifiuto:
`--reject <id>` la cancella. Fail-open ovunque: un errore qui non
blocca mai un task.

Soglia: 3 occorrenze (stessa del correction loop).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "SKILLS"
PROPOSALS_DIR = ROOT / "state" / "skill_proposals"
FAILURES_FILE = PROPOSALS_DIR / "failures.json"
THRESHOLD = 3

# Firma → (etichetta, skill base da cui partire, regola appresa)
SIGNATURES: dict[str, dict] = {
    "prosa_senza_fence": {
        "label": "Prosa prima del codice (niente fence ```python)",
        "base": "py-cli-script.md",
        "rule": ("Il modello apre con testo libero ('Okay, let's tackle…') "
                 "senza il fence ```python in prima riga. La risposta DEVE "
                 "iniziare direttamente con ```python e contenere solo codice."),
    },
    "placeholder_copiato": {
        "label": "Placeholder {{...}} copiato letteralmente",
        "base": "py-text-analyze.md",
        "rule": ("Un segnaposto {{...}} è rimasto nel codice → errore di "
                 "sintassi. Sostituire TUTTI i placeholder con codice reale; "
                 "i commenti `# HINT` sono solo suggerimenti, vanno attivati "
                 "se il task lo richiede."),
    },
    "try_senza_except": {
        "label": "try: senza except/finally",
        "base": "py-class-module.md",
        "rule": ("Ogni `try:` aperto DEVE avere il suo `except` (o "
                 "`finally`). Mai cancellare un blocco except. Per eccezioni "
                 "personalizzate: `class NomeError(Exception)`."),
    },
    "input_interattivo": {
        "label": "Uso di input()/stdin (script non interattivo)",
        "base": "py-cli-script.md",
        "rule": ("Lo script gira non-interattivamente (stdin vuoto). MAI "
                 "usare input(): hard-codificare i valori d'esempio del "
                 "task e stampare il risultato."),
    },
    "marker_mancante": {
        "label": "Marker atteso non stampato (LEN=, SOMMA=, …)",
        "base": "py-class-module.md",
        "rule": ("Stampare TUTTI i marker che il task richiede, con il "
                 "valore LETTERALE scritto nel task (ok, True, 42…), mai il "
                 "messaggio dell'eccezione. Leggere il task riga per riga."),
    },
    "classe_senza_istanza": {
        "label": "Metodo chiamato sulla classe invece che su un'istanza",
        "base": "py-class-module.md",
        "rule": ("Se il PROJECT MAP mostra una classe, usare un'ISTANZA: "
                 "`obj = Class(); obj.method()`. Mai `Class.method()`."),
    },
    "nome_inedito": {
        "label": "NameError: nome usato ma mai definito/importato",
        "base": "py-cli-script.md",
        "rule": ("Ogni nome usato deve essere definito o importato. "
                 "Riutilizzare i simboli del PROJECT MAP invece di "
                 "allucinare API."),
    },
    "loop_infinito": {
        "label": "Loop infinito (iteratore ricreato nel while)",
        "base": "py-class-module.md",
        "rule": ("Drain: creare l'iteratore UNA SOLA VOLTA fuori dal "
                 "loop (`it = iter(coll)`), poi `next(it)` dentro; "
                 "`next(iter(x))` nel loop crea un iteratore fresco a "
                 "ogni giro → mai StopIteration. Il drain più sicuro è "
                 "`for item in coll: print(item)`."),
    },
    "generico": {
        "label": "Fallimento generico (nessuna firma riconosciuta)",
        "base": "py-cli-script.md",
        "rule": ("Verificare che il codice compili, giri e stampi i "
                 "marker attesi prima di dichiarare ok."),
    },
}


def classify_failure(error: str, code: str = "") -> str:
    """Classifica un errore di run_direct in una firma riconosciuta."""
    e = (error or "").lower()
    c = (code or "").lower()
    if "eoferror" in e or "input(" in c:
        return "input_interattivo"
    if "placeholder" in e or "{{" in c:
        return "placeholder_copiato"
    if "expected 'except' or 'finally'" in e or "expected \"except\"" in e:
        return "try_senza_except"
    if "output atteso mancante" in e:
        return "marker_mancante"
    if "no attribute" in e or "function' object" in e or "has no attribute" in e:
        return "classe_senza_istanza"
    if "nameerror" in e or "name '" in e:
        return "nome_inedito"
    if "timeout" in e and ("loop" in e or "input" in e):
        return "loop_infinito"
    if "pycompileerror" in e and "the output should" in e:
        return "prosa_senza_fence"
    if "pycompileerror" in e or "syntaxerror" in e:
        return "prosa_senza_fence" if "okay" in c or "let's" in c else "generico"
    return "generico"


def _load_failures() -> dict:
    try:
        if FAILURES_FILE.exists():
            return json.loads(FAILURES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"counts": {}, "last_seen": {}, "proposals": {}}


def _save_failures(data: dict) -> None:
    try:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        FAILURES_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


def record_failure(signature: str, task_title: str = "",
                   error: str = "") -> Optional[str]:
    """Registra un fallimento. Se la firma raggiunge THRESHOLD e non c'è
    già una bozza pendente, crea la bozza e ne restituisce l'id.

    Ritorna l'id della bozza creata (o None se nessuna creata).
    Fail-open: mai solleva.
    """
    try:
        if signature not in SIGNATURES:
            signature = "generico"
        data = _load_failures()
        counts = data.setdefault("counts", {})
        counts[signature] = counts.get(signature, 0) + 1
        data.setdefault("last_seen", {})[signature] = time.time()
        data.setdefault("proposals", {})
        _save_failures(data)

        if counts[signature] >= THRESHOLD and signature not in data["proposals"]:
            return _create_proposal(signature, task_title, error, counts[signature])
        return None
    except Exception:
        return None


def _create_proposal(signature: str, task_title: str, error: str,
                     count: int) -> Optional[str]:
    """Genera la bozza di skill in state/skill_proposals/."""
    try:
        info = SIGNATURES[signature]
        base_path = SKILLS_DIR / info["base"]
        base_content = ""
        if base_path.exists():
            base_content = base_path.read_text(encoding="utf-8")

        prop_id = f"{signature}_{int(time.time())}"
        draft_path = PROPOSALS_DIR / f"{prop_id}.md"
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

        # G1: Bozza con template CONCRETO (non solo la regola).
        # Il template è basato sulla firma: include un esempio di codice
        # corretto che il modello può copiare e adattare.
        templates = {
            "input_interattivo": (
                "import sys\n\n"
                "# MAI usare input(): hard-codifica i valori del task\n"
                "valori = [25]  # esempio dal task\n"
                "for v in valori:\n"
                "    risultato = v * 9 / 5 + 32\n"
                "    print(f\"RISULTATO={risultato}\")\n"),
            "marker_mancante": (
                "# Stampa TUTTI i marker richiesti dal task\n"
                "print(f\"MARKER={valore}\")  # adatta nome e valore\n"),
            "try_senza_except": (
                "try:\n"
                "    {{ FILL IT }}\n"
                "except Exception as e:\n"
                "    print(e)\n"),
            "loop_infinito": (
                "it = iter(coll)\n"
                "while True:\n"
                "    try:\n"
                "        print(next(it))\n"
                "    except StopIteration:\n"
                "        break\n"),
        }
        template = templates.get(signature, "# {{ IMPLEMENTAZIONE }}\n")

        learned = (
            "\n\n---\n# REGOLA APPRESA (bozza — da approvare)\n\n"
            f"Firma fallimento: `{signature}` ({info['label']})\n"
            f"Occorrenze osservate: {count}\n"
            f"Ultimo task: {task_title[:120]}\n"
            f"Ultimo errore: {error[:200]}\n\n"
            "## Regola\n"
            f"{info['rule']}\n\n"
            "## Template concreto\n"
            f"```python\n{template}```\n\n"
            "## Azione richiesta\n"
            "Rivedi questa bozza, modificala se necessario, poi approva con:\n"
            f"  python -m CORE.skill_proposer --approve {prop_id}\n"
            "oppure rifiuta con:\n"
            f"  python -m CORE.skill_proposer --reject {prop_id}\n"
        )
        draft_path.write_text(base_content + learned, encoding="utf-8")

        # Registra la proposta
        data = _load_failures()
        data.setdefault("proposals", {})[signature] = {
            "id": prop_id,
            "path": str(draft_path),
            "count": count,
            "created_at": time.time(),
            "status": "pending",
        }
        _save_failures(data)
        return prop_id
    except Exception:
        return None


def pending_proposals() -> list[dict]:
    """Lista delle bozze in attesa di approvazione."""
    try:
        data = _load_failures()
        out = []
        for sig, info in data.get("proposals", {}).items():
            p = Path(info["path"])
            if info.get("status") == "pending" and p.exists():
                out.append({
                    "id": info["id"],
                    "signature": sig,
                    "label": SIGNATURES.get(sig, {}).get("label", sig),
                    "count": info.get("count", 0),
                    "path": str(p),
                    "preview": p.read_text(encoding="utf-8")[:400],
                })
        return out
    except Exception:
        return []


def approve_proposal(prop_id: str) -> bool:
    """Approva una bozza: la sposta in SKILLS/ (dove il matcher la carica)."""
    try:
        data = _load_failures()
        for sig, info in data.get("proposals", {}).items():
            if info.get("id") == prop_id and info.get("status") == "pending":
                src = Path(info["path"])
                if not src.exists():
                    return False
                # nome skill dal filename della base (stesso id della base)
                base = SIGNATURES[sig]["base"]
                skill_name = base  # sovrascrive la skill base con la versione appresa
                dst = SKILLS_DIR / skill_name
                # Backup della skill base prima di sovrascrivere
                if dst.exists():
                    backup = SKILLS_DIR / f"{dst.stem}.backup.md"
                    shutil.copy2(dst, backup)
                shutil.move(str(src), str(dst))
                info["status"] = "approved"
                info["approved_at"] = time.time()
                _save_failures(data)
                return True
        return False
    except Exception:
        return False


def reject_proposal(prop_id: str) -> bool:
    """Rifiuta una bozza: la cancella e resetta il contatore della firma."""
    try:
        data = _load_failures()
        for sig, info in data.get("proposals", {}).items():
            if info.get("id") == prop_id and info.get("status") == "pending":
                p = Path(info["path"])
                if p.exists():
                    p.unlink()
                info["status"] = "rejected"
                info["rejected_at"] = time.time()
                # resetta il contatore: l'utente ha detto "non è un problema"
                data.setdefault("counts", {})[sig] = 0
                _save_failures(data)
                return True
        return False
    except Exception:
        return False


# ── G2: auto-approvazione dopo N successi ─────────────────────────────
def record_skill_usage(skill_id: str, success: bool) -> Optional[str]:
    """Traccia l'uso di una skill suggerita. Se usata 3 volte senza
    fallimenti → auto-approvazione (con log). Ritorna l'id approvato
    o None. Fail-open.
    """
    try:
        data = _load_failures()
        usage = data.setdefault("usage", {})
        u = usage.setdefault(skill_id, {"success": 0, "fail": 0})
        if success:
            u["success"] = u.get("success", 0) + 1
        else:
            u["fail"] = u.get("fail", 0) + 1
        _save_failures(data)

        # Auto-approve se 3 successi consecutivi senza fallimenti
        if (u.get("success", 0) >= 3 and u.get("fail", 0) == 0):
            # Trova la proposta pendente con questo skill_id
            for sig, info in data.get("proposals", {}).items():
                if info.get("status") == "pending" and sig in skill_id:
                    ok = approve_proposal(info["id"])
                    if ok:
                        return info["id"]
        return None
    except Exception:
        return None


def _cli() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m CORE.skill_proposer",
        description="M8: bozze di skill generate dai fallimenti ricorrenti.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true",
                   help="Lista le bozze in attesa di approvazione.")
    g.add_argument("--approve", metavar="ID",
                   help="Approva una bozza (la sposta in SKILLS/).")
    g.add_argument("--reject", metavar="ID",
                   help="Rifiuta una bozza (la cancella).")
    args = parser.parse_args()

    if args.list:
        props = pending_proposals()
        if not props:
            print("Nessuna bozza in attesa.")
            return 0
        for p in props:
            print(f"\n[{p['id']}] {p['label']} (occorrenze: {p['count']})")
            print(f"  file: {p['path']}")
            print(f"  preview: {p['preview'][:200].replace(chr(10), ' | ')}")
        return 0
    if args.approve:
        ok = approve_proposal(args.approve)
        print("APPROVATA" if ok else "NON TROVATA / già gestita")
        return 0 if ok else 1
    if args.reject:
        ok = reject_proposal(args.reject)
        print("RIFIUTATA" if ok else "NON TROVATA / già gestita")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
