"""Spot-check post-ottimizzazioni: task falliti della suite, codice nuovo.

1) worker_coder_big su T9 (era timeout LLM) — valida SYSTEM_DIRECT
   nuovo + extract_code con troncamento prosa
2) worker_granite (granite4:7b-a1b-h, ~1B attivi) su T9 e T1 —
   candidato heavy alternativo per questa macchina

Output: state/suite_compare/spotcheck.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from CORE.skill_executor import run_direct  # noqa: E402

PROJECT = "project/PR_TEST_progetto"

T9 = ("Decoratore misura_tempo che stampa i millisecondi di esecuzione "
      "di una funzione. Applicalo a una funzione che somma i numeri "
      "da 1 a 100000 e stampa SOMMA=5000050000.")
T1 = ("fammi un software in python che calcola media, mediana e moda di "
      "una lista di numeri. Usa la lista [4, 2, 7, 2, 5] come dati di "
      "esempio e stampa i tre valori.")

RUNS = [
    ("worker_coder_big", "T9", T9),
    ("worker_granite", "T9", T9),
    ("worker_granite", "T1", T1),
]


def main() -> int:
    out_path = Path("state/suite_compare/spotcheck.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results: dict = {}
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            results = {}
    for model, tid, text in RUNS:
        key = f"{model}/{tid}"
        if key in results and results[key].get("done"):
            continue
        t0 = time.monotonic()
        started_at = datetime.now().isoformat()
        try:
            res = run_direct({"title": text}, PROJECT, model_key=model,
                             max_retries=3, enable_routing=False)
        except Exception as e:
            res = {"ok": False, "attempts": 0, "error": f"runner: {e}",
                   "stdout": "", "history": []}
        res["done"] = True
        res["secs"] = round(time.monotonic() - t0, 1)
        results[key] = res
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"[{key}] {'ok' if res['ok'] else 'FAIL'} "
              f"(attempts {res.get('attempts')}, {res['secs']}s) "
              f"stdout={repr((res.get('stdout') or '')[:60])}", flush=True)
    print(f"\nSPOTCHECK SALVATO: {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
