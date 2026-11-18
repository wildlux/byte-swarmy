#!/usr/bin/env python3
"""run_eval.py — eval suite interna (Fase A, mini-SWE-bench).

Carica i casi da evals/cases.json e produce un report per asse e per
granularità. Due modalità:

  --dry-run  (default): valida i casi e stampa il riepilogo (zero LLM).
  --live     : esegue i casi col worker (richiede ventole al max, ≤60°C).

Uso:
    .venv/bin/python tools/run_eval.py                # dry-run
    .venv/bin/python tools/run_eval.py --json         # dry-run JSON
    .venv/bin/python tools/run_eval.py --live         # richiede LLM

Ogni caso ha: id, title, description, axis (asse radar), granularity
(small/medium/large), refs, expected_marker o expected_fail/expected_clarify.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "evals" / "cases.json"
VALID_AXES = {
    "Task GUI (creazione)", "Modifiche minime", "Refactoring mecc.",
    "Gate / verifica", "Fedeltà API", "Chiarimenti ambigui",
    "Architettura", "Memoria / contesto",
}
VALID_GRAN = {"small", "medium", "large"}


def load_cases(path: Path = CASES) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cases.json deve essere una lista")
    return data


def validate_cases(cases: list[dict]) -> list[str]:
    errors = []
    ids = set()
    for i, c in enumerate(cases):
        for key in ("id", "title", "description", "axis", "granularity"):
            if key not in c:
                errors.append(f"caso #{i}: manca '{key}'")
        if c.get("id") in ids:
            errors.append(f"caso #{i}: id duplicato '{c['id']}'")
        ids.add(c.get("id"))
        if c.get("axis") not in VALID_AXES:
            errors.append(f"{c.get('id')}: axis sconosciuto '{c.get('axis')}'")
        if c.get("granularity") not in VALID_GRAN:
            errors.append(f"{c.get('id')}: granularity sconosciuta")
    if len(cases) < 12:
        errors.append(f"servono >=12 casi, trovati {len(cases)}")
    return errors


def summarize(cases: list[dict]) -> dict:
    by_axis = defaultdict(int)
    by_gran = defaultdict(int)
    for c in cases:
        by_axis[c["axis"]] += 1
        by_gran[c["granularity"]] += 1
    return {
        "total": len(cases),
        "by_axis": dict(by_axis),
        "by_granularity": dict(by_gran),
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true",
                        help="esegue i casi col worker (richiede LLM)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cases = load_cases()
    errors = validate_cases(cases)

    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors,
                          "summary": summarize(cases)}, indent=2,
                         ensure_ascii=False))
    else:
        print(f"Eval suite: {len(cases)} casi")
        if errors:
            print("ERRORI DI VALIDAZIONE:")
            for e in errors:
                print(f"  - {e}")
        else:
            print("Validazione OK.")
        s = summarize(cases)
        print("\nPer asse:")
        for axis, n in sorted(s["by_axis"].items()):
            print(f"  {axis}: {n}")
        print("\nPer granularità:")
        for g, n in sorted(s["by_granularity"].items()):
            print(f"  {g}: {n}")

    if args.live:
        print("\n--live non ancora implementato: richiede ventole al max e "
              "orchestratore in pausa. Vedi DOCS/ARCHITETTURA_SLOT.md Fase A.",
              file=sys.stderr)
        return 2

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
