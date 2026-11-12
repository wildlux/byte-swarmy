"""Suite DATI COMPLESSI — 600 task su 6 categorie.

Testa il sistema su task complessi/enterprise. Supporta:
  - filtro per categoria (--cat programmazione_complessa)
  - campionamento (--sample N per categoria)
  - filtro per modello (--model worker_coder)
  - routing ON/OFF (--routing)

Output: state/suite_complex_data/results.json (incrementale, riprendibile).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from CORE.skill_executor import run_direct  # noqa: E402

DATA_FILE = "DATI_COMPLESSI.json"
PROJECT = "project/PR_TEST_progetto"


def load_tasks(cats_filter=None, sample=None, seed=42):
    data = json.load(open(DATA_FILE, encoding="utf-8"))
    all_tasks = []
    for cat, info in data["categorie"].items():
        if cats_filter and cat not in cats_filter:
            continue
        for ex in info.get("esempi", []):
            all_tasks.append({
                "id": f"{cat[:4]}_{ex['id']}",
                "cat": cat,
                "title": ex["richiesta"],
            })
    if sample:
        rng = random.Random(seed)
        by_cat = {}
        for t in all_tasks:
            by_cat.setdefault(t["cat"], []).append(t)
        sampled = []
        for cat, tasks in by_cat.items():
            sampled.extend(rng.sample(tasks, min(sample, len(tasks))))
        all_tasks = sampled
    return all_tasks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", nargs="?", default="worker_coder")
    parser.add_argument("--cat", nargs="*", help="Categorie da testare")
    parser.add_argument("--sample", type=int, default=None,
                        help="N task per categoria (campionamento)")
    parser.add_argument("--routing", action="store_true",
                        help="Abilita routing (default OFF)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    tasks = load_tasks(args.cat, args.sample, args.seed)
    print(f"Task da eseguire: {len(tasks)} (model={args.model}, "
          f"routing={'ON' if args.routing else 'OFF'})", flush=True)

    out_dir = Path("state/suite_complex_data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.json"
    results: dict = {}
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            results = {}
    results.setdefault(args.model, {})

    done = 0
    failed = 0
    for t in tasks:
        tid = t["id"]
        if tid in results[args.model] and results[args.model][tid].get("done"):
            continue
        t0 = time.monotonic()
        try:
            res = run_direct(
                {"title": t["title"]}, PROJECT, model_key=args.model,
                max_retries=2, enable_routing=args.routing)
        except Exception as e:
            res = {"ok": False, "attempts": 0, "error": f"runner: {e}",
                   "stdout": "", "history": []}
        dt = round(time.monotonic() - t0, 1)
        res["done"] = True
        res["secs"] = dt
        res["cat"] = t["cat"]
        results[args.model][tid] = res
        out_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8")
        status = "ok" if res["ok"] else "FAIL"
        if res["ok"]:
            done += 1
        else:
            failed += 1
        print(f"[{args.model}] {tid}: {status} "
              f"(att {res.get('attempts')}, {dt}s) "
              f"stdout={repr((res.get('stdout') or '')[:60])}",
              flush=True)
        if not res["ok"]:
            print(f"   err: {(res.get('error') or '')[:120]}", flush=True)

    total = done + failed
    print(f"\n=== {args.model}: {done}/{total} ok, {failed} fail ===",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())