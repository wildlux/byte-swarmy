#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""E2 — eval deterministico di fedeltà API (zero LLM, zero rete).

Per ogni caso: si estraggono dall'AST gli usi `modulo.simbolo` e si verifica
ogni simbolo con `api_lookup(modulo, simbolo, strict=True)` — lo STESSO gate
usato dal worker. Un simbolo non verificabile è un'allucinazione API e
viene conteggiato come `undefined`.

Inoltre valida i ref generati per gli stessi moduli con `validate_refs.py`
(simboli, firme e versioni). Il report è deterministico: stesso input →
stesso testo.

Uso:
    .venv/bin/python tools/api_fidelity_eval.py
    .venv/bin/python tools/api_fidelity_eval.py --json
    .venv/bin/python tools/api_fidelity_eval.py --out RAG/DOCS/API_FIDELITY_REPORT.md

Exit: 0 se 0 simboli indefiniti e ref validi, 1 altrimenti.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_refs as vr  # noqa: E402
from CORE.tools import ToolSet  # noqa: E402

REFS_DIR = ROOT / "GUI" / "refs"

# Due librerie FUORI dai cheat sheet storici (GUI/refs/*.md pre-E2).
EVAL_CASES = [
    {
        "id": "json-01",
        "module": "json",
        "code": (
            "import json\n"
            "payload = json.dumps({'ok': True}, sort_keys=True)\n"
            "data = json.loads(payload)\n"
            "encoder = json.JSONEncoder(indent=2)\n"
        ),
    },
    {
        "id": "csv-01",
        "module": "csv",
        "code": (
            "import csv\n"
            "rows = csv.reader(['a,b'])\n"
            "writer = csv.DictWriter([], fieldnames=['a', 'b'], "
            "quoting=csv.QUOTE_MINIMAL)\n"
            "dialect = csv.excel()\n"
        ),
    },
]


def symbol_usages(code: str, module: str) -> list[str]:
    """Simboli `module.nome` usati nel codice, ordinati e senza duplicati."""
    tree = ast.parse(code)
    return sorted({n.attr for n in ast.walk(tree)
                   if isinstance(n, ast.Attribute)
                   and isinstance(n.value, ast.Name)
                   and n.value.id == module})


def _lookup(module: str, symbol: str) -> str:
    return ToolSet.api_lookup(SimpleNamespace(project_root=ROOT),
                              module, symbol, True)


def evaluate(cases=None, refs: bool = True) -> dict:
    """Valuta i casi e (opzionalmente) i ref generati per i loro moduli."""
    cases = list(EVAL_CASES if cases is None else cases)
    results = []
    for case in cases:
        module, cid = case["module"], case["id"]
        try:
            symbols = symbol_usages(case["code"], module)
            error = ""
        except SyntaxError as e:
            symbols, error = [], f"codice non valido: {e.msg}"
        verified, undefined = [], []
        for sym in symbols:
            out = _lookup(module, sym)
            (verified if "VERIFICATO via inspect" in out else undefined).append(
                sym if not out.startswith("ERROR") else f"{sym}: {out[:100]}")
        results.append({
            "id": cid, "module": module, "symbols": symbols,
            "verified": verified, "undefined": undefined, "error": error,
            "ok": bool(symbols) and not undefined and not error,
        })

    ref_reports = []
    if refs:
        for module in sorted({c["module"] for c in cases}):
            path = REFS_DIR / f"{module}_api.md"
            if not path.exists():
                ref_reports.append({
                    "module": module, "path": str(path.relative_to(ROOT)),
                    "ok": False, "signatures": 0, "missing": ["ref assente"],
                })
                continue
            report = vr.check_ref(path)
            ref_reports.append({
                "module": module,
                "path": str(path.relative_to(ROOT)),
                "ok": bool(report["ok"] and report["signatures_checked"]),
                "signatures": len(report["signatures_checked"]),
                "missing": report["missing"] + report["signature_mismatch"],
            })

    undefined_total = sum(len(r["undefined"]) for r in results)
    bad_refs = sum(1 for r in ref_reports if not r["ok"])
    return {
        "cases": results,
        "refs": ref_reports,
        "undefined_total": undefined_total,
        "bad_refs": bad_refs,
        "ok": (undefined_total == 0 and bad_refs == 0
               and all(r["ok"] for r in results)),
    }


def markdown(report: dict) -> str:
    lines = [
        "# 🔬 API Fidelity Eval (E2)",
        "",
        f"**Verdetto**: {'✅ PASS' if report['ok'] else '❌ FAIL'} — "
        f"{report['undefined_total']} simboli indefiniti, "
        f"{report['bad_refs']} ref non validi. Zero LLM, zero rete.",
        "",
        "| Caso | Modulo | Simboli | Verificati | Indefiniti | Esito |",
        "|---|---|---:|---:|---|---|",
    ]
    for c in report["cases"]:
        detail = ", ".join(c["symbols"]) or c["error"] or "—"
        undef = ", ".join(c["undefined"]) or "0"
        lines.append(
            f"| {c['id']} | `{c['module']}` | {len(c['symbols'])} | "
            f"{len(c['verified'])} | {undef} | "
            f"{'✅' if c['ok'] else '❌'} |")
        lines.append(f"<!-- {c['id']}: {detail} -->")
    lines += ["", "| Ref | Firme | Mancanti | Esito |", "|---|---:|---|---|"]
    for r in report["refs"]:
        lines.append(
            f"| `{r['path']}` | {r['signatures']} | "
            f"{', '.join(r['missing']) or '0'} | {'✅' if r['ok'] else '❌'} |")
    lines += [
        "",
        "Gate: `api_lookup(strict=True)` è lo stesso usato dal worker; "
        "i ref sono generati da `tools/gen_api_refs.py` e validati da "
        "`tools/validate_refs.py`.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="stampa solo JSON")
    ap.add_argument("--out", default=None, help="scrive report Markdown qui")
    args = ap.parse_args(argv)

    report = evaluate()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(report), encoding="utf-8")
        print(f"Report scritto: {out} ({'PASS' if report['ok'] else 'FAIL'})")
    else:
        sys.stdout.write(markdown(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
