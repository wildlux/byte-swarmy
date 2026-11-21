#!/usr/bin/env python3
"""CORE/kernel_api_whitelist.py — whitelist deterministica di API kernel per versione.

Un'API kernel non nella whitelist è sospetta (possibile allucinazione).
La whitelist è derivata dagli header del kernel target (tools/extract_kernel_refs.py)
e persistita in CORE/refs/linux_kernel_<ver>_whitelist.json.

Zero LLM, nessuna rete.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).parent.parent.resolve()
REFS_DIR = BASE_DIR / "CORE" / "refs"

# Simbodo C standard / keyword da escludere dal controllo.
_C_BUILTINS = frozenset({
    "if", "while", "for", "switch", "return", "sizeof", "defined",
    "printf", "printk", "sprintf", "snprintf", "memcpy", "memset",
    "strlen", "strcmp", "strcpy", "strncpy", "malloc", "free", "NULL",
    "container_of", "likely", "unlikely", "BUILD_BUG_ON", "WARN_ON",
    "dev_err", "dev_info", "dev_warn", "dev_dbg", "pr_info", "pr_err",
    "pr_warn", "pr_debug", "pr_notice",
})

# Regex per chiamate di funzione in C.
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


def _whitelist_path(version: str) -> Path:
    return REFS_DIR / f"linux_kernel_{version}_whitelist.json"


def load_whitelist(version: str | None = None) -> set[str]:
    """Carica la whitelist per la versione (o quella del kernel corrente)."""
    if version is None:
        version = os.uname().release
    path = _whitelist_path(version)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return set(data)
            if isinstance(data, dict):
                return set(data.get("symbols", []))
        except Exception:
            pass
    # Fallback: prova a generare dagli header disponibili.
    return _generate_from_headers(version)


def _generate_from_headers(version: str) -> set[str]:
    """Genera la whitelist estraendo i prototipi dagli header del kernel."""
    import sys
    sys.path.insert(0, str(BASE_DIR))
    try:
        from tools.extract_kernel_refs import generate
    except Exception:
        return set()
    headers = Path("/lib/modules") / version / "build" / "include"
    if not headers.is_dir():
        return set()
    # Usa generate per ottenere i nomi (senza scrivere file).
    text, _ = generate(None, headers, 100000)
    names = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- `") and line.endswith("`"):
            names.add(line[3:-1])
    return names


def save_whitelist(version: str, symbols: set[str]) -> Path:
    """Salva la whitelist su disco."""
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    path = _whitelist_path(version)
    path.write_text(
        json.dumps(sorted(symbols), indent=2, ensure_ascii=False),
        encoding="utf-8")
    return path


def extract_calls(source: str) -> set[str]:
    """Estrae i nomi di funzione chiamati in un sorgente C."""
    return set(_CALL_RE.findall(source or ""))


def check_source(source: str, version: str | None = None,
                 known: Iterable[str] = ()) -> list[str]:
    """Restituisce i simbodo chiamati nel sorgente che NON sono nella
    whitelist (possibili allucinazioni).

    `known` sono simbodo aggiuntivi considerati validi (es. funzioni
    definite nello stesso file, macro locali).
    """
    if version is None:
        version = os.uname().release
    whitelist = load_whitelist(version)
    whitelist |= set(known) | _C_BUILTINS
    calls = extract_calls(source)
    unknown = sorted(c for c in calls if c not in whitelist)
    return unknown


def is_allowed(symbol: str, version: str | None = None) -> bool:
    """True se il simbodo è nella whitelist (o è un builtin C)."""
    if symbol in _C_BUILTINS:
        return True
    wl = load_whitelist(version)
    return symbol in wl


def format_unknown(unknown: list[str], limit: int = 20) -> str:
    """Formatta la lista di simbodo sconosciuti per il prompt di correction."""
    if not unknown:
        return ""
    items = unknown[:limit]
    lines = [f"  - {s}" for s in items]
    if len(unknown) > limit:
        lines.append(f"  ... e altri {len(unknown) - limit}")
    return "\n".join(lines)
