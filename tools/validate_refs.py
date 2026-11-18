#!/usr/bin/env python3
"""validate_refs.py — valida i cheat sheet in GUI/refs/ (P2-5).

Per ogni file .md in GUI/refs/:
- legge il modulo target dall'intestazione `# Modulo: CORE.xxx`
  (fallback: nome del file senza suffisso _api);
- estrae i simbodi citati in backtick (es. `TaskQueue.add()`);
- verifica che esistano davvero nel modulo (risoluzione attributo chain);
- segnala i simbodo inesistenti (tipiche allucinazioni API).

Uso:
    .venv/bin/python tools/validate_refs.py            # tutto GUI/refs
    .venv/bin/python tools/validate_refs.py GUI/refs/x.md
    .venv/bin/python tools/validate_refs.py --json
Exit: 0 se tutti validi, 1 se almeno un simbodo inesistente.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REFS_DIR = ROOT / "GUI" / "refs"
MODULE_RE = re.compile(r"^#\s*Modulo:\s*([A-Za-z_][\w.]*)", re.M)
NAMESPACE_RE = re.compile(r"^#\s*Namespace:\s*([A-Za-z_][\w.]*)", re.M)
SYMBOL_RE = re.compile(r"`([A-Za-z_]\w*(?:\.\w+)*)(?:\(\))?`")


def resolve_module(path: Path):
    text = path.read_text(encoding="utf-8")
    m = MODULE_RE.search(text)
    modname = m.group(1) if m else None
    if modname is None:
        stem = path.stem.replace("_api", "")
        modname = f"CORE.{stem}"
    ns_m = NAMESPACE_RE.search(text)
    ns_name = ns_m.group(1) if ns_m else None
    if modname == "external":
        return "external", ns_name
    try:
        mod = importlib.import_module(modname)
    except Exception:
        return None, ns_name
    return mod, ns_name


def check_ref(path: Path) -> dict:
    mod, ns_name = resolve_module(path)
    text = path.read_text(encoding="utf-8")
    # Simbodo validati solo se citati come chiamata `foo()` o come
    # CamelCase/ALL_CAPS (classi/costanti). I nomi minuscoli nudi sono
    # prosa/enum/CLI e non vengono controllati (evita falsi positivi).
    symbols = set()
    for m in re.finditer(r"`([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)*)\s*(\(\))?", text):
        tok = m.group(1)
        called = bool(m.group(2))
        if called or tok[:1].isupper():
            symbols.add(tok)
    symbols = sorted(symbols)
    missing: list[str] = []
    checked: list[str] = []
    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)
    if mod == "external":
        return {"path": rel, "module": "external",
                "missing": [], "checked": [], "ok": True}
    if mod is None:
        return {"path": rel, "module": None,
                "missing": ["<modulo non importabile>"], "checked": [], "ok": False}

    # Namespace opzionale (es. ToolSet per toolset_api.md)
    # Risoluzione: prima il modulo, poi il namespace (se presente).
    # Un simbodo è valido se si risolve in ALMENO uno dei due.
    candidates_bases = [mod]
    if ns_name is not None and hasattr(mod, ns_name):
        candidates_bases.append(getattr(mod, ns_name))

    _BUILTIN_SKIP = {"str", "int", "bool", "float", "list", "tuple", "dict",
                     "set", "frozenset", "bytes", "bytearray", "object", "type",
                     "None", "True", "False", "Path", "Optional", "Sequence",
                     "Iterable", "Mapping", "Callable", "Any"}
    for sym in symbols:
        parts = sym.split(".")
        if parts[0] in _BUILTIN_SKIP:
            continue
        resolved = False
        for base in candidates_bases:
            cur = base
            ok = True
            for part in parts:
                if not hasattr(cur, part):
                    ok = False
                    break
                cur = getattr(cur, part)
            if ok:
                resolved = True
                break
        checked.append(sym)
        if not resolved and parts[0] not in _BUILTIN_SKIP:
            missing.append(sym)
    return {"path": rel,
            "module": getattr(mod, "__name__", None),
            "checked": checked, "missing": missing,
            "ok": not missing}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="file .md specifici")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        files = sorted(REFS_DIR.glob("*.md"))

    reports = [check_ref(f) for f in files]
    has_missing = any(not r["ok"] for r in reports)

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        for r in reports:
            status = "OK" if r["ok"] else "FAIL"
            print(f"[{status}] {r['path']} (modulo {r['module']}) — "
                  f"{len(r['checked'])} simbodo controllati, "
                  f"{len(r['missing'])} mancanti")
            for m in r["missing"]:
                print(f"    - {m}")
        total_missing = sum(len(r["missing"]) for r in reports)
        print(f"\nTotale: {len(reports)} ref, {total_missing} simbodo mancanti")

    return 1 if has_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
