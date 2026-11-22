#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SLOT-4 — prompt per-slot, senza LLM e senza toccare il motore.

Trasforma un `SlotPlan` (già prodotto da `CORE/slot_planner.py`) in **uno
prompt per chiamata**: ogni prompt contiene solo le refs dello slot corrente,
l'anchor reale del template e regole di output piccolo. I piani rifiutati
non generano prompt: il builder è fail-closed come il planner.

Nessun modello, rete o scrittura di progetto (solo `--out` opzionale).

Uso:
    .venv/bin/python tools/slot_prompt.py --task "finestra con titolo"
    .venv/bin/python tools/slot_prompt.py --task "..." --json
    .venv/bin/python tools/slot_prompt.py --task "..." --out DOCS/SLOT4_PROMPTS.md

Il benchmark di SLOT-4 (3 task reali con pass@1) resta 🔒 termico: qui si
blocca solo la struttura dei prompt, non si misura alcuna qualità del modello.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.slot_planner import SlotPlan, plan_slots  # noqa: E402

MAX_OUTPUT_LINES = 40


def _refs_block(refs: tuple[str, ...]) -> str:
    if not refs:
        return "- (nessuna ref aggiuntiva; solo i nomi impliciti del tipo)"
    return "\n".join(f"- `{ref}`" for ref in refs)


def build_slot_prompt(plan: SlotPlan, index: int) -> str:
    """Uno slot per chiamata: refs e anchor solo dello slot richiesto."""
    if plan.rejected or not plan.ok:
        raise ValueError(f"piano rifiutato: {plan.reason}")
    if not 0 <= index < len(plan.slots):
        raise ValueError(f"indice slot {index} fuori range (0..{len(plan.slots)-1})")
    slot = plan.slots[index]
    lines = [
        f"# SLOT {index + 1}/{len(plan.slots)} — {slot.kind}",
        "",
        f"Task: {plan.task}",
        f"Template: `{plan.template}`",
        "",
        "## REF DI QUESTO SLOT SOLO",
        _refs_block(slot.refs),
        "",
        "## ISTRUZIONE",
        slot.instruction,
        "",
        "## ANCHOR (non modificarlo)",
        f"`# SLOT: {slot.marker}`",
        "",
        "## REGOLE OUTPUT",
        f"- Rispondi SOLO con il codice di questo slot ({slot.kind}).",
        f"- Massimo {MAX_OUTPUT_LINES} righe, nessuna spiegazione.",
        "- Usa SOLO le REF sopra e i nomi impliciti del tipo di slot.",
        "- Non riscrivere gli altri slot né aggiungere API non dichiarate.",
        "- Le ref degli altri slot non sono incluse in questo prompt.",
    ]
    return "\n".join(lines) + "\n"


def build_all_prompts(plan: SlotPlan) -> list[str]:
    return [build_slot_prompt(plan, i) for i in range(len(plan.slots))]


def report(plan: SlotPlan) -> dict:
    return {
        "task": plan.task,
        "template": plan.template,
        "rejected": plan.rejected,
        "reason": plan.reason,
        "slot_count": len(plan.slots),
        "prompts": [
            {"index": i, "kind": s.kind, "anchor": s.anchor,
             "refs": list(s.refs), "text": build_slot_prompt(plan, i)}
            for i, s in enumerate(plan.slots)
        ],
    }


def markdown(data: dict) -> str:
    lines = [
        "# SLOT-4 — prompt per slot",
        "",
        f"Task: {data['task']}",
        f"Template: `{data['template']}` — slot: {data['slot_count']}",
        "",
        "> Struttura deterministica dei prompt. **Nessun modello è stato "
        "chiamato**: il benchmark con 3 task reali resta 🔒 termico.",
        "",
    ]
    for item in data["prompts"]:
        lines += [f"## Prompt {item['index'] + 1} — `{item['kind']}`", "",
                  "```text", item["text"].rstrip(), "```", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True, help="task dichiarativo")
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", type=Path, help="scrive i prompt qui")
    args = p.parse_args(argv)

    plan = plan_slots(args.task)
    if not plan.ok:
        print(f"RIFIUTATO: {plan.reason}", file=sys.stderr)
        return 1
    data = report(plan)
    text = json.dumps(data, indent=2, ensure_ascii=False) if args.json \
        else markdown(data)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Prompt scritti: {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
