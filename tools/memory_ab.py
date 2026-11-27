#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E4 — harness A/B memoria/contesto: 10 task congelati, con/senza contesto.

PREPARAZIONE, NON ESECUZIONE LIVE. Il modulo non importa client LLM e non
apre connessioni: con `--dry-run` usa solver/retriever finti per validare
l'harness. Un solver reale può essere passato solo a `run_ab(..., live=True)`
dopo la verifica delle ventole (file `data/state/fan_verified.json` con
`fan_rpm > 0` e `temp_c <= 60`). Fino ad allora il live resta 🔒 bloccato.

Uso:
    .venv/bin/python tools/memory_ab.py --dry-run
    .venv/bin/python tools/memory_ab.py --dry-run --out RAG/DOCS/MEMORY_AB_REPORT.md
    .venv/bin/python tools/memory_ab.py --json

Soglia GO/NO-GO dichiarata (PRIMA di qualsiasi run live):
    with >= 0.60  E  delta >= 0.20  → GO (mantieni contesto)
    delta <= 0                    → NO-GO (riduci/disattiva)
    altrimenti                    → INCONCLUSIVE (più campioni)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAX_TEMP_C = 60.0
MIN_WITH_RATE = 0.60
MIN_DELTA = 0.20
FAN_FILE = ROOT / "data" / "state" / "fan_verified.json"

# Task set CONGELATO: modificare una riga richiede di aggiornare TASK_SET_ID
# (il test test_task_set_congelato lo verifica). Nessun dato live o personale.
TASK_SET = (
    {"id": "mem-01", "prompt": "Spiega la differenza tra list e tuple in Python.",
     "expected": "mutabilita", "aided": True},
    {"id": "mem-02", "prompt": "Come si chiude un QThread PyQt6 senza abort?",
     "expected": "quit", "aided": True},
    {"id": "mem-03", "prompt": "Quale gate verifica una firma API Python?",
     "expected": "inspect", "aided": True},
    {"id": "mem-04", "prompt": "Dove sono i template GUI del progetto?",
     "expected": "GUI/refs/templates", "aided": True},
    {"id": "mem-05", "prompt": "Che cosa misura il refactor guard?",
     "expected": "comportamento", "aided": True},
    {"id": "mem-06", "prompt": "Come si rigenera il grafico miglioramenti?",
     "expected": "gen_grafici", "aided": True},
    {"id": "mem-07", "prompt": "Quale stato NON vale verified?",
     "expected": "not_tested", "aided": True},
    {"id": "mem-08", "prompt": "Come si chiama il corpus di feedback?",
     "expected": "feedback_corpus", "aided": True},
    {"id": "mem-09", "prompt": "Quale comando lancia i test offscreen?",
     "expected": "pytest", "aided": False},
    {"id": "mem-10", "prompt": "Che temperatura massima vale per il LLM locale?",
     "expected": "60", "aided": False},
)
TASK_SET_ID = "5e6051bfc33d"


class FakeRetriever:
    """Contesto deterministico: la risposta attesa solo per i task `aided`."""

    def __init__(self, tasks=TASK_SET):
        self.tasks = {t["id"]: t for t in tasks}

    def context_for(self, task: dict) -> str:
        t = self.tasks.get(task["id"], task)
        if not t.get("aided"):
            return "Nessun task simile trovato."
        return (f"--- task simile (score 0.90) ---\n"
                f"RISPOSTA: {t['expected']}")


def fake_solver(prompt: str, context: str) -> str:
    """Solver finto: usa il contesto se contiene una RISPOSTA esplicita."""
    if "RISPOSTA:" in context:
        return context.split("RISPOSTA:", 1)[1].strip().splitlines()[0]
    return "risposta generica senza contesto"


def check_answer(answer: str, task: dict) -> bool:
    return task["expected"].lower() in str(answer).lower()


