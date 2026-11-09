"""
regex_controller.py — Controllore centralizzato delle regex del progetto.

Motivazione: nel progetto ci sono decine di usi di `re.` sparsi (parsing
JSON da output LLM, estrazioni "RISULTATO: <num>", nomi def/class Python,
path, blocchi markdown, …). Questo modulo offre:

1. Un REGISTRO di pattern precompilati per nome ("json_object",
   "py_def", "home_path", …) con cache di compilazione
   (functools.lru_cache).
2. Helper statici per i casi d'uso reali: numeri etichettati, primo
   blocco JSON in testo misto LLM, blocchi di codice markdown, nomi
   sicuri per file/risorse, validazione ref/glob (stile tools.py).
3. Matching "any-of" su più pattern con gestione errori non-fatale.

I pattern invalidi NON sono fatali: vengono loggati e tenuti come None;
i metodi di matching sollevano KeyError chiaro solo quando il nome è
assente o invalido. Nessuna dipendenza fuori dalla stdlib.
"""
from __future__ import annotations

import functools
import logging
import re
from typing import Callable, Iterable, Optional, Union

log = logging.getLogger("byte-swarmy.regex_controller")


@functools.lru_cache(maxsize=512)
def compile_cached(pattern: str, flags: int = 0):
    """Compila una regex con cache; ritorna None se il pattern è invalido."""
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        log.error("Regex invalida (%s): %s", e, pattern[:120])
        return None


# ═══════════════════════════════════════════════════════════════════
# Pattern di default di BYTE-SWARMY (i flag inline sono nel pattern)
# ═══════════════════════════════════════════════════════════════════

DEFAULT_PATTERNS = {
    # ── output LLM → dati ───────────────────────────────────────────
    "json_object": r"\{[\s\S]*\}",                # primo oggetto {...} (orchestrator)
    "json_array": r"\[[\s\S]*\]",                 # primo array [...] (orchestrator)
    "code_fenced": r"(?s)```(?:[A-Za-z0-9_+-]+)?[ \t]*\n([\s\S]*?)```",  # ```code```
    # ── Python ──────────────────────────────────────────────────────
    "py_def": r"(?m)^def\s+([a-zA-Z_]\w*)\s*\(",   # nome della func su def
    "py_class": r"(?m)^class\s+([a-zA-Z_]\w*)\s*\(",
    "py_typed_signature": r"(?i)def\s+\w+\s*\([^)]*:\s*\w+",   # memory: tipizzata
    "py_docstring": r'(?s)""".*?"""',
    "py_comment": r"#\s+\w+",
    "py_dataclass": r"(?i)@dataclass",
    # ── esecuzione / controllo codice worker (harness, correction) ──
    "loop_increment": r"(?i)(i\s*\+=\s*1|i\s*=\s*i\s*\+\s*1|\bi\s*\+\+\b)",
    "off_by_one_fix": r"range\s*\(\s*1\s*,\s*n\s*\+\s*1\s*\)|range\s*\(\s*n\s*\+\s*1\s*\)",
    # ── filesystem (correction.py) ──────────────────────────────────
    "home_path": r"/home/[^/\s]+(?=/|\s|:|$)",
    "file_ext": r"\.[A-Za-z0-9]{1,5}$",
    # ── hint hardware (hardware_detector) ───────────────────────────
    "chip_line": r"Chip:\s*(.+)",
    "ram_gb": r"Memory:\s*(\d+)\s*GB",
}

# Hint linguistici (persistent_memory.py: identificar linguaggio di progetto)
LANG_HINTS = {
    "lang_python": r"(?i)\b(python|\.py|pip|django|flask|fastapi)\b",
    "lang_c": r"(?i)(\bgcc\b|\.c\b|\.h\b|makefile|cmake)",
    "lang_javascript": r"(?i)\b(javascript|\.js\b|node|npm)\b",
    "lang_rust": r"(?i)\b(rust|\.rs|cargo)\b",
    "hint_flask": r"(?i)\bflask\b",
    "hint_django": r"(?i)\bdjango\b",
    "hint_fastapi": r"(?i)\bfastapi\b",
    "hint_pytest": r"(?i)\bpytest\b",
    "hint_unittest": r"(?i)\bunittest\b",
}


# ═══════════════════════════════════════════════════════════════════
# RegexController — registro per-nome + matching
# ═══════════════════════════════════════════════════════════════════

