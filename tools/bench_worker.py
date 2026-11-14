#!/usr/bin/env python3
"""Benchmark del worker ReAct con Ollama reale.

Esegue task rappresentativi (creazione file + patch) direttamente tramite
CORE.worker.Worker con ModelClient reale, in una sandbox isolata
(state/bench_sandbox/ — il progetto reale non viene toccato).

Per ogni chiamata LLM registra: modello, char del prompt, char del system,
chunk/tokens in uscita, durata. Salva i risultati in state/benchmarks/ e
confronta con la baseline precedente (bench-baseline.json): l'obiettivo è
misurare l'effetto reale delle ottimizzazioni token (T1–T22) sul tempo
per step su hardware lento (4GB VRAM).

Usage:
    .venv/bin/python tools/bench_worker.py                  # esegue + confronta
    .venv/bin/python tools/bench_worker.py --save-baseline  # salva come baseline
    .venv/bin/python tools/bench_worker.py --task-timeout 900
"""

import argparse
import copy
import json
import logging
import os
import shutil
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCHMARKS_DIR = ROOT / "state" / "benchmarks"
SANDBOX_DIR = ROOT / "state" / "bench_sandbox"
BASELINE_FILE = BENCHMARKS_DIR / "bench-baseline.json"

BENCH_TASKS = [
    {
        "id": "bench-create",
        "title": "Crea bench_calc.py",
        "description": (
            "Crea il file bench_calc.py con una funzione add(a, b) che "
            "ritorna la somma di due numeri. Includi una docstring breve."
        ),
    },
    {
        "id": "bench-patch",
        "title": "Aggiungi mul a bench_calc.py",
        "description": (
            "Modifica bench_calc.py: aggiungi una funzione mul(a, b) che "
            "ritorna il prodotto di due numeri. Non rimuovere la funzione add."
        ),
    },
]


def get_logger() -> logging.Logger:
    """Logger di console per il benchmark."""
    log = logging.getLogger("bench-worker")
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        log.addHandler(h)
    log.setLevel(logging.INFO)
    return log


def ollama_reachable(host: str, timeout: float = 3.0) -> bool:
    """True se Ollama risponde su <host>/api/tags entro il timeout."""
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags",
                                    timeout=timeout):
            return True
    except Exception:
        return False


class CallRecorder:
    """Registra ogni chiamata LLM fatta dal worker (streaming e non)."""

    def __init__(self):
        self.rows: list = []

    def reset(self) -> None:
        """Svuota le righe raccolte (all'inizio di ogni task)."""
        self.rows = []

    def attach(self, client) -> None:
        """Wrappa call_streaming e call del client per la misurazione.

        Firma esplicita (non *args/**kwargs): il worker chiama sempre con
        queste keyword, così estraiamo model_key/prompt in modo affidabile.
        """
        rec = self
        orig_stream = client.call_streaming
        orig_call = client.call

        def stream_wrap(model_key, prompt, system=None, max_tokens=None,
                        options_override=None):
            t0 = time.perf_counter()
            chunks = 0
            out_chars = 0
            try:
                for tok in orig_stream(
                    model_key=model_key, prompt=prompt, system=system,
                    max_tokens=max_tokens, options_override=options_override,
                ):
                    chunks += 1
                    out_chars += len(tok or "")
                    yield tok
            finally:
                # finally: cattura anche il caso di early-stop (T21) con
                # chiusura anticipata del generatore da parte del worker.
                rec.rows.append({
                    "kind": "stream", "model": model_key,
                    "prompt_chars": len(prompt or ""),
                    "system_chars": len(system or ""),
                    "out_chars": out_chars,
                    "chunks": chunks,
                    "seconds": round(time.perf_counter() - t0, 2),
                })

        def call_wrap(model_key, prompt, system=None, max_tokens=None):
            t0 = time.perf_counter()
            out = orig_call(model_key=model_key, prompt=prompt,
                            system=system, max_tokens=max_tokens)
            rec.rows.append({
                "kind": "call", "model": model_key,
                "prompt_chars": len(prompt or ""),
                "system_chars": len(system or ""),
                "out_chars": len(out or ""), "chunks": 0,
                "seconds": round(time.perf_counter() - t0, 2),
            })
            return out

        client.call_streaming = stream_wrap
        client.call = call_wrap