def thermal_gate_ok(live: bool) -> bool:
    """Vero per il dry-run; per il live richiede ventole verificate e <=60C."""
    if not live:
        return True
    try:
        data = json.loads(FAN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    try:
        return (float(data.get("fan_rpm", 0)) > 0
                and float(data.get("temp_c", 999)) <= MAX_TEMP_C)
    except (TypeError, ValueError):
        return False


def verdict(with_rate: float, without_rate: float) -> str:
    delta = round(with_rate - without_rate, 4)  # evita 0.6-0.4 = 0.1999...
    if with_rate >= MIN_WITH_RATE and delta >= MIN_DELTA:
        return "GO"
    if delta <= 0:
        return "NO-GO"
    return "INCONCLUSIVE"


@dataclass(frozen=True)
class Arm:
    name: str
    passed: int
    total: int

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def run_ab(solver=fake_solver, retriever=None, tasks=TASK_SET,
           live: bool = False) -> dict:
    """Esegue i 10 task in due bracci. Nessun LLM nel default (dry-run)."""
    if live and not thermal_gate_ok(True):
        raise RuntimeError(
            "A/B live 🔒 bloccato: verificare ventole (fan_rpm>0) e "
            f"temperatura <= {MAX_TEMP_C:.0f}C in {FAN_FILE}")
    retriever = retriever or FakeRetriever()
    tasks = list(tasks)
    out = {"live": live, "task_set_id": TASK_SET_ID, "tasks": [], "arms": {}}
    for arm_name in ("with_context", "without_context"):
        passed = 0
        for task in tasks:
            context = (retriever.context_for(task)
                       if arm_name == "with_context" else "")
            answer = solver(task["prompt"], context)
            ok = check_answer(answer, task)
            passed += int(ok)
            out["tasks"].append({
                "id": task["id"], "arm": arm_name,
                "context_chars": len(context), "pass": ok,
            })
        out["arms"][arm_name] = Arm(arm_name, passed, len(tasks))
    with_rate = out["arms"]["with_context"].rate
    without_rate = out["arms"]["without_context"].rate
    out["delta"] = round(with_rate - without_rate, 4)
    out["verdict"] = verdict(with_rate, without_rate)
    return out


def to_dict(result: dict) -> dict:
    return {
        "live": result["live"],
        "task_set_id": result["task_set_id"],
        "n_tasks": len(TASK_SET),
        "arms": {k: {"passed": a.passed, "total": a.total,
                     "rate": round(a.rate, 4)}
                 for k, a in result["arms"].items()},
        "delta": result["delta"],
        "verdict": result["verdict"],
        "tasks": result["tasks"],
        "thermal_gate": (
            "N/A (dry-run)" if not result["live"]
            else "OK" if thermal_gate_ok(True) else "BLOCKED"),
    }


def markdown(result: dict) -> str:
    d = to_dict(result)
    mode = "LIVE" if d["live"] else "DRY-RUN (solver finto — NON è un verdetto reale)"
    lines = [
        "# 🧠 A/B memoria / contesto (E4)",
        "",
        f"**Modalità**: {mode} — task set `{d['task_set_id']}` "
        f"({d['n_tasks']} task congelati).",
        "",
        f"**Gate termico**: {d['thermal_gate']} — live richiede "
        f"`fan_rpm > 0` e `temp_c <= {MAX_TEMP_C:.0f}` in `{FAN_FILE.relative_to(ROOT)}`.",
        "",
        "| Soglia (fissata prima del live) | Valore |",
        "|---|---:|",
        f"| with-context minimo | {MIN_WITH_RATE:.2f} |",
        f"| delta minimo (with − without) | {MIN_DELTA:.2f} |",
        f"| GO / NO-GO / INCONCLUSIVE | {verdict(MIN_WITH_RATE, MIN_WITH_RATE - MIN_DELTA)} / "
        f"{verdict(0.4, 0.5)} / {verdict(0.4, 0.3)} |",
        "",
        "| Braccio | Passati | Totale | Tasso |",
        "|---|---:|---:|---:|",
    ]
    for name, a in d["arms"].items():
        lines.append(f"| `{name}` | {a['passed']} | {a['total']} | {a['rate']:.2f} |")
    lines += [
        "",
        f"Delta: **{d['delta']:.2f}** — verdetto "
        f"{'harness (simulato)' if not d['live'] else 'live'}: "
        f"**{d['verdict']}**.",
        "",
        "| Task | Braccio | Contesto (char) | Esito |",
        "|---|---|---:|---|",
    ]
    for t in d["tasks"]:
        lines.append(
            f"| `{t['id']}` | `{t['arm']}` | {t['context_chars']} | "
            f"{'✅' if t['pass'] else '❌'} |")
    lines += [
        "",
        "⚠️ Il dry-run valida solo l'harness: il verdetto sull'impatto reale "
        "della memoria arriva da 10 task con LLM live, 🔒 bloccato finché "
        "le ventole non sono verificate. Non usare questi numeri per alzare "
        "l'asse Memoria/contesto del radar.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="usa solver/retriever finti (default, nessun LLM)")
    ap.add_argument("--json", action="store_true", help="stampa solo JSON")
    ap.add_argument("--out", default=None, help="scrive report Markdown qui")
    args = ap.parse_args(argv)

    try:
        result = run_ab(live=False)
    except RuntimeError as e:
        print(f"🔒 {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(to_dict(result), indent=2, ensure_ascii=False))
    elif args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(result), encoding="utf-8")
        print(f"Report scritto: {out} ({result['verdict']}, dry-run)")
    else:
        sys.stdout.write(markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
