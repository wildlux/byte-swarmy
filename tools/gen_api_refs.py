#!/usr/bin/env python3
r"""Genera ref API validabili da un pacchetto installato (Cycle 97 / E2).

Uso:
    .venv/bin/python tools/gen_api_refs.py <module> [--out DIR] [--max 200]

Deterministico: stesso pacchetto/versione → stesso output (ordinato).
Zero LLM, zero rete.

Dal Cycle 97 l'output è compatibile con `tools/validate_refs.py`:
  - `# Modulo: <modulo>` (risoluzione dei simboli);
  - `# Versione: <pkg==ver>` solo se la versione è nota;
  - `# Firma: \`nome(a, b)\`` per ogni callabile introspettabile.
Le firme usano solo i NOMI dei parametri: `validate_refs` confronta nomi e
ordine via `inspect.signature`, e così si evitano virgole annidate nei
valori di default. Il nome del file è `<modulo>_api.md` (senza timestamp).
"""
from __future__ import annotations

import argparse
import importlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "CORE" / "refs"


def _public_names(mod) -> list[str]:
    return sorted(n for n in dir(mod) if not n.startswith("_"))


def _param_names(obj) -> list[str] | None:
    """Nomi dei parametri in ordine, oppure None se non introspettabile."""
    try:
        return [p.name for p in inspect.signature(obj).parameters.values()]
    except (TypeError, ValueError):
        return None


def installed_version(module_name: str, mod) -> str | None:
    """Versione installata da metadata, poi __version__ (stdlib: None)."""
    try:
        from importlib.metadata import version
        found = version(module_name)
        if found:
            return str(found)
    except Exception:
        pass
    found = getattr(mod, "__version__", None)
    return str(found) if found else None


def generate(module_name: str, max_items: int = 200) -> str:
    mod = importlib.import_module(module_name)
    version = installed_version(module_name, mod)
    lines = [
        f"# Modulo: {module_name}",
        f"# API Ref — {module_name}"
        + (f" (versione {version})" if version else " (stdlib/versione non nota)"),
        "",
        "Generato da tools/gen_api_refs.py (deterministico, zero LLM).",
        "Validabile con: .venv/bin/python tools/validate_refs.py <questo file>",
        "",
        "## Simboli pubblici",
        "",
    ]
    if version:
        lines.insert(2, f"# Versione: {module_name}=={version}")

    names = _public_names(mod)
    signatures: list[str] = []
    for name in names[:max_items]:
        obj = getattr(mod, name, None)
        params = _param_names(obj)
        try:
            sig = inspect.signature(obj)
            lines.append(f"- `{name}{sig}`")
        except (TypeError, ValueError):
            lines.append(f"- `{name}`")
        if params is not None:
            signatures.append(
                f"# Firma: `{name}({', '.join(params)})`")
        doc = inspect.getdoc(obj)
        if doc:
            lines.append(f"  - {doc.splitlines()[0][:120]}")
    if len(names) > max_items:
        lines.append(f"\n... altri {len(names) - max_items} simboli (troncato).")
    if signatures:
        lines += ["", "## Firme verificate via inspect", ""] + signatures
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Genera ref API da un pacchetto.")
    parser.add_argument("module", help="Nome del modulo (es. json, pathlib).")
    parser.add_argument("--out", default=str(OUT_DEFAULT),
                        help="Cartella di output (default: CORE/refs).")
    parser.add_argument("--max", type=int, default=200,
                        help="Max simboli da includere.")
    args = parser.parse_args(argv)

    text = generate(args.module, args.max)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = args.module.replace(".", "_")
    out_path = out_dir / f"{safe}_api.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"scritto {out_path} ({len(text)} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