def _totals(rows: list) -> dict:
    """Aggrega le righe di un task in totali compatti."""
    in_chars = sum(r["prompt_chars"] + r["system_chars"] for r in rows)
    # Stima token: ~4 char/token (euristica standard per italiano/codice)
    est_in = in_chars // 4
    # In uscita: i chunk dello streaming ≈ token; le call complete si
    # stimano dai char.
    est_out = sum(r["chunks"] for r in rows) + sum(
        r["out_chars"] // 4 for r in rows if r["kind"] == "call")
    return {
        "calls": len(rows),
        "in_chars": in_chars,
        "est_in_tokens": est_in,
        "est_out_tokens": est_out,
        "llm_seconds": round(sum(r["seconds"] for r in rows), 2),
    }


def run_bench(task_timeout: int, log: logging.Logger) -> dict:
    """Esegue i task di benchmark in sandbox e ritorna il report JSON."""
    from CORE.orchestrator import load_config
    from CORE.ollama_client import ModelClient
    from CORE.tools import ToolSet
    from CORE.memory import AgentMemory
    from CORE.worker import Worker

    cfg = load_config(str(ROOT / "CONFIG" / "config.toml"))
    host = cfg["ollama"]["host"]
    if not ollama_reachable(host):
        log.error(f"Ollama non raggiungibile su {host} — avvialo e riprova.")
        sys.exit(2)

    # Sandbox: copia della config con path ridirezionati. Il progetto
    # reale (project/, state/memory) NON viene toccato.
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR, ignore_errors=True)
    (SANDBOX_DIR / "project").mkdir(parents=True, exist_ok=True)
    (SANDBOX_DIR / "state").mkdir(parents=True, exist_ok=True)
    cfg = copy.deepcopy(cfg)
    cfg["paths"]["project_root"] = str(SANDBOX_DIR / "project")
    cfg["paths"]["state_dir"] = str(SANDBOX_DIR / "state")

    logger = get_logger()
    tools = ToolSet(cfg, logger)
    client = ModelClient(cfg, logger)
    recorder = CallRecorder()
    recorder.attach(client)

    model_key = "worker_coder"
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "host": host,
        "model_key": model_key,
        "prompt_version": getattr(Worker, "PROMPT_VERSION", "n/d"),
        "tasks": [],
    }

    for task in BENCH_TASKS:
        log.info(f"--- task {task['id']}: {task['title']}")
        memory = AgentMemory("bench-worker", Path(cfg["paths"]["state_dir"]),
                             client, logger)
        worker = Worker("bench-worker", model_key, tools, memory,
                        client, logger)
        recorder.reset()
        t0 = time.perf_counter()
        result, timed_out = "", False
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(worker.execute, dict(task))
                result = fut.result(timeout=task_timeout)
        except Exception as e:
            timed_out = True
            result = f"TIMEOUT/ERROR: {e}"
        wall = round(time.perf_counter() - t0, 2)

        artifact = SANDBOX_DIR / "project" / "bench_calc.py"
        rec_task = {
            "id": task["id"],
            "wall_seconds": wall,
            "timed_out": timed_out,
            "artifact_ok": artifact.exists(),
            "result": (result or "")[:300],
            "calls": list(recorder.rows),
            "totals": _totals(recorder.rows),
        }
        report["tasks"].append(rec_task)
        log.info(f"--- {task['id']}: wall={wall}s llm={rec_task['totals']['llm_seconds']}s "
                 f"steps={rec_task['totals']['calls']} "
                 f"in~{rec_task['totals']['est_in_tokens']}tok "
                 f"out~{rec_task['totals']['est_out_tokens']}tok "
                 f"artifact={'OK' if rec_task['artifact_ok'] else 'MANCANTE'}"
                 + (" TIMEOUT" if timed_out else ""))
        for i, r in enumerate(rec_task["calls"], 1):
            log.info(f"    step {i}: {r['model']} in={r['prompt_chars']}+{r['system_chars']}ch "
                     f"out={r['out_chars']}ch/{r['chunks']}chunk {r['seconds']}s")

    grand = {
        "wall_seconds": round(sum(t["wall_seconds"] for t in report["tasks"]), 2),
        "est_in_tokens": sum(t["totals"]["est_in_tokens"] for t in report["tasks"]),
        "est_out_tokens": sum(t["totals"]["est_out_tokens"] for t in report["tasks"]),
        "calls": sum(t["totals"]["calls"] for t in report["tasks"]),
    }
    report["grand"] = grand
    return report


def compare(current: dict, baseline: dict, log: logging.Logger) -> None:
    """Stampa il confronto current vs baseline (negativo = meglio)."""
    log.info("")
    log.info("=== CONFRONTO vs baseline "
             f"({baseline.get('timestamp', '?')}, prompt {baseline.get('prompt_version', '?')}) ===")
    log.info(f"{'metrica':<28}{'baseline':>12}{'ora':>12}{'delta':>10}")
    bg, cg = baseline.get("grand", {}), current.get("grand", {})
    for label, key in (("wall totale (s)", "wall_seconds"),
                       ("token prompt (stima)", "est_in_tokens"),
                       ("token generati (stima)", "est_out_tokens"),
                       ("chiamate LLM", "calls")):
        b, c = bg.get(key, 0), cg.get(key, 0)
        delta = f"{((c - b) / b * 100):+.1f}%" if b else "n/d"
        log.info(f"{label:<28}{b:>12}{c:>12}{delta:>10}")
    bt = {t["id"]: t for t in baseline.get("tasks", [])}
    for t in current.get("tasks", []):
        b = bt.get(t["id"], {}).get("wall_seconds", 0)
        if b:
            log.info(f"  {t['id']}: wall {b}s → {t['wall_seconds']}s "
                     f"({((t['wall_seconds'] - b) / b * 100):+.1f}%)")


def main() -> None:
    """Entry point CLI del benchmark worker."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--save-baseline", action="store_true",
                    help="salva il risultato come nuova baseline")
    ap.add_argument("--task-timeout", type=int, default=600,
                    help="timeout per singolo task (default 600s)")
    args = ap.parse_args()

    log = get_logger()
    report = run_bench(args.task_timeout, log)

    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    hist = BENCHMARKS_DIR / f"bench-{ts}.json"
    hist.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    log.info(f"report salvato: {hist}")

    baseline = None
    if BASELINE_FILE.exists() and not args.save_baseline:
        try:
            baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
            compare(report, baseline, log)
        except Exception as e:
            log.warning(f"confronto baseline fallito: {e}")

    if args.save_baseline or not BASELINE_FILE.exists():
        BASELINE_FILE.write_text(json.dumps(report, indent=2,
                                            ensure_ascii=False),
                                 encoding="utf-8")
        log.info(f"baseline aggiornata: {BASELINE_FILE}")

    failed = any(t["timed_out"] or not t["artifact_ok"] for t in report["tasks"])
    sys.stdout.flush()
    sys.stderr.flush()
    # os._exit: termina anche eventuali thread worker sopravvissuti a un
    # timeout (i thread Python non si possono terminare).
    os._exit(1 if failed else 0)


if __name__ == "__main__":
    main()
