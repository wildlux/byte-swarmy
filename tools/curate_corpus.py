#!/usr/bin/env python3
"""curate_corpus.py — curazione del corpus di feedback (Fase B).

Prende le triple del corpus (`CORE/feedback_corpus`) e produce la lista
curata per il training futuro (QLoRA STaR, Fase C): dedup deterministico
+ filtro "solo done" (i casi con correction sono i piu' preziosi per il
vero STaR, ma l'item di partenza chiede la curazione base).

Regola di partenza: **SOLO esempi gate-verificati**. Nel nostro flusso un
task entra nel corpus solo se ha raggiunto lo stato di done (gate test /
import-check); le righe con `verdict='corrected'` restano nel corpus per
la valutazione, ma la curatura per il futuro prende solo `done`.

Uso:
    .venv/bin/python tools/curate_corpus.py                # riepilogo task noti
    .venv/bin/python tools/curate_corpus.py --task task-...
    .venv/bin/python tools/curate_corpus.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import feedback_corpus as fc  # noqa: E402


def collect_task(task_id: str, state_dir: str | Path | None = None) -> list:
    return fc.load_task(task_id, state_dir=state_dir)


def curate(samples: list, only_done: bool = True) -> list:
    """Dedup + (opzionale) filtro done. Ordine di arrivo preservato."""
    unique = fc.dedupe(samples)
    if not only_done:
        return unique
    return [t for t in unique if t.verdict == "done"]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    task = None
    state_dir = None
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", default=None, help="task_id specifico")
    p.add_argument("--state-dir", default=None, help="dir di stato (default)")
    p.add_argument("--only-done", action="store_true", default=True,
                   help="solo esempi con verdict='done'")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    state = Path(state_dir) if state_dir else (ROOT / "state")
    task_ids = [task] if task else sorted(
        f.stem for f in (state / "feedback_corpus").glob("*.jsonl")
        if f.is_file())
    samples: list = []
    for tid in task_ids:
        samples.extend(collect_task(tid, state_dir=state))
    curated = curate(samples, only_done=args.only_done)

    report = {
        "task": task,
        "samples": len(samples),
        "curated": len(curated),
        "done": sum(1 for t in samples if t.verdict == "done"),
        "corrected": sum(1 for t in samples if t.verdict == "corrected"),
    }
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        action = f"task {task}" if task else "tutti i task noti"
        print(f"corpus {action}: {report['samples']} sample, "
              f"{report['curated']} curati (done={report['done']}, "
              f"corrected={report['corrected']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
