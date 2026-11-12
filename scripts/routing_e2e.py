"""M2 — Test e2e del routing LIVE (Fase 7, percorso completo).

Differenza dai unit test (tests/test_routing.py): qui NON c'è client finto
— `run_direct` parte con client None (percorso CLI reale) e `enable_routing`
si attiva da solo. Atteso:
  1. il task cita simboli toccando ≥2 file → livello ALTA per IMPATTO
  2. la decisione `route` nel risultato deve nominare `worker_granite`
  3. granite4 genera il codice e il task PASSA (marker runtime corretti)

Progetto: `project/PR_TEST_routing` (creato al volo se manca) con catena
utils.Statistiche ← app.report ← test_app.test_report — la stessa struttura
dei unit test, così il verdict di impatto è noto in anticipo.

Output: state/suite_compare/routing_e2e.json — mai solleva per singolo run.
ATTENZIONE: usa l'LLM — NON lanciare insieme alla suite (conflitto RAM).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from CORE.routing import reset_hysteresis          # noqa: E402
from CORE.skill_executor import run_direct         # noqa: E402

PROJ = "project/PR_TEST_routing"

FILES = {
    "utils.py": (
        "class Statistiche:\n"
        "    def media(self, numeri):\n"
        "        return sum(numeri) / len(numeri)\n"
        "\n"
        "    def mediana(self, numeri):\n"
        "        nums = sorted(numeri)\n"
        "        n = len(nums)\n"
        "        mid = n // 2\n"
        "        if n % 2:\n"
        "            return nums[mid]\n"
        "        return (nums[mid - 1] + nums[mid]) / 2\n"),
    "app.py": (
        "from utils import Statistiche\n"
        "\n"
        "\n"
        "def report(numeri):\n"
        "    s = Statistiche()\n"
        "    return s.media(numeri), s.mediana(numeri)\n"),
    "test_app.py": (
        "from app import report\n"
        "\n"
        "\n"
        "def test_report():\n"
        "    assert report([1, 2, 3]) == (2.0, 2)\n"),
}

# Cita Statistiche/media/mediana → file toccati: utils.py (def) + app.py
# (chiamate) → IMPATTO ALTA → il routing DEVE scegliere l'heavy.
TASK = ("usa la classe Statistiche di utils.py per calcolare media e "
        "mediana della lista [4, 2, 7, 2, 5] e stampa MEDIA=4 e MEDIANA=4.")

RUNS = [
    ("routing_live_alta", TASK),
]


def main() -> int:
    proj = Path(PROJ)
    proj.mkdir(parents=True, exist_ok=True)
    for name, content in FILES.items():
        p = proj / name
        if not p.exists():
            p.write_text(content, encoding="utf-8")

    out_path = Path("state/suite_compare/routing_e2e.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results: dict = {}
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            results = {}

    for rid, text in RUNS:
        if rid in results and results[rid].get("done"):
            continue
        reset_hysteresis()
        t0 = time.monotonic()
        try:
            # client None → percorso CLI reale → routing AUTO-ON
            res = run_direct({"title": text}, PROJ, max_retries=3)
        except Exception as e:
            res = {"ok": False, "attempts": 0, "error": f"runner: {e}",
                   "route": "", "stdout": "", "history": []}
        dt = round(time.monotonic() - t0, 1)
        res["done"] = True
        res["secs"] = dt
        res["started_at"] = started_at
        res["finished_at"] = datetime.now().isoformat()
        results[rid] = res
        out_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8")
        route = res.get("route") or ""
        model = res.get("model") or "?"
        ok = "ok" if res["ok"] else "FAIL"
        heavy_picked = "worker_granite" == model
        print(f"[{rid}] {ok} attempts={res.get('attempts')} {dt}s "
              f"model={model} heavy_picked={heavy_picked}",
              flush=True)
        print(f"   route: {route}", flush=True)
        print(f"   stdout: {repr((res.get('stdout') or '')[:80])}",
              flush=True)
        if not res["ok"]:
            print(f"   error: {(res.get('error') or '')[:200]}", flush=True)
            for h in res.get("history", []):
                print(f"   └ {h.get('attempt')} | "
                      f"{(h.get('error') or '')[:160]}", flush=True)

    print(f"\nE2E SALVATO: {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
