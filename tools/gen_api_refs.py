#!/usr/bin/env python3
"""Genera CORE/refs/<pkg>_<version>.md — ref API da un pacchetto installato.

Uso:
    .venv/bin/python tools/gen_api_refs.py <module> [--out DIR] [--max 200]

Deterministico: stesso pacchetto/versione → stesso output (ordinato).
Zero LLM.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "CORE" / "refs"


def _public_names(mod) -> list[str]:
    return sorted(n for n in dir(mod) if not n.startswith("_"))


def generate(module_name: str, max_items: int = 200) -> str:
    mod = importlib.import_module(module_name)
    version = getattr(mod, "__version__", "unknown")
    lines = [
        f"# API Ref — {module_name} (versione {version})",
        "",
        "Generato da tools/gen_api_refs.py (deterministico, zero LLM).",
        "",
        "## Simbodo pubblici",
        "",
    ]
    names = _public_names(mod)
    for name in names[:max_items]:
        obj = getattr(mod, name, None)
        try:
            sig = inspect.signature(obj)
            lines.append(f"- `{name}{sig}`")
        except (TypeError, ValueError):
            lines.append(f"- `{name}`")
        doc = inspect.getdoc(obj)
        if doc:
            lines.append(f"  - {doc.splitlines()[0][:120]}")
    if len(names) > max_items:
        lines.append(f"\n... altri {len(names) - max_items} simbodo (troncato).")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Genera ref API da un pacchetto.")
    parser.add_argument("module", help="Nome del modulo (es. json, pathlib).")
    parser.add_argument("--out", default=str(OUT_DEFAULT),
                        help="Cartella di output (default: CORE/refs).")
    parser.add_argument("--max", type=int, default=200,
                        help="Max simbodo da includere.")
    args = parser.parse_args(argv)

    text = generate(args.module, args.max)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    mod = importlib.import_module(args.module)
    version = getattr(mod, "__version__", "unknown")
    safe = args.module.replace(".", "_")
    out_path = out_dir / f"{safe}_{version}.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"scritto {out_path} ({len(text)} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
