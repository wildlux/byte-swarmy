#!/usr/bin/env python3
"""tools/bench_cold_sessions.py — Benchmark a sessioni fredde (🆕 Cycle 66).

Il portatile dell'utente ha un limite termico duro: 60°C (mai di più).
Misurato (Cycle 66): da macchina calda (51°C) il carico LLM scala ~1°C/s —
nessun segmento di 20-30s può ripartire senza sforare. Da freddo (44-46°C)
scala ~0,3°C/s e un segmento breve resta in soglia.

Protocollo: per ogni task, aspetta che la macchina sia FREDDA (≤ COLD_START),
poi lancia UNA sessione di benchmark (`--task <id>`: fast lane + naked con
pausa adattiva interna). Tra le sessioni il driver NON carica la CPU.

Uso:
    .venv/bin/python tools/bench_cold_sessions.py                 # tutti
    .venv/bin/python tools/bench_cold_sessions.py ext-03 ext-05   # subset
"""

import glob
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")

COLD_START = 45.5     # °C: sotto questa temperatura si lancia una sessione
MAX_COOL_WAIT = 1800  # s: attesa massima di raffreddamento (30 min)


def max_temp() -> float:
    """Temperatura massima tra le zone termiche (stessa fonte del benchmark)."""
    m = 0.0
    for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            m = max(m, float(Path(p).read_text().strip()) / 1000.0)
        except Exception:
            pass
    return m


def wait_cold(limit: float = COLD_START, max_wait: float = MAX_COOL_WAIT) -> bool:
    """Attende il raffreddamento. True = fredda, False = max wait scaduto."""
    waited = 0.0
    while True:
        t = max_temp()
        if t <= limit:
            return True
        if waited >= max_wait:
            print(f"[driver] max attesa scaduto: {t:.1f}°C > {limit}°C "
                  f"dopo {waited:.0f}s", flush=True)
            return False
        print(f"[driver] attesa raffreddamento: {t:.1f}°C > {limit}°C "
              f"({waited:.0f}s/{max_wait:.0f}s)", flush=True)
        time.sleep(20.0)
        waited += 20.0


def main() -> int:
    tasks = sys.argv[1:] or [f"ext-{i:02d}" for i in range(1, 9)]
    print(f"[driver] sessioni fredde per {len(tasks)} task "
          f"(cold start ≤ {COLD_START}°C, mai sopra 60°C)", flush=True)

    for tid in tasks:
        print(f"\n[driver] === sessione {tid} ===", flush=True)
        if not wait_cold():
            print(f"[driver] fermo prima di {tid} — raffreddamento impossibile.")
            return 2
        t = max_temp()
        print(f"[driver] macchina fredda ({t:.1f}°C) → lancio {tid}", flush=True)
        r = subprocess.run(
            [PY, "-m", "CORE.external_benchmark", "--run",
             "--config", str(ROOT / "CONFIG" / "config.toml"),
             "--model", "worker_coder", "--cooldown", "30",
             "--thermal-limit", "60", "--resume-offset", "14",
             "--num-thread", "2",
             "--task", tid],
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            print(f"[driver] {tid} ritorno {r.returncode} — stop.", flush=True)
            return r.returncode

    # Riepilogo: aggrega i JSON dell'ultima ora per task
    print("\n[driver] === RIEPILOGO SESSIONI ===", flush=True)
    bench_dir = ROOT / "state" / "benchmarks"
    by_task = {}
    for jf in sorted(bench_dir.glob("external_bench-*.json")):
        if time.time() - jf.stat().st_mtime > 6 * 3600:
            continue
        try:
            d = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        for mode in ("harness", "naked"):
            for t in d.get("tasks", {}).get(mode, []):
                tid = t.get("task_id")
                if not tid or t.get("skipped"):
                    continue
                key = (tid, mode)
                by_task.setdefault(key, {
                    "ok1": bool(t.get("success_first_try")),
                    "wall": float(t.get("wall_seconds", 0) or 0),
                })

    for tid in tasks:
        h = by_task.get((tid, "harness"))
        n = by_task.get((tid, "naked"))
        hs = ("OK " if h and h["ok1"] else "NO ") if h else " n.d."
        ns = ("OK " if n and n["ok1"] else "NO ") if n else " n.d."
        hw = f"{h['wall']:.0f}s" if h else "-"
        nw = f"{n['wall']:.0f}s" if n else "-"
        print(f"  {tid}: fast lane {hs} ({hw}) | naked {ns} ({nw})", flush=True)

    print("[driver] DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
