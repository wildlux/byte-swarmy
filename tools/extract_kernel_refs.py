#!/usr/bin/env python3
"""Estrae riferimenti API dal kernel Linux (header C) → CORE/refs/linux_kernel_<ver>.md.

Uso:
    .venv/bin/python tools/extract_kernel_refs.py [--subsystem i2c] [--out DIR] [--max 500]

Deterministico: stesso kernel → stesso output (ordinato, dedup).
Zero LLM, nessuna rete.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HEADERS = Path("/lib/modules") / os.uname().release / "build" / "include"
OUT_DEFAULT = ROOT / "CORE" / "refs"

# Regex per prototipi di funzione C (riga singola, terminata da ';').
_PROTO_RE = re.compile(
    r"^\s*(?:[A-Za-z_][\w\s\*\(\)]+?)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*;",
    re.MULTILINE,
)

# Filtri per escludere macro/static inline e falsi positivi.
_SKIP_NAMES = frozenset({
    "if", "while", "for", "switch", "return", "sizeof", "defined",
})


def _kernel_version() -> str:
    try:
        return os.uname().release
    except Exception:
        return "unknown"


def _header_files(headers_dir: Path, subsystem: str | None) -> list[Path]:
    out = []
    headers_dir = headers_dir.resolve()  # segue i symlink (es. /lib/modules/.../build)
    if not headers_dir.is_dir():
        return out
    for root, _dirs, files in os.walk(headers_dir, followlinks=True):
        for fn in files:
            if not fn.endswith(".h"):
                continue
            p = Path(root) / fn
            if subsystem and subsystem.lower() not in str(p).lower():
                continue
            out.append(p)
    return sorted(set(out))


def _extract_prototypes(path: Path) -> set[str]:
    """Estrae prototipi di funzione da un header C."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    # Rimuovi commenti /* ... */ (multilinea) per evitare falsi positivi.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    found = set()
    for m in _PROTO_RE.finditer(text):
        name = m.group(1)
        if name in _SKIP_NAMES:
            continue
        # Scarta se contiene spazi (non è un identificatore pulito).
        if " " in name:
            continue
        found.add(name)
    return found


def generate(subsystem: str | None = None, headers_dir: Path = DEFAULT_HEADERS,
             max_items: int = 2000) -> tuple[str, str]:
    """Genera il testo del ref e la versione kernel."""
    version = _kernel_version()
    files = _header_files(headers_dir, subsystem)
    names: set[str] = set()
    for f in files:
        names |= _extract_prototypes(f)
    names = sorted(n for n in names if n.isidentifier())
    names = names[:max_items]

    title = f"Linux Kernel API Ref — {version}"
    if subsystem:
        title += f" (sottosistema: {subsystem})"

    lines = [
        f"# {title}",
        "",
        "Generato da tools/extract_kernel_refs.py (deterministico, zero LLM).",
        f"Kernel: {version} | Header: {headers_dir}",
        f"File analizzati: {len(files)} | Simbodo estratti: {len(names)}",
        "",
        "## API (prototipi estratti)",
        "",
    ]
    for n in names:
        lines.append(f"- `{n}`")
    return "\n".join(lines) + "\n", version


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Estrae ref API dal kernel Linux (header C).")
    parser.add_argument("--subsystem", default=None,
                        help="Filtra per sottosistema (es. i2c, gpio, platform).")
    parser.add_argument("--headers", default=str(DEFAULT_HEADERS),
                        help="Cartella include del kernel.")
    parser.add_argument("--out", default=str(OUT_DEFAULT),
                        help="Cartella di output.")
    parser.add_argument("--max", type=int, default=2000,
                        help="Max simbodo da includere.")
    args = parser.parse_args(argv)

    text, version = generate(args.subsystem, Path(args.headers), args.max)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.subsystem}" if args.subsystem else ""
    out_path = out_dir / f"linux_kernel_{version}{suffix}.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"scritto {out_path} ({len(text)} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
