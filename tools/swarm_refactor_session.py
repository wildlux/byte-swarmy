#!/usr/bin/env python3
"""Sessione di refactoring su progetto esterno TRAMITE il worker reale.

Nata per il test su prismalux (repo utente, clone in project/):
un task, un agente FRESH, attesa fredda automatica. Differenze chiave
rispetto a build_real_worker_factory (CORE/external_benchmark.py):

  - agent_id nuovo (default "prx-worker"): la factory del benchmark
    riusa "bench-worker-{model_key}" cuya memoria resta inquinata da
    sessioni passate (695 eventi → hallucination misurata);
  - project_root = progetto target (le gate del ToolSet lavorano lì);
  - DESCRIZIONE con DISCIPLINA (learning ledger #4): read_file prima
    di write_file, vietato creare file nuovi, un solo file toccato;
  - attesa fredda automatica: non parte finché la CPU non è ≤
    soglia (limite termico 60°C, regola permanente);
  - temp before/after + wall time stampati per il registro.

Uso:
    .venv/bin/python tools/swarm_refactor_session.py \
        --project project/prismalux \
        --file MCPs/docker_mcp/server.py \
        --title "..." --description "..." [--task-id prx-mcp-05]

Il runner NON scrive mai nel repo target: esegue solo il task e
stampa il risultato (la verifica post-run è a parte, deterministica).
"""

import argparse
import glob
import logging
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COLD_THRESHOLD_C = 45.5   # sotto il limite 60°C, margine per il run
MAX_WAIT_SEC = 45 * 60    # attesa massima di raffreddamento
CHECK_EVERY_SEC = 20
AGENT_ID = "prx-worker"
NUM_THREAD = 2            # regola termica: meno calore (Cycle 66)

DISCIPLINA = (
    "DISCIPLINA (obbligatoria, dal ledger byte-swarmy #4): "
    "(1) PRIMA leggi il file target con lo strumento di lettura; "
    "(2) VIETATO creare file nuovi; (3) modifica SOLO il file "
    "indicato, con i cambi minimi; (4) dopo la modifica, rileggi "
    "per verifica. NOTA: i nomi-file e i nomi-strumento sono "
    "volutamente generici — parole specifiche inquina il routing "
    "e il matching skill (learning run 2)."
)


def read_max_temp() -> float:
    """Max temperatura tra le zone termiche (°C).

    🆕 Cycle 73 (lezione UEFI): si usa la max su TUTTE le zone —
    B0D4 non è un falso sensore (misurato: 52°C a freddo, 100°C sotto
    carico → UEFI block). Ignorarlo significa non vedere il componente
    più caldo. Il gate severo è la protezione, non il nemico: le
    attese lunghe si risolvono con le VENTOLE (tools/fan_control_qt.py),
    non abbassando la guardia.
    """
    m = 0.0
    for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            m = max(m, float(Path(p).read_text().strip()) / 1000.0)
        except (OSError, ValueError):
            pass
    return m


def wait_cold(threshold: float = COLD_THRESHOLD_C,
              max_wait: int = MAX_WAIT_SEC, log=None) -> tuple[bool, float]:
    """Aspetta il raffreddamento sotto soglia. Ritorna (ok, temp)."""
    t0 = time.time()
    temp = read_max_temp()
    while temp > threshold:
        if time.time() - t0 > max_wait:
            return False, temp
        if log:
            log.info("attesa fredda: %.1f°C > %.1f°C (%.0fs di attesa)",
                     temp, threshold, time.time() - t0)
        time.sleep(CHECK_EVERY_SEC)
        temp = read_max_temp()
    return True, temp


def build_task(task_id: str, title: str, description: str,
               file_path: str) -> dict:
    """Task dict con la disciplina già dentro la descrizione."""
    return {
        "id": task_id,
        "title": title,
        "description": f"{description} {DISCIPLINA}",
        "file": file_path,
        "type": "fix",
        "source": "debt_ledger",
    }


def run_session(project: Path, task: dict, config_path: str = "CONFIG/config.toml",
                model_key: str = "worker_coder", log=None) -> dict:
    """1 task con Worker diretto su agent fresh. Ritorna il report."""
    from CORE.constants import DEFAULT_PATHS
    from CORE.memory import AgentMemory
    from CORE.ollama_client import ModelClient
    from CORE.tools import ToolSet
    from CORE.worker import Worker

    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    # Override termico SOLO in memoria (mai su config.toml, Cycle 66).
    # 🆕 v2 (run 2: 46→66°C in 35s): su TUTTI i modelli — il routing
    # può passare a worker_granite, e senza override girerebbe con
    # i thread di default violando il limite 60°C.
    for _mk in config.setdefault("models", {}):
        config["models"][_mk]["num_thread"] = NUM_THREAD

    project_root = project.resolve()
    config["paths"] = dict(config.get("paths", {}))
    config["paths"]["project_root"] = str(project_root)

    state_dir = Path(config.get("paths", {}).get(
        "state_dir", DEFAULT_PATHS["state_dir"]))

    tools = ToolSet(config, log)
    memory = AgentMemory(agent_id=AGENT_ID, state_dir=state_dir,
                         model_client=ModelClient(config, log), logger=log)
    worker = Worker(agent_id=AGENT_ID, model_key=model_key, tools=tools,
                    memory=memory, model_client=memory.models, logger=log)

    temp_before = read_max_temp()
    t0 = time.time()
    result = worker.execute(task)
    wall = time.time() - t0
    temp_after = read_max_temp()
    return {"result": result, "wall": wall,
            "temp_before": temp_before, "temp_after": temp_after}


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        stream=sys.stdout)
    log = logging.getLogger("swarm_session")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("--file", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--task-id", default="swarm-task")
    ap.add_argument("--config", default="CONFIG/config.toml")
    ap.add_argument("--model", default="worker_coder")
    ap.add_argument("--threshold", type=float, default=COLD_THRESHOLD_C,
                    help="Soglia di raffreddamento (°C) prima di avviare "
                         "(default %.1f). Per task xs con runner v2 (num_thread "
                         "su tutti i modelli) si puo' alzare a ~48°C." %
                    COLD_THRESHOLD_C)
    args = ap.parse_args(argv)

    cwd = Path.cwd()
    ok, temp = wait_cold(threshold=args.threshold, log=log)
    if not ok:
        log.error("mai raffreddato sotto %.1f°C in %ds (ultima %.1f°C): "
                  "niente run (regola termica)", COLD_THRESHOLD_C,
                  MAX_WAIT_SEC, temp)
        return 2
    log.info("freddo raggiunto: %.1f°C → avvio sessione", temp)
    # 🆕 Guardia dura (lezione UEFI, Cycle 73): se QUALSIQUE zona è
    # ≥ 90°C il blocco UEFI è dietro l'angolo — mai inferenza.
    if temp >= 90.0:
        log.error("zona ≥ 90°C (%.1f°C): abort di sicurezza", temp)
        return 3

    task = build_task(args.task_id, args.title, args.description, args.file)
    try:
        report = run_session(cwd / args.project, task, args.config,
                             args.model, log)
    except Exception as e:  # noqa: BLE001 — report onesto anche in errore
        log.error("sessione fallita: %s", e)
        return 1

    log.info("wall: %.1fs | temp: %.1f°C → %.1f°C",
             report["wall"], report["temp_before"], report["temp_after"])
    print("--- RISULTATO WORKER ---")
    print(str(report["result"])[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
