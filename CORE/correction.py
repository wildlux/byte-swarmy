"""
correction.py — Post-execution feedback loop (work order T2).

build_correction_prompt(original_task, previous_code, stderr) costruisce
il prompt direttivo per il prossimo tentativo:
- i path assoluti dell'utente vengono anonimizzati ([PATH]);
- l'errore e' limitato ai primi MAX_ERROR_FRAMES frame o 500 caratteri;
- ogni sezione e' troncata a MAX_PROMPT_CHARS (vincolo globale 500).

Il dispatcher usa il prompt ritornato per SOVRASCRIVERE la description
del task fino a RETRY_LIMIT tentativi; al 4° fallimento lo stato diventa
"failed_definitively" (nessun loop infinito).
"""
from __future__ import annotations

import re
from typing import Optional

# Constraint globale: nessuna stringa iniettata nel prompt > 500 caratteri
MAX_PROMPT_CHARS = 500
MAX_ERROR_FRAMES = 5

# /home/wildlux/... -> [PATH]  (leva via l'identita' e accorcia)
_PATH_RE = re.compile(r"/home/[^/\s]+(?=/|\s|:|$)")

_DIRECTIVE_HEAD = (
    "Correggi il seguente errore e restituisci solo il codice. "
    "Non spiegare, non ripetere il codice invariato."
)
_DIRECTIVE_TAIL = (
    "Next step (JSON only, "
    'format: {"action": "write_file", "args": ["<path>", "<codice corretto>"]}):'
)


def sanitize_paths(text: str) -> str:
    """Anonimizza i path assoluti /home/<utente>/... -> [PATH]/..."""
    return _PATH_RE.sub("[PATH]", str(text or ""))


def limit_error(stderr: str,
                max_frames: int = MAX_ERROR_FRAMES,
                max_chars: int = MAX_PROMPT_CHARS) -> str:
    """Limita lo stderr ai primi `max_frames` righe/frame e 500 caratteri.

    Le righe tipo 'File "..." line N' sono un frame; blockquote di traceback
    python e gcc hanno comunque righe: manteniamo la testata di ogni frame.
    """
    raw = sanitize_paths(str(stderr or ""))
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    kept = lines[:max_frames]
    out = "\n".join(kept)
    if len(out) > max_chars:
        out = out[:max_chars]
    return out


def clamp(text: str, max_chars: int = MAX_PROMPT_CHARS) -> str:
    s = sanitize_paths(text)
    return s[:max_chars]


def build_correction_prompt(original_task: str,
                            previous_code: str,
                            stderr: str,
                            previous_prompt: Optional[str] = None) -> str:
    """Prompt direttivo di correzione (ogni sezione <= 500 caratteri).

    Args:
        original_task: titolo/descrizione originale del task.
        previous_code: codice scritto nell'ultimo tentativo (puo' essere "").
        stderr: errore catturato (proviene da run_result o eccezione worker).
        previous_prompt: prompt precedente, se gia' sovrascritto.

    Returns:
        prompt pronto per la description del task al prossimo tentativo.
    """
    parts = [
        _DIRECTIVE_HEAD,
        "",
        f"## TASK ORIGINALE\n{clamp(original_task)}",
        "",
        f"## ERRORE\n{limit_error(stderr)}",
    ]

    code = sanitize_paths(previous_code or "")
    if code:
        prev = "\n".join(code.splitlines()[:MAX_PROMPT_CHARS // 40])
        parts += ["", f"## CODICE PRECEDENTE\n{clamp(prev)}"]

    if previous_prompt:
        parts += ["", f"## CORREZIONE PRECEDENTE\n{clamp(previous_prompt)}"]

    prompt = "\n".join(parts)

    if len(prompt) > 2000:               # cap totale: description non esplode
        prompt = prompt[:2000]

    return f"{prompt}\n\n{_DIRECTIVE_TAIL}"
