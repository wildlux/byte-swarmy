#!/usr/bin/env python3
"""curate_corpus.py — curazione del corpus di feedback (Fase B, A3).

Dedup deterministico + stratificazione per verdetto:

- ``done``      → esempi positivi (risposta corretta, anche dopo retry);
- ``corrected`` → **hard negatives**: il prompt correttivo spiega l'errore;
- ``failed_definitively`` → escluso (non è un esempio da imitare).

Di default la curazione include **done + corrected** in ordine interleaved
(deterministico). ``--only-done`` ripristina il comportamento storico.

Uso:
    .venv/bin/python tools/curate_corpus.py                # done + corrected
    .venv/bin/python tools/curate_corpus.py --only-done    # vecchio filtro
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

VERDICT_POSITIVE = "done"
VERDICT_HARD_NEGATIVE = "corrected"


def collect_task(task_id: str, state_dir: str | Path | None = None) -> list:
    return fc.load_task(task_id, state_dir=state_dir)


def curate(samples: list, only_done: bool = False,
           max_per_verdict: int | None = None) -> list:
    """Dedup + stratificazione `done`/`corrected`, ordine deterministico.

    `only_done=True` → solo positivi (comportamento storico).
    `max_per_verdict` → cap opzionale per classe (nessuno di default).
    """
    unique = fc.dedupe(samples)
    if only_done:
        return [t for t in unique if t.verdict == VERDICT_POSITIVE]
    positives = [t for t in unique if t.verdict == VERDICT_POSITIVE]
    negatives = [t for t in unique if t.verdict == VERDICT_HARD_NEGATIVE]
    if max_per_verdict is not None and max_per_verdict >= 0:
        positives = positives[:max_per_verdict]
        negatives = negatives[:max_per_verdict]
    out = []
    for i in range(max(len(positives), len(negatives))):
        if i < len(positives):
            out.append(positives[i])
        if i < len(negatives):
            out.append(negatives[i])
    return out


def verdict_counts(samples: list) -> dict:
    """Conteggio per verdetto, incluse le righe escluse dalla curazione."""
    counts = {v: 0 for v in sorted(fc.VALID_VERDICTS)}
    for t in samples:
        key = str(getattr(t, "verdict", ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    task = None
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", default=None, help="task_id specifico")
    p.add_argument("--state-dir", default=None, help="dir di stato (default)")
    p.add_argument("--only-done", action="store_true", default=False,
                   help="solo esempi con verdict='done' (comportamento storico)")
    p.add_argument("--max-per-verdict", type=int, default=None,
                   help="cap opzionale per classe")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    state = Path(args.state_dir) if args.state_dir else (ROOT / "state")
    task_ids = [task] if task else sorted(
        f.stem for f in (state / "feedback_corpus").glob("*.jsonl")
        if f.is_file())
    samples: list = []
    for tid in task_ids:
        samples.extend(collect_task(tid, state_dir=state))
    curated = curate(samples, only_done=args.only_done,
                     max_per_verdict=args.max_per_verdict)
    counts = verdict_counts(samples)

    report = {
        "task": task,
        "samples": len(samples),
        "curated": len(curated),
        "counts": counts,
        "done": counts.get(VERDICT_POSITIVE, 0),
        "corrected": counts.get(VERDICT_HARD_NEGATIVE, 0),
        "excluded_failed": counts.get("failed_definitively", 0),
        "only_done": args.only_done,
    }
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        action = f"task {task}" if task else "tutti i task noti"
        mode = "solo done" if args.only_done else "done + corrected (hard negatives)"
        print(f"corpus {action}: {report['samples']} sample, "
              f"{report['curated']} curati ({mode}; "
              f"done={report['done']}, corrected={report['corrected']}, "
              f"failed esclusi={report['excluded_failed']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
