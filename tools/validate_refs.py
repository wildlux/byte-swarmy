#!/usr/bin/env python3
"""validate_refs.py — valida i cheat sheet in GUI/refs/ (P2-5).

Per ogni file .md in GUI/refs/:
- legge il modulo target dall'intestazione `# Modulo: CORE.xxx`
  (fallback: nome del file senza suffisso _api);
- estrae i simbodi citati in backtick (es. `TaskQueue.add()`);
- verifica che esistano davvero nel modulo (risoluzione attributo chain);
- confronta le firme dichiarate con `# Firma: `foo(a, b=1)`` (nomi e ordine
  dei parametri via inspect.signature);
- confronta `# Versione: pkg==x.y` con la versione installata;
- segnala simbodi, firme o versioni non corrispondenti (allucinazioni API).

Uso:
    .venv/bin/python tools/validate_refs.py            # tutto GUI/refs
    .venv/bin/python tools/validate_refs.py GUI/refs/x.md
    .venv/bin/python tools/validate_refs.py --json
Exit: 0 se tutti validi, 1 se almeno un simbodo inesistente.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
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
VERSION_RE = re.compile(r"^#\s*(?:Versione|Version):\s*([^\s]+)", re.M | re.I)
SIG_RE = re.compile(
    r"^#\s*Firma:\s*`([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\(([^`]*)\)`",
    re.M,
)
_BUILTIN_SKIP = {"str", "int", "bool", "float", "list", "tuple", "dict",
                 "set", "frozenset", "bytes", "bytearray", "object", "type",
                 "None", "True", "False", "Path", "Optional", "Sequence",
                 "Iterable", "Mapping", "Callable", "Any"}


def installed_version(package: str, mod=None) -> str | None:
    """Versione installata di `package` (metadata, poi `__version__`)."""
    try:
        from importlib.metadata import version
        found = version(package)
        if found:
            return str(found)
    except Exception:
        pass
    found = getattr(mod, "__version__", None) if mod is not None else None
    return str(found) if found else None


def resolve_symbol(base, dotted: str):
    """Risolve `a.b.c` partendo da `base`; ritorna None se manca."""
    cur = base
    for part in dotted.split("."):
        if not hasattr(cur, part):
            return None
        cur = getattr(cur, part)
    return cur


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


def _check_signatures(report: dict, bases: list, declared: list) -> None:
    """Confronta nomi/ordine dei parametri con inspect.signature."""
    for sym, args in declared:
        obj = None
        for base in bases:
            obj = resolve_symbol(base, sym)
            if obj is not None:
                break
        if obj is None:
            if sym not in report["missing"]:
                report["missing"].append(sym)
            continue
        report["signatures_checked"].append(sym)
        try:
            actual = [p.name for p in inspect.signature(obj).parameters.values()]
        except (TypeError, ValueError):
            report["signature_mismatch"].append(
                f"{sym}: firma non introspettabile")
            continue
        wanted = [part.strip().split("=", 1)[0].lstrip("*").strip()
                  for part in args.split(",") if part.strip()]
        if wanted != actual:
            report["signature_mismatch"].append(
                f"{sym}: dichiarata {wanted}, installata {actual}")


def _check_version(report: dict, declared: str | None, mod) -> None:
    """Confronta `# Versione: pkg==x.y` con il pacchetto installato."""
    if not declared:
        return
    package, _, wanted = declared.partition("==")
    wanted = wanted or declared
    actual = installed_version(package, mod)
    report["installed_version"] = actual
    if actual is None:
        report["version_unverified"].append(
            f"{package}: versione installata non rilevata")
    elif actual != wanted:
        report["version_mismatch"].append(
            f"{package}: ref {wanted} != installato {actual}")


def check_ref(path: Path) -> dict:
    mod, ns_name = resolve_module(path)
    text = path.read_text(encoding="utf-8")
    version_match = VERSION_RE.search(text)
    declared_version = version_match.group(1).strip() if version_match else None
    declared_signatures = [(sym.strip(), args.strip())
                           for sym, args in SIG_RE.findall(text)]
    symbols = set()
    for m in re.finditer(r"`([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)*)\s*(\(\))?", text):
        tok, called = m.group(1), bool(m.group(2))
        if called or tok[:1].isupper():
            symbols.add(tok)
    checked, missing = [], []
    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)
    report = {
        "path": rel,
        "module": (getattr(mod, "__name__", None)
                   if mod not in (None, "external") else mod),
        "declared_version": declared_version, "installed_version": None,
        "version_mismatch": [], "version_unverified": [],
        "signatures_checked": [], "signature_mismatch": [],
        "checked": checked, "missing": missing, "ok": True,
    }
    if mod == "external":
        return report
    if mod is None:
        missing.append("<modulo non importabile>")
        report["ok"] = False
        return report

    # Valido se si risolve nel modulo O nel namespace opzionale.
    bases = [mod]
    if ns_name is not None and hasattr(mod, ns_name):
        bases.append(getattr(mod, ns_name))
    for sym in sorted(symbols):
        if sym.split(".")[0] in _BUILTIN_SKIP:
            continue
        checked.append(sym)
        if not any(resolve_symbol(base, sym) is not None for base in bases):
            missing.append(sym)
    _check_signatures(report, bases, declared_signatures)
    _check_version(report, declared_version, mod)
    report["ok"] = not (missing or report["version_mismatch"]
                        or report["signature_mismatch"])
    return report


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
                  f"{len(r['checked'])} simbodo, "
                  f"{len(r['signatures_checked'])} firme, "
                  f"{len(r['missing'])} mancanti")
            for m in r["missing"]:
                print(f"    - simbolo: {m}")
            for m in r["signature_mismatch"]:
                print(f"    - firma: {m}")
            for m in r["version_mismatch"]:
                print(f"    - versione: {m}")
            for m in r["version_unverified"]:
                print(f"    ? {m}")
        total_bad = sum(len(r["missing"]) + len(r["signature_mismatch"])
                        + len(r["version_mismatch"]) for r in reports)
        print(f"\nTotale: {len(reports)} ref, {total_bad} discrepanze")

    return 1 if has_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