class RegexController:
    """Registro di regex precompilate per nome.

    Usage:
        rc = RegexController()
        rc.add("risultati", r"RISULTATO\\s*[:=]\\s*(-?\\d+)")
        m = rc.search("risultati", "RISULTATO: 42")
        rc.findall("risultati", text)
    """

    def __init__(self, patterns: Optional[dict[str, str]] = None):
        self._compiled: dict[str, Optional[re.Pattern]] = {}
        for name, pattern in (patterns or {}).items():
            self.add(name, pattern)

    # ── gestione registro ──────────────────────────────────────────
    def add(self, name: str, pattern: str, flags: int = 0) -> bool:
        """Registra (o aggiorna) un pattern. Ritorna False se invalido."""
        compiled = compile_cached(pattern, flags)
        self._compiled[name] = compiled
        return compiled is not None

    def remove(self, name: str) -> None:
        """Rimuove un pattern dal registro (no-op se assente)."""
        self._compiled.pop(name, None)

    def has(self, name: str) -> bool:
        """True solo se il nome è registrato E il pattern è compilabile."""
        return bool(self._compiled.get(name))

    def names(self) -> list:
        """Nomi registrati (anche quelli invalidi, per ispezione)."""
        return sorted(self._compiled)

    def get(self, name: str) -> Optional[re.Pattern]:
        """Pattern compilato, senza eccezioni (None se assente/invalido)."""
        return self._compiled.get(name)

    def _need(self, name: str) -> re.Pattern:
        """Pattern compilato; KeyError chiaro se assente o invalido."""
        compiled = self._compiled.get(name)
        if compiled is None:
            if name in self._compiled:
                raise KeyError(
                    f"Pattern '{name}' invalido (vedi log byte-swarmy.regex_controller)")
            raise KeyError(f"Pattern '{name}' non registrato")
        return compiled

    # ── matching per nome ─────────────────────────────────────────
    def search(self, name: str, text: str) -> Optional[re.Match]:
        return self._need(name).search(text or "")

    def match(self, name: str, text: str) -> Optional[re.Match]:
        return self._need(name).match(text or "")

    def fullmatch(self, name: str, text: str) -> Optional[re.Match]:
        return self._need(name).fullmatch(text or "")

    def findall(self, name: str, text: str) -> list:
        return self._need(name).findall(text or "")

    def finditer(self, name: str, text: str) -> Iterable[re.Match]:
        return self._need(name).finditer(text or "")

    def sub(self, name: str, repl: Union[str, Callable], text: str,
            count: int = 0) -> str:
        return self._need(name).sub(repl, text or "", count)

    def split(self, name: str, text: str, maxsplit: int = 0) -> list:
        return self._need(name).split(text or "", maxsplit)

    # ── combinatori ───────────────────────────────────────────────
    def match_any(self, names: Iterable[str], text: str) -> Optional[re.Match]:
        """Primo match che riesce tra più pattern (i pattern invalidi/assenti
        vengono saltati senza interrompere l'evaluation)."""
        for name in names:
            compiled = self._compiled.get(name)
            if compiled is None:
                continue
            hit = compiled.search(text or "")
            if hit:
                return hit
        return None

    def first_matches(self, names: Iterable[str], text: str) -> list:
        """Lista [(nome, match)] della prima occorrenza di ogni pattern dato."""
        out = []
        for name in names:
            compiled = self._compiled.get(name)
            if compiled is None:
                continue
            hit = compiled.search(text or "")
            if hit:
                out.append((name, hit))
        return out


# ═══════════════════════════════════════════════════════════════════
# Helper statici riusabili (casi d'uso reali del progetto)
# ═══════════════════════════════════════════════════════════════════

def number_after_label(text: str, label: str = "RISULTATO") -> Optional[int]:
    """Ultimo numero dopo `label:` / `label=` (es. 'RISULTATO: 5050' → 5050)."""
    if not text or not label:
        return None
    pattern = re.escape(label) + r"\s*[:=]\s*(-?\d+)"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return int(matches[-1]) if matches else None


def last_number(text: str) -> Optional[int]:
    """Ultimo numero isolato nel testo (fallback senza etichetta)."""
    nums = re.findall(r"(?<![\w.])(-?\d+)(?![\w.])", text or "")
    return int(nums[-1]) if nums else None


def json_block(text: str) -> Optional[str]:
    """Primo blocco JSON in output LLM misto: prova array, poi oggetto.

    Equivalente ad orchestrator.py (che cerca \\[...\\] poi \\{...\\}).
    Ritorna il TESTO del blocco (non parsato) o None.
    """
    if not text:
        return None
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        return m.group(0)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return m.group(0)
    return None


def fenced_code(text: str, lang: str = "") -> Optional[str]:
    """Primo blocco di codice ``` del testo (filtro lingua opzionale).

    Ritorna il CONTENUTO del blocco o None.
    """
    if not text:
        return None
    if lang:
        pattern = r"```" + re.escape(lang) + r"[ \t]*\n([\s\S]*?)```"
    else:
        pattern = r"```(?:[A-Za-z0-9_+-]+)?[ \t]*\n([\s\S]*?)```"
    m = re.search(pattern, text, re.IGNORECASE if lang else 0)
    return m.group(1) if m else None


def sanitize_name(text: str, maxlen: int = 80, fallback: str = "x",
                  extra_ok: str = "") -> str:
    """Nomi sicuri per file/risorse: solo [a-z0-9._-] (+ caratteri extra_ok).

    Riusa qualunque caso tipo hfw_* (hf_weights), model key, report filename.
    """
    forbidden = re.compile(r"[^a-z0-9._" + re.escape(extra_ok or "") + r"\-]")
    cleaned = forbidden.sub("-", (text or "").lower())[:maxlen]
    return cleaned if cleaned else fallback


def validate_chars(value: str, kind: str = "ref") -> bool:
    """Validazione stile tools.py per id/glob prima di usarli.

    - "ref":  [A-Za-z0-9][A-Za-z0-9._/~^@-]{0,79}
    - "glob": [A-Za-z0-9_./*?\\[\\]-]{1,120}
    """
    if kind == "ref":
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/~^@-]{0,79}", value or ""))
    if kind == "glob":
        return bool(re.fullmatch(r"[A-Za-z0-9_./*?\[\]-]{1,120}", value or ""))
    raise ValueError(f"kind sconosciuto: {kind!r} (usare 'ref' o 'glob')")


def escape_literal(text: str) -> str:
    """Escape di testo per uso come regex letterale (Trova/nonna usa)."""
    return re.escape(text or "")


__all__ = [
    "RegexController", "compile_cached", "DEFAULT_PATTERNS", "LANG_HINTS",
    "number_after_label", "last_number", "json_block", "fenced_code",
    "sanitize_name", "validate_chars", "escape_literal",
]
