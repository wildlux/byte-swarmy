#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Piano SLOT deterministico da un task (SLOT-3 / P2-3).

Uso:
    .venv/bin/python tools/slot_plan.py --task "finestra con titolo"
    .venv/bin/python tools/slot_plan.py --task "..." --json --out PIANO.md

Nessun LLM, rete o file di progetto scritti (a meno di --out).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.slot_planner import plan_slots  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Planner deterministico a slot")
    parser.add_argument("--task", required=True, help="task dichiarativo")
    parser.add_argument("--json", action="store_true", help="output JSON")
    parser.add_argument("--out", type=Path, help="scrive il piano qui")
    args = parser.parse_args(argv)

    plan = plan_slots(args.task)
    text = (json.dumps(plan.to_dict(), indent=2, ensure_ascii=False)
            if args.json else plan.to_markdown())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Piano scritto: {args.out}")
    else:
        print(text)
    if plan.rejected:
        print(f"RIFIUTATO: {plan.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
