"""
execute_handler.py — Handler deterministico per i task type="execute".

Compila ed esegue senza passare dal worker LLM: i comandi vengono
estratti con regex dalla descrizione del task e passati a una callback
run(cmd) (tipicamente tools.run_bash). Zero chiamate al modello.

Se la descrizione non contiene comandi riconosciuti, la funzione ritorna
un messaggio d'errore esplicito con la guida per l'utente.

Comandi riconosciuti:
- compilazione:  gcc|g++|cc|clang|clang++ <src> -o <out>
- esecuzione:    il binario prodotto dalla compilazione
- script python: python[3] <path>.py
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional

# gcc/g++/cc/clang path/to/file.c(pp|x?) -o path/to/out
_COMPILER_RE = re.compile(
    r"\b(gcc|g\+\+|cc|clang(?:\+\+)?)\s+([^\s]+\.(?:c|cc|cpp|cxx|c\+\+))\s+"
    r"\-o\s+([^\s]+)",
    re.IGNORECASE,
)

# python3 path/to/file.py  (il .py è obbligatorio: niente esecuzioni generiche)
_PY_RE = re.compile(
    r"\bpython3?\s+([^\s]+\.py)\b",
    re.IGNORECASE,
)

_OUTPUT_PREVIEW = 1500


def parse_execute_commands(description: str) -> List[dict]:
    """Estrae le fasi (compilazione + esecuzione) dalla descrizione del task.

    Le fasi ritornate sono in ordine deterministico: prima tutte le
    compilazioni (nell'ordine in cui appaiono nel testo), poi le
    esecuzioni. Ritorna [] se non c'è nulla di riconosciuto.
    """
    desc = str(description or "")
    if len(desc) > 20000:
        desc = desc[:20000]

    steps: List[dict] = []

    for match in _COMPILER_RE.finditer(desc):
        compiler = match.group(1)
        src = match.group(2).rstrip(".,;:!?)")
        out = match.group(3).rstrip(".,;:!?)")
        steps.append({
            "kind": "compile",
            "cmd": f"{compiler} {src} -o {out}",
            "label": f"compilazione {src} -> {out}",
        })
        # il binario prodotto va eseguito: e' il senso di type=execute
        steps.append({
            "kind": "run",
            "cmd": out,
            "label": f"esecuzione {out}",
        })

    for match in _PY_RE.finditer(desc):
        script = match.group(1).rstrip(".,;:!?)")
        steps.append({
            "kind": "run",
            "cmd": f"python3 {script}",
            "label": f"esecuzione {script}",
        })

    # compila prima di eseguire, a prescindere dall'ordine nel testo
    steps.sort(key=lambda s: 0 if s["kind"] == "compile" else 1)
    return steps


def handle_execute_task(task: dict,
                        run_cmd: Callable[[str], str],
                        log: Optional[object] = None) -> str:
    """Esegue ogni fase in modo deterministico (no LLM).

    Args:
        task: task dalla coda (usa description + context).
        run_cmd: callback di esecuzione (tools.run_bash), riceve una
            stringa comando semplice e ritorna stdout oppure "ERROR: ...".
        log: logger opzionale.

    Returns:
        stringa result da salvare nella coda; il fallimento è segnalato
        con prefisso "ERROR:" (convenzione usata dall'orchestratore).
    """
    if not callable(run_cmd):
        return "ERROR: handler execute senza callback run cmd"

    desc = " ".join(
        str(task.get(key) or "") for key in ("description", "context")
    )
    steps = parse_execute_commands(desc)
    if not steps:
        return (
            "ERROR: nessun comando riconosciuto per type=execute. "
            "La descrizione deve contenere un comando esplicito, es: "
            "'gcc project/main.c -o project/main' o 'python3 project/script.py"
        )

    parts: List[str] = []
    for step in steps:
        if log is not None:
            log.info(f"execute: {step['label']} (no LLM)")
        out = run_cmd(step["cmd"])
        out_text = str(out or "")
        if out_text.startswith("ERROR"):
            return f"ERROR: {step['label']} fallita: {out_text}"
        parts.append(f"[{step['kind']}] {step['label']} -> OK")
        body = out_text.strip()
        if body:
            parts.append(body[:_OUTPUT_PREVIEW])

    return "execute OK\n" + "\n".join(parts)
