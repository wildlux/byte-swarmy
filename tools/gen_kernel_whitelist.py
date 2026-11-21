#!/usr/bin/env python3
"""Genera CORE/refs/linux_kernel_<ver>_whitelist.json — whitelist API kernel.

Uso:
    .venv/bin/python tools/gen_kernel_whitelist.py [--subsystem i2c] [--out DIR]

Deterministico: stesso kernel → stesso output (ordinato).
Zero LLM, nessuna rete.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


DEFAULT_HEADERS = Path("/lib/modules") / os.uname().release / "build" / "include"
OUT_DEFAULT = ROOT / "CORE" / "refs"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera whitelist API kernel da header.")
    parser.add_argument("--subsystem", default=None,
                        help="Filtra per sottosistema (es. i2c, gpio).")
    parser.add_argument("--headers", default=str(DEFAULT_HEADERS),
                        help="Cartella include del kernel.")
    parser.add_argument("--out", default=str(OUT_DEFAULT),
                        help="Cartella di output.")
    args = parser.parse_args(argv)

    from tools.extract_kernel_refs import _header_files
    headers = Path(args.headers)
    files = _header_files(headers, args.subsystem)
    names = set()
    import re
    proto_re = re.compile(
        r"^\s*(?:[A-Za-z_][\w\s\*\(\)]+?)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*;",
        re.MULTILINE)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for m in proto_re.finditer(text):
            name = m.group(1)
            if " " not in name and name.isidentifier():
                names.add(name)

    version = os.uname().release
    suffix = f"_{args.subsystem}" if args.subsystem else ""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"linux_kernel_{version}{suffix}_whitelist.json"
    path.write_text(
        __import__("json").dumps(sorted(names), indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"scritto {path} ({len(names)} simbodo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
