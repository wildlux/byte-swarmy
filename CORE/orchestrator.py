"""
orchestrator.py — Single process, single loop, classes.

Architettura:
  Orchestrator  -> legge coda, dispatcha
  Planner       -> decompone task complessi (on-demand)
  Worker        -> esegue un task usando ToolSet + ModelClient
  TaskQueue     -> coda persistente su file JSON

Tutto gira in UN processo, UN thread, UN while True.
Niente multiprocessing, niente asyncio. Sequenziale e predicibile.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import shutil
import signal
import sys
import time
import tarfile
from pathlib import Path
from typing import Optional

from CORE.constants import DEFAULT_NUM_CTX
from MONITORING.lifecycle_manager import LifecycleManager
from MONITORING.system_monitor import SystemMonitor
from CORE.task_dispatcher import TaskDispatcher

# core/orchestrator.py
from CORE.tools import ToolSet
from CORE.memory import AgentMemory
from CORE.ollama_client import ModelClient

# New import for structured logging
import datetime

# Python 3.11+ ha tomllib, fallback a tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        log.error("ERROR: serve Python 3.11+ o `pip install tomli`")
        sys.exit(1)

from CORE.tools import ToolSet
from CORE.memory import AgentMemory
from CORE.ollama_client import ModelClient
from CORE.regex_controller import RegexController, DEFAULT_PATTERNS, json_block

# Controllore regex riusabile (json_object, json_array già nei default)
_REGEX = RegexController(DEFAULT_PATTERNS)
from SAFETY.security import log_security_event
from SAFETY.security_checks import check_isolation, apply_safe_mode
from CORE.execute_handler import handle_execute_task
from CORE.decision_feedback import DecisionValidator
from CORE.correction import build_correction_prompt
from CORE.loop_detector import detect_loop
from CORE.last_good_config import last_good_config
from MONITORING.thermal_manager import (TimestralManager, TimestralGatekeeper,
                                        load_timestral_overrides,
                                        PAUSE_CPU, PAUSE_GPU, RESUME_TEMP)
from CORE.scheduler_worker import SchedulerWorker
from CORE.task_queue import TaskQueue
from CORE.planner import Planner
from CORE.auditor import AuditWorker
from CORE.generic_planner import GenericTaskPlanner
from CORE.worker import Worker, suggest_escalation


# ====================================================================
# LOGGER
# ====================================================================

def setup_logger(config) -> logging.Logger:
    log_cfg = config.get("logging", {})
    log_file = log_cfg.get("file", "./logs/byte-swarmy.log")
    log_jsonl_file = log_cfg.get("jsonl", "./logs/byte-swarmy.jsonl")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logger = logging.getLogger("byte-swarmy")
    logger.setLevel(level)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file)
    fh.setFormatter(logging.Formatter(fmt))
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter(fmt))
    logger.addHandler(sh)

    # Structured JSONL Logger
    jsonl_handler = logging.FileHandler(log_jsonl_file)
    class JSONLFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": datetime.datetime.now(
                    datetime.timezone.utc).isoformat(),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            }
            if hasattr(record, "extra_data"):
                log_record.update(record.extra_data)
            return json.dumps(log_record)

    jsonl_handler.setFormatter(JSONLFormatter())
    logger.addHandler(jsonl_handler)

    return logger


# ====================================================================
# CONFIG LOADER
# ====================================================================

def load_config(path: str = "CONFIG/config.toml") -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)



class Orchestrator:
    """
    Coordination layer. Integrates specialized managers to maintain the swarm.
    Follows Single Responsibility Principle (SRP).
    """
    def __init__(self, config_path: str = "CONFIG/config.toml"):
        self.config = load_config(config_path)
        self.log = setup_logger(self.config)

        # --- SYSTEM ISOLATION CHECK (Safe Mode) ---
        is_safe, reason = check_isolation()
        if not is_safe:
            self.log.error(f"SECURITY ALERT: {reason}")
            apply_safe_mode(self.log)
        else:
            self.log.info("✓ System isolation verified. Running in Standard Mode.")

        # 1. Lifecycle & Setup
        self.lifecycle = LifecycleManager(self.config, self.log)
        self.lifecycle.prepare_directories()
        self.lifecycle.init_git()

        # 2. Core Components
        self.models = ModelClient(self.config, self.log)
        self.tools = ToolSet(self.config, self.log)
        self.queue = TaskQueue(Path(self.config["paths"]["tasks_dir"]), self.log)
        # Retry dei task configurabili: [orchestrator] max_task_retries e
        # retry_cooldown_sec in CONFIG/config.toml (quante volte ritentare
        # e quanto aspettare tra i tentativi prima del blocco definitivo).
        self.retry_cooldown_sec = 30
        try:
            o_cfg = self.config.get("orchestrator", {})
            self.queue.RETRY_LIMIT = max(1, int(o_cfg.get("max_task_retries", 3)))
            self.retry_cooldown_sec = max(0, int(o_cfg.get("retry_cooldown_sec", 30)))
            self.log.info(
                f"[orchestrator] max_task_retries={self.queue.RETRY_LIMIT} "
                f"retry_cooldown_sec={self.retry_cooldown_sec}")
        except Exception as e:
            self.log.warning(f"config retry non valida, uso i default: {e}")
        # 🆕 Fix: resetta task "running" a "pending" all'avvio (erano crashati)
        try:
            with self.queue._get_conn() as conn:
                cur = conn.execute(
                    "UPDATE tasks SET status = 'pending', started_at = NULL "
                    "WHERE status = 'running'"
                )
                if cur.rowcount > 0:
                    self.log.info(f"reset {cur.rowcount} zombie running task(s) to pending")
                conn.commit()
        except Exception as e:
            self.log.warning(f"reset running tasks failed: {e}")
        self.planner = Planner(self.models, self.log)
        self.generic_planner = GenericTaskPlanner(self.config, self.models, self.log)
        self.auditor = AuditWorker(self.models, self.log, decision_client=self.generic_planner._call_decision_model)

        # Pre-flight validation + feedback su SQLite (work order T1)
        self.decision_validator = DecisionValidator(
            self.queue,
            decision_client=self.generic_planner.ask_verdict,
        )

        # 3. Monitoring
        self.timestral = None
        if self.config.get("thermal", {}).get("enabled", False):
            try:
                self.timestral = TimestralManager(self.config, self.log, base_dir=Path(self.config["paths"]["state_dir"]).parent)
                self.timestral.start()
            except Exception as e:
                self.log.warning(f"Timestral failed: {e}")

        # Gatekeeper termico: priorità CONFIG/actors.json (T2.2, pannello
        # Attori della GUI) > config.toml [thermal] > default work order T3
        thermal_cfg = self.config.get("thermal", {})
        actors_ts = load_timestral_overrides()
        pause_cpu = float(actors_ts.get(
            "cpu_temp_threshold",
            thermal_cfg.get("pause_cpu", PAUSE_CPU)))
        pause_gpu = float(actors_ts.get(
            "gpu_temp_threshold",
            thermal_cfg.get("pause_gpu", PAUSE_GPU)))
        # A1: resume_temp da actors.json (con fallback a config.toml, poi
        # default 65). Prima era hardcoded, ora se l'utente imposta 70 dal
        # pannello Attori, riprende a 70 (coerente con la soglia di pausa).
        resume_temp = float(actors_ts.get(
            "resume_temp_threshold",
            thermal_cfg.get("resume_temp", RESUME_TEMP)))
        # A2: soglia tok/s minima — se sotto, il gatekeeper scatta pausa
        min_tps = float(actors_ts.get(
            "min_tokens_per_sec",
            thermal_cfg.get("min_tokens_per_sec", 0.0)))
        # A3: se True, i controlli termici scattano solo se GPU presente
        self.check_only_if_gpu = bool(actors_ts.get(
            "check_only_if_gpu",
            thermal_cfg.get("check_only_if_gpu", False)))
        # A4: se True, durante pausa termica anche il decision model si ferma
        self.pause_decision_model_too = bool(actors_ts.get(
            "pause_decision_model_too",
            thermal_cfg.get("pause_decision_model_too", True)))
        self.thermal_gate = TimestralGatekeeper(
            pause_cpu=pause_cpu,
            pause_gpu=pause_gpu,
            resume_temp=resume_temp,
            min_tokens_per_sec=min_tps,
        )
        if actors_ts:
            self.log.info(
                "[timestral] attori override: pause_cpu=%.0f pause_gpu=%.0f "
                "resume=%.0f min_tps=%.1f check_only_if_gpu=%s pause_dm=%s",
                pause_cpu, pause_gpu, resume_temp, min_tps,
                self.check_only_if_gpu, self.pause_decision_model_too)
        # intervallo di campionamento configurabile dal pannello Attori
        interval = actors_ts.get("monitor_interval_sec")
        if interval:
            self.timestral.SAMPLE_INTERVAL = max(5, int(float(interval)))

        # ── H5: Strategia hardware + pesi modelli (Round 3) ────────────
        # Legge da CONFIG/settings.json (hardware_strategy) e da
        # CONFIG/actors.json (weights di llm/decision_model/timestral).
        # Poi decide dove mandare ogni modello:
        #   - gpu+cpu:   LLM → GPU,  Decision+Timestral → CPU (parallelo)
        #   - gpu_only:  LLM → GPU,  Decision → GPU,  Timestral → CPU (sempre)
        #   - cpu_only:  tutto su CPU
        #   - cpu_then_gpu: default CPU, switcha a GPU se CPU > 90% (overload)
        # Il Timestral è SEMPRE su CPU (force_cpu=True, gatekeeper reattivo).
        try:
            from GUI.settings_store import get_hardware_strategy, is_gpu_available
            self.hardware_strategy = get_hardware_strategy()
            self.gpu_available = is_gpu_available()
        except ImportError:
            # GUI non disponibile (es. test in CI) → fallback safe
            self.hardware_strategy = "cpu_only"
            self.gpu_available = False
        # Pesi modelli da actors.json
        self.actor_weights = {
            "llm": actors_ts.get("weight", "medium") if "weight" in actors_ts else
                   self._load_actor_weight("llm", "medium"),
            "decision_model": self._load_actor_weight("decision_model", "light"),
            "timestral": "light",  # H4: sempre light
        }
        # H4: force_cpu del Timestral — sempre True (gatekeeper in RAM su CPU)
        self.timestral_force_cpu = True
        self.log.info(
            "[hardware] strategy=%s gpu_available=%s weights=%s timestral_force_cpu=%s",
            self.hardware_strategy, self.gpu_available,
            self.actor_weights, self.timestral_force_cpu,
        )

        # Scheduler GUI (T2.3): thread background, ogni tick legge
        # CONFIG/scheduled_tasks.json e inietta i task scaduti in coda.
        self.scheduler = SchedulerWorker(self.queue, logger=self.log)
        self.scheduler.start()

        self.monitor = SystemMonitor(self.config, self.log, self.timestral)
        self.dispatcher = TaskDispatcher(self.queue, self.planner, self.generic_planner, self.models, self.tools, self.log)

        self.memories = {}
        self.running = True
        # Timer di manutenzione usati dal loop principale (_tick)
        now = time.time()
        self.last_health_check = now
        self.last_git_snapshot = now
        self.last_memory_compaction = now
        self.last_backup = now
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def preflight_and_queue(self, prompt: str, params: dict) -> dict:
        """Pre-flight + accodamento (work order T1).

        API per CLI e GUI (Task 4): puo' essere chiamata da un processo
        esterno (QProcess) per non bloccare mai il main thread della GUI.
        Ritorna {"status": "queued", "task_id": ...} oppure
        {"status": "needs_revision", "reason": ...}.
        """
        return self.decision_validator.validate(prompt, params).as_dict()

    def run(self) -> None:
        """Loop principale. Singolo thread."""
        tick = self.config["timing"]["orchestrator_tick"]

        while self.running:
            try:
                self._tick()
            except Exception as e:
                self.log.error(f"tick error (will continue): {e}", exc_info=True)

            # Sleep rispettando shutdown
            slept = 0
            while slept < tick and self.running:
                time.sleep(1)
                slept += 1

        # Cleanup
        self._shutdown()

    def _load_actor_weight(self, actor: str, default: str = "medium") -> str:
        """H5: legge il peso di un attore da CONFIG/actors.json.

        Ritorna "light" | "medium" | "heavy". Per il Timestral è sempre
        "light" (H4: gatekeeper in RAM su CPU).
        """
        try:
            from GUI.actors_panel import load_actors
            a = load_actors()
            return a.get(actor, {}).get("weight", default)
        except (ImportError, Exception):
            return default

    def _resolve_actor_target(self, actor: str) -> str:
        """H5: decide dove mandare il modello di un attore (CPU o GPU).

        Regole (in base a self.hardware_strategy):
          - cpu_only:  tutto → "cpu"
          - gpu_only:  LLM/Decision → "gpu", Timestral → "cpu" (H4)
          - gpu+cpu:   LLM → "gpu", Decision → "cpu", Timestral → "cpu"
          - cpu_then_gpu: default "cpu"; se CPU overload → "gpu" per LLM
            (overload: gestito da _check_resources, qui semplificato)
        """
        # H4: Timestral SEMPRE su CPU
        if actor == "timestral":
            return "cpu"
        # Se GPU non disponibile, tutto su CPU
        if not self.gpu_available:
            return "cpu"
        # CPU only: tutto su CPU
        if self.hardware_strategy == "cpu_only":
            return "cpu"
        # GPU only: LLM e Decision su GPU
        if self.hardware_strategy == "gpu_only":
            return "gpu"
        # GPU+CPU: LLM su GPU, Decision su CPU (parallelo, più efficiente)
        if self.hardware_strategy == "gpu+cpu":
            return "gpu" if actor == "llm" else "cpu"
        # CPU→GPU: default CPU, switcha a GPU se CPU overload
        if self.hardware_strategy == "cpu_then_gpu":
            # Verifica overload CPU (ultimo sample)
            sample = getattr(self.timestral, "last_sample", None) if self.timestral else None
            if sample and getattr(sample, "cpu_load", 0) > 0.9 and actor == "llm":
                return "gpu"
            return "cpu"
        # Fallback safe
        return "cpu"

    def _resolve_actor_model(self, actor: str) -> str:
        """H5: ritorna il modello Ollama da usare per un attore, tenendo
        conto del peso (light/medium/heavy) e della strategia hardware.

        Per ora ritorna il modello salvato in actors.json per quell'attore
        (configurato dal pannello ActorsPanel). In futuro può applicare
        weight_default_model() per auto-sostituire in base al peso.
        """
        try:
            from GUI.actors_panel import load_actors
            a = load_actors()
            return a.get(actor, {}).get("model", "qwen2.5:1.5b")
        except (ImportError, Exception):
            # Fallback al modello di default
            return "qwen2.5:1.5b"

    def _thermal_gate_pass(self) -> bool:
        """Gatekeeper termico T3 (non bloccante, polling a ogni tick).

        False = tick sospeso: i task in attesa sono messi in
        'thermal_paused' e verrano riaccodati automaticamente appena la
        temperatura scende sotto la soglia di ripresa.

        A3: se ``check_only_if_gpu=True`` e GPU non rilevata (gpu_temp==0),
        il gate termico è sospeso (degradato, non blocca).
        A4: se ``pause_decision_model_too=True`` e il gate scatta, anche
        il decision model viene fermato (task generic non pianificati).
        """
        sample = (getattr(self.timestral, "last_sample", None)
                  if self.timestral else None)
        if sample is None:
            # sensori assenti/disabilitati: nessun gate (degradato, non blocca)
            return True

        cpu_temp = sample.cpu_temp_max
        gpu_temp = getattr(sample, "gpu_temp", 0.0)

        # A3: se l'utente ha flaggato "scatta controlli SOLO se GPU presente"
        # e GPU non rilevata (gpu_temp == 0), bypassa il gate termico.
        if self.check_only_if_gpu and gpu_temp == 0.0:
            # Logga una volta sola per cambio di stato (semi-debug)
            if not getattr(self, "_no_gpu_logged", False):
                self.log.info(
                    "[thermal-gate] GPU non rilevata, controllo termico "
                    "sospeso (check_only_if_gpu=True)"
                )
                self._no_gpu_logged = True
            return True
        else:
            self._no_gpu_logged = False

        # A2: passa tok/s se disponibile (altrimenti None = skip check tps)
        tok_per_sec = getattr(sample, "tokens_per_sec", None)
        if tok_per_sec is None:
            # Fallback: se il sample non ha tokens_per_sec, prova advice
            advice = self.timestral.get_advice() if self.timestral else None
            tok_per_sec = getattr(advice, "tokens_per_sec", None) if advice else None

        paused = self.thermal_gate.check(
            cpu_temp, gpu_temp, tok_per_sec=tok_per_sec,
        )
        if paused:
            self.queue.pause_thermal()
            self.log.warning(
                f"[thermal-gate] PAUSA TERMICA: {self.thermal_gate.pause_reason}"
            )
            # A4: se pause_decision_model_too, ferma anche il decision model
            # (usa generic_planner se presente — simmetrico al path ripresa)
            if self.pause_decision_model_too:
                planner = getattr(self, "generic_planner", None)
                if planner:
                    try:
                        planner.set_paused(True)
                    except Exception:
                        pass  # backward compat se non ha set_paused
            return False

        resumed = self.queue.resume_thermal()
        if resumed:
            self.log.info(
                f"[thermal-gate] ripresa (<{self.thermal_gate.resume_temp:.0f}C): "
                f"{resumed} task riaccodati"
            )
            # A4: riprendi anche il decision model
            if self.pause_decision_model_too:
                planner = getattr(self, "generic_planner", None)
                if planner:
                    try:
                        planner.set_paused(False)
                    except Exception:
                        pass
        return True

    def _tick(self) -> None:
        # Check pause.flag (GUI pausa) - se presente, salta TUTTI i tick
        import os
        _pause_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state', 'pause.flag')
        if os.path.exists(_pause_file):
            return  # Orchestratore in pausa - non processa nessun task

        # next_pending() filtra: status IN ('pending', 'retry')
        # - 'paused' (pausa utente) NON viene mai preso
        # - 'thermal_paused' gestito da pause_thermal/resume_thermal
        # - 'done', 'failed', 'completed' non vengono ripresi
        # Logica: orchestratore attivo AND task pending/retry = esecuzione

        """Singolo tick del loop."""
        # 0. Gatekeeper termico (T3) PRIMA di avviare qualsiasi LLM
        if not self._thermal_gate_pass():
            return

        # 1. Safety checks (ogni tick, leggeri)
        if not self._check_resources():
            self.log.warning("resources low, skipping tick")
            return

        # 1b. Timestral advice — pausa se CPU troppo calda
        if self.timestral:
            advice = self.timestral.get_advice()
            if advice.action == "pause":
                self.log.warning(f"[timestral] PAUSE: {advice.reason}")
                return
            # Logga cambio di stato
            if advice.action != "normal":
                self.log.info(f"[timestral] {advice.action.upper()}: {advice.reason} "
                              f"(tick x{advice.tick_multiplier})")

        # 2. Health check (ogni 5 min)
        if time.time() - self.last_health_check > self.config["timing"]["health_check"]:
            self._health_check()
            self.last_health_check = time.time()

        # 3. Git snapshot (ogni 15 min)
        if time.time() - self.last_git_snapshot > self.config["timing"]["git_snapshot"]:
            self.tools.git_commit(f"auto-snapshot {int(time.time())}")
            self.last_git_snapshot = time.time()

        # 4. Memory compaction (ogni 1 ora)
        if time.time() - self.last_memory_compaction > self.config["timing"]["memory_compaction"]:
            for mem in self.memories.values():
                mem.compact()
            self.last_memory_compaction = time.time()

        # 5. Backup (ogni 24h)
        if time.time() - self.last_backup > self.config["timing"]["backup_complete"]:
            self._backup()
            self.last_backup = time.time()

        # 6. Dispatch task
        task = self.queue.next_pending()
        if not task:
            return  # coda vuota, aspetta

        # 🆕 Intercetta swarm commands (gestione diretta, no LLM)
        swarm_intent = self._extract_swarm_intent(task)
        if swarm_intent:
            self.log.info(f"swarm command: {swarm_intent} (handling directly)")
            try:
                result = self._handle_swarm_command(task, swarm_intent)
                self.queue.mark_done(task["id"], result)
                self.log.info(f"swarm command {swarm_intent} done")
            except Exception as e:
                self.queue.mark_failed(task["id"], str(e))
                self.log.error(f"swarm command failed: {e}")
            return  # non passare al worker

        # 🆕 type=execute: handler deterministico (compila + esegui, no LLM)
        if task.get("type") == "execute":
            self.log.info(f"execute task {task['id']}: direct handler (no LLM)")
            try:
                result = handle_execute_task(
                    task, run_cmd=self.tools.run_bash, log=self.log
                )
            except Exception as e:
                result = f"ERROR: {e}"
            if str(result).startswith("ERROR"):
                self.queue.mark_failed(task["id"], str(result))
                self.log.warning(f"execute task {task['id']} failed "
                                 f"{str(result)[:120]}")
            else:
                self.queue.mark_done(task["id"], str(result))
                self.tools.git_commit(f"execute {task['id']}: "
                                      f"{task.get('title', '')[:50]}")
                self.log.info(f"execute task {task['id']} done")
            return  # il task è gestito: nessun worker, nessun auditor

        self.log.info(f"dispatching {task['id']}: {task.get('title', '')[:80]}")

        # 6a. Generic Task? Usa GenericTaskPlanner (decision model)
        if task.get("type") == "generic" or task.get("source", "").startswith("generic"):
            self.log.info(f"generic task {task['id']}: decomposing with decision model")
            if self.generic_planner.is_enabled():
                subtasks = self.generic_planner.decompose(task)
                if subtasks:
                    # Aggiungi sottotask alla coda
                    for st in subtasks:
                        self.queue.add(st)
                    self.queue._save()
                    # Marca il task generic come 'planned'
                    for t in self.queue.list_tasks():
                        if t["id"] == task["id"]:
                            t["status"] = "planned"
                            t["subtask_ids"] = [s["id"] for s in subtasks]
                            t["result"] = f"Decomposed into {len(subtasks)} code tasks"
                    self.queue._save()
                    self.log.info(f"generic task {task['id']} -> {len(subtasks)} code tasks")
                    return
                else:
                    self.log.warning(f"generic planner returned 0 subtasks, falling back to worker")
            else:
                self.log.warning("generic planner disabled or no decision model, "
                                 "treating as regular task")

        # 6b. Routing: serve il pianificatore classico?
        elif self._needs_planning(task):
            self.log.info(f"planning {task['id']}")
            subtasks = self.planner.decompose(task)
            if subtasks:
                # Aggiungi sottotask alla coda
                for st in subtasks:
                    self.queue.add(st)
                self.queue._save()
                # Marca il task parent come 'planned' (UPDATE SQLite diretto)
                self.queue.update_task(
                    task["id"],
                    status="planned",
                    subtask_ids=[s["id"] for s in subtasks],
                )
                return
            # Se il planner fallisce, esegui il task direttamente

        # 6c. Esegui con worker
        model_key = self._select_worker(task)
        worker = self._build_worker(task["id"], model_key)

        # ── Audit gate pre-esecuzione ────────────────────────────────
        # Prima di eseguire il task, verifica che il progetto target passi
        # il gate di audit (porte esposte, tunnel, import banditi, ecc.).
        # Modalità:
        #   - "off"      → skip (gate disattivato)
        #   - "advisory" → log warning se FAIL, ma procedi
        #   - "strict"   → blocca il task, marca come "blocked:audit_gate"
        try:
            from CORE.audit_gate import check_audit_gate, load_gate_config
            gate_cfg = load_gate_config()
            if gate_cfg.get("enabled", False) and gate_cfg.get("mode", "off") != "off":
                # Determina il project_path: "auto" = project/ di byte-swarmy,
                # oppure il path esplicito nel config.
                target = gate_cfg.get("target", "auto")
                if target == "auto":
                    import os
                    proj_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "project",
                    )
                    # Se il task ha un project_path specifico nel context, usalo
                    ctx = task.get("context", {})
                    if isinstance(ctx, dict) and ctx.get("project_path"):
                        proj_path = ctx["project_path"]
                else:
                    proj_path = target
                # Esegui il gate (sincrono: ~1-3s su progetti piccoli)
                gate_result = check_audit_gate(proj_path)
                if gate_result.gate == "FAIL":
                    if gate_result.blocks_execution:
                        # strict mode: blocca il task
                        self.log.warning(
                            f"task {task['id']} BLOCKED by audit gate "
                            f"(mode=strict, {gate_result.critical_count} critical)"
                        )
                        self.queue.mark_failed(
                            task["id"],
                            f"blocked:audit_gate ({gate_result.critical_count} critical findings)",
                        )
                        return
                    else:
                        # advisory mode: log warning ma procedi
                        self.log.warning(
                            f"task {task['id']} audit gate FAIL "
                            f"(mode=advisory, {gate_result.critical_count} critical) — procedo"
                        )
                else:
                    self.log.info(f"task {task['id']} audit gate PASS")
        except Exception as _e:
            # Se il gate check crasha, non bloccare l'esecuzione (fail-open)
            self.log.warning(f"audit gate check fallito (fail-open): {_e}")

        try:
            if not self._execute_task_with_worker(task, worker):
                # 🆕 Fallback modello: se worker_coder (3B) fallisce
                # definitivamente, prova con worker_general (1.5B)
                # come secondo tentativo.
                if worker.model_key == "worker_coder":
                    self.log.info(
                        f"task {task['id']} fallback modello: provo con worker_general"
                    )
                    # Rimette il task in pending per rieseguirlo con il fallback
                    self.queue.mark_pending(task["id"])
                    fallback_worker = self._build_worker(task["id"], "worker_general")
                    self._execute_task_with_worker(task, fallback_worker)
        except Exception as e:
            self.log.error(f"task {task['id']} exception: {e}", exc_info=True)

    def _execute_task_with_worker(self, task: dict, worker) -> bool:
        """Esegue un task con un worker e gestisce l'audit.

        Restituisce True se il task è stato completato con successo (APPROVE),
        False altrimenti (fallimento, rifiuto, eccezione).
        """
        try:
            result = worker.execute(task)
            if result.startswith("ERROR"):
                self._process_worker_failure(task, result,
                                             getattr(worker, "last_code", ""),
                                             worker)
                self.log.warning(f"task {task['id']} failed: {result[:100]}")
                return False
            # --- ENTERPRISE AUDIT STEP ---
            self.log.info(f"task {task['id']} submitted for audit")
            worker_history = worker.memory.get_history()
            audit_res = self.auditor.audit(task, result, worker_history)

            if audit_res.get("decision") == "APPROVE":
                self.log.info(f"task {task['id']} APPROVED by auditor")
                self.queue.mark_done(task["id"], result)
                # 🆕 Salva la configurazione LLM usata come "last good"
                # per poter fare rollback se una config futura fallisce.
                used_opts = self.models.last_options_used.get(
                    worker.model_key, {}
                )
                if used_opts:
                    last_good_config.save(worker.model_key, used_opts)
                    self.log.debug(
                        f"task {task['id']} saved last-good config for "
                        f"{worker.model_key}: {used_opts}"
                    )
                # Flusso utente 3: il progetto generato deve SEMPRE avere
                # un avvio (avvia.sh) — anche se l'LLM non l'ha scritto.
                self._ensure_avvio_script()
                self.tools.git_commit(f"task {task['id']}: {task.get('title', '')[:50]}")
                self.log.info(f"task {task['id']} DONE")
                return True
            else:
                feedback = audit_res.get("feedback", "No feedback provided")
                self.log.warning(
                    f"task {task['id']} REJECTED by auditor: {feedback[:100]}"
                )
                # We mark it as failed so it gets retried, but we inject the
                # auditor's feedback into the task description so the worker
                # sees why it was rejected.
                task["description"] += f"\n\n⚠️ AUDIT REJECTION: {feedback}"
                self.queue.mark_failed(task["id"], f"AUDIT_REJECT: {feedback}")
                return False
        except Exception as e:
            self._process_worker_failure(task, str(e),
                                         getattr(worker, "last_code", ""),
                                         worker)
            self.log.error(f"task {task['id']} exception: {e}", exc_info=True)
            return False

    def _process_worker_failure(self, task: dict, reason: str,
                                previous_code: str = "", worker=None) -> str:
        """Feedback loop T2: costruisce il prompt di correzione e riarma
        il task fino a 3 retry; il 4° fallimento lo rende definitivo.

        Returns:
            nuovo status ('pending' | 'failed_definitively').
        """
        correction = build_correction_prompt(
            original_task=f"{task.get('title', '')}\n{task.get('description', '')}",
            previous_code=previous_code,
            stderr=reason,
        )
        status = self.queue.fail_with_correction(
            task["id"], reason, correction,
            cooldown_sec=getattr(self, "retry_cooldown_sec", 30),
        )
        if status == self.queue.STATUS_FINAL:
            self.log.error(
                f"task {task['id']} FAILED_DEFINITIVELY after "
                f"{self.queue.RETRY_LIMIT + 1} attempts"
            )
            # 🆕 Rollback all'ultima configurazione LLM nota come buona,
            # per evitare di restare bloccati con parametri che producono loop.
            mk = worker.model_key if worker else None
            if mk:
                good = last_good_config.load(mk)
                if good:
                    self.models.models_cfg[mk].update(good)
                    self.log.info(
                        f"task {task['id']} rollback a ultima config buona "
                        f"per {mk}: {good}"
                    )
                else:
                    self.log.warning(
                        f"task {task['id']} nessun last-good config per {mk}, "
                        f"rollback saltato"
                    )
            # Alzare la posta in gioco: suggerisci un LLM più potente.
            try:
                import json as _json
                actors = Path(self.config["paths"]["project_root"]).parent \
                    / "CONFIG" / "actors.json"
                llm_w = "medium"
                if actors.exists():
                    llm_w = (_json.loads(actors.read_text(encoding="utf-8"))
                             .get("llm", {}).get("weight", "medium"))
                tip = suggest_escalation(llm_w)
                if tip:
                    self.queue.update_task(task["id"], reason=tip)
                    self.log.info(f"task {task['id']} escalation: {tip}")
            except Exception as _e:
                self.log.debug(f"suggerimento escalation non salvato: {_e}")
        else:
            self.log.warning(
                f"task {task['id']} -> {status} "
                f"(retry con prompt di correzione)"
            )
        return status

    def _ensure_avvio_script(self) -> None:
        """Flusso utente 3: garantisce che il progetto generato abbia un
        avvio. Se l'LLM non ha scritto avvia.sh, lo genera dal contenuto:
        main.py/app.py/primo .py → venv+python; Makefile → make; *.c → gcc.
        Non sovrascrive mai un avvia.sh esistente (quello dell'LLM vince).
        """
        try:
            from CORE.constants import weight_default_model  # noqa: F401 (coerenza import)
            proj = Path(self.config["paths"]["project_root"])
            avvio = proj / "avvia.sh"
            if avvio.exists():
                return                      # quello dell'LLM vince
            entry = None
            for name in ("main.py", "app.py"):
                if (proj / name).exists():
                    entry = name
                    break
            if entry is None:
                pys = [p for p in sorted(proj.glob("*.py"))
                       if not p.name.startswith("test_")]
                if pys:
                    entry = pys[0].name
            if entry:
                body = (
                    "#!/bin/bash\n"
                    'cd "$(dirname "$0")"\n'
                    "if [ -f requirements.txt ]; then\n"
                    "  [ -d .venv ] || python3 -m venv .venv\n"
                    "  .venv/bin/pip install -r requirements.txt\n"
                    "  PY=.venv/bin/python\n"
                    "else\n"
                    "  PY=python3\n"
                    "fi\n"
                    f'exec "$PY" {entry}\n'
                )
            elif (proj / "Makefile").exists():
                body = ('#!/bin/bash\n' 'cd "$(dirname "$0")"\n'
                        "make\n")
            elif c_files := list(proj.glob("*.c")):
                out = c_files[0].stem
                body = ('#!/bin/bash\n' 'cd "$(dirname "$0")"\n'
                        f"gcc {c_files[0].name} -o {out} && ./{out}\n")
            else:
                return                      # nulla di eseguibile riconosciuto
            avvio.write_text(body, encoding="utf-8")
            avvio.chmod(0o755)
            self.log.info(f"[flusso 3] generato avvia.sh (entry={entry or 'build'})")
        except Exception as e:
            self.log.warning(f"avvia.sh non generato: {e}")

    # ------------------------------------------------------------------
    # Routing e decisioni
    # ------------------------------------------------------------------

    def _needs_planning(self, task: dict) -> bool:
        """Heuristic: serve il planner?
        - task con 'complex' o 'multi' nella descrizione
        - task senza keyword dirette
        - task con parent None (root task)
        """
        # I sottotask non vengono ri-pianificati
        if task.get("parent") is not None:
            return False

        text = (task.get("title", "") + " " + task.get("description", "")).lower()
        direct = []
        for kws in self.config["routing"]["direct_keywords"].values():
            direct.extend(kws)
        if any(kw in text for kw in direct):
            return False

        # Parole che indicano complessità
        if any(w in text for w in ["complesso", "multi", "sistema", "architettura", "più file"]):
            return True

        # Default: pianifica
        return True

    def _select_worker(self, task: dict) -> str:
        """Seleziona il modello worker in base alle keyword."""
        text = (task.get("title", "") + " " + task.get("description", "")).lower()
        coder_kw = self.config["routing"]["direct_keywords"]["worker_coder"]
        if any(kw in text for kw in coder_kw):
            return "worker_coder"
        return "worker_general"

    def _build_worker(self, task_id: str, model_key: str) -> Worker:
        agent_id = f"worker-{model_key}"
        if agent_id not in self.memories:
            self.memories[agent_id] = AgentMemory(
                agent_id=agent_id,
                state_dir=Path(self.config["paths"]["state_dir"]),
                model_client=self.models,
                logger=self.log,
            )
        return Worker(
            agent_id=agent_id,
            model_key=model_key,
            tools=self.tools,
            memory=self.memories[agent_id],
            model_client=self.models,
            logger=self.log,
        )

    # ------------------------------------------------------------------
    # Safety e maintenance
    # ------------------------------------------------------------------

    def _check_resources(self) -> bool:
        """Verifica RAM e disco disponibili."""
        # RAM via /proc/meminfo (Linux)
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                k, _, v = line.partition(":")
                info[k.strip()] = int(v.strip().split()[0]) * 1024  # bytes
            total = info.get("MemTotal", 1)
            avail = info.get("MemAvailable", 0)
            ratio = 1 - (avail / total)
            if ratio > self.config["safety"]["swap_threshold"]:
                self.log.warning(f"RAM pressure: {ratio*100:.0f}% used, pausing")
                return False
        except Exception:
            pass  # non-Linux, skip

        # Disco
        try:
            stat = os.statvfs(self.config["paths"]["project_root"])
            free = stat.f_bavail * stat.f_frsize
            if free < self.config["safety"]["disk_free_threshold"]:
                self.log.warning(f"disk low: {free/1e9:.2f} GB free, pausing")
                return False
        except Exception:
            pass

        return True

    def _health_check(self) -> None:
        """Verifica che Ollama sia vivo."""
        if not self.models.is_available():
            self.log.error("Ollama unreachable! Tasks will fail.")
        # Verifica heartbeat agenti (in futuro con worker paralleli)

    def _backup(self) -> None:
        """Backup completo del progetto (tar.gz)."""
        ts = int(time.time())
        backup_path = Path(self.config["paths"]["backups_dir"]) / f"backup-{ts}.tar.gz"
        project_root = Path(self.config["paths"]["project_root"])
        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in project_root.iterdir():
                    if item.name == ".git":
                        continue
                    tar.add(item, arcname=item.name)
            self.log.info(f"backup saved: {backup_path}")
            # Mantieni solo gli ultimi 7 backup
            backups = sorted(Path(self.config["paths"]["backups_dir"]).glob("backup-*.tar.gz"))
            for old in backups[:-7]:
                old.unlink()
        except Exception as e:
            self.log.error(f"backup failed: {e}")

    def _init_git(self) -> None:
        """Inizializza git nel project_root se non già fatto."""
        project = Path(self.config["paths"]["project_root"])
        git_dir = project / ".git"
        if not git_dir.exists():
            try:
                import subprocess
                subprocess.run(["git", "init"], cwd=str(project),
                              capture_output=True, timeout=10)
                # Config minima
                subprocess.run(["git", "config", "user.email", "ai@civ.local"],
                              cwd=str(project), capture_output=True)
                subprocess.run(["git", "config", "user.name", "BYTE-SWARMY"],
                              cwd=str(project), capture_output=True)
                self.log.info("git initialized in project_root")
            except Exception as e:
                self.log.warning(f"git init failed: {e}")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # 🆕 Swarm command handlers (no LLM needed)
    # ------------------------------------------------------------------

    def _handle_swarm_command(self, task: dict, intent: str) -> str:
        """Gestisce direttamente i comandi swarm senza usare il worker LLM.
        Ritorna il risultato testuale da salvare come result del task.
        """
        try:
            if intent == "swarm_status":
                return self._cmd_swarm_status()
            elif intent == "swarm_time":
                return self._cmd_swarm_time()
            elif intent == "list_tasks":
                return self._cmd_list_tasks()
            elif intent == "show_logs":
                return self._cmd_show_logs()
            elif intent == "pause_swarm":
                return self._cmd_pause_swarm()
            elif intent == "resume_swarm":
                return self._cmd_resume_swarm()
            elif intent == "inspect_memory":
                return self._cmd_inspect_memory()
            elif intent == "cancel_task":
                return self._cmd_cancel_task(task)
            elif intent == "run_audit":
                return self._cmd_run_audit()
            else:
                return f"unknown swarm command: {intent}"
        except Exception as e:
            self.log.error(f"swarm command {intent} failed: {e}")
            return f"ERROR: {e}"

    def _cmd_swarm_status(self) -> str:
        """Stato completo dello swarm."""
        stats = self.queue.stats()
        models_loaded = self.models.list_models()
        timestral_state = "n/a"
        if self.timestral:
            advice = self.timestral.get_advice()
            timestral_state = advice.action
            if advice.sample:
                timestral_state += f" (CPU {advice.sample.cpu_temp_max:.0f}°C, load {advice.sample.cpu_load*100:.0f}%)"

        lines = [
            "🐝 BYTE-SWARMY Status",
            "=" * 40,
            f"Coda task: {stats}",
            f"Modelli Ollama disponibili: {len(models_loaded)}",
            f"Modello attivo: {self.models.current_model or 'nessuno'}",
            f"Stato timestral: {timestral_state}",
            f"Agenti in memoria: {len(self.memories)}",
            f"Running: {self.running}",
        ]
        return "\n".join(lines)

    def _cmd_swarm_time(self) -> str:
        """Risponde a 'che ore sono / data' senza LLM (swarm command diretto)."""
        from datetime import datetime
        now = datetime.now()
        giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
        mesi = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
                "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
        return (f"🕐 {now.strftime('%H:%M:%S')}\n"
                f"📅 {giorni[now.weekday()]} {now.day} {mesi[now.month-1]} {now.year}")
        """Lista tutti i task nella coda."""
        tasks = self.queue.get_all_tasks()
        if not tasks:
            return "Nessun task nella coda."

        lines = [f"📋 Coda task ({len(tasks)} totali):", "=" * 60]
        for t in tasks[:20]:  # max 20
            status_icon = {
                "pending": "⏳", "running": "▶", "done": "✓",
                "retry": "🔄", "stuck": "⛔", "planned": "📝",
                "needs_human": "👤"
            }.get(t.get("status", ""), "?")
            lines.append(f"{status_icon} [{t['status']:10}] {t['id']} | {t.get('title', '')[:50]}")
        return "\n".join(lines)

    def _cmd_show_logs(self) -> str:
        """Ultime 30 righe di log."""
        try:
            log_file = Path(self.config["logging"]["file"])
            if not log_file.exists():
                return "Log file non trovato."
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            # Filtra timestral (troppo verboso)
            filtered = [l for l in lines if "timestral" not in l.lower()][-30:]
            return "📜 Ultimi log:\n" + "\n".join(filtered)
        except Exception as e:
            return f"ERROR reading logs: {e}"

    def _cmd_pause_swarm(self) -> str:
        """Mette in pausa lo swarm."""
        self.running = False
        return "⏸ Swarm messo in pausa. Usa 'resume swarm' per riprendere."

    def _cmd_resume_swarm(self) -> str:
        """Riprende lo swarm."""
        self.running = True
        return "▶ Swarm ripreso."

    def _cmd_inspect_memory(self) -> str:
        """Ispeziona memoria agenti."""
        if not self.memories:
            return "Nessun agente ha memoria attiva."

        lines = ["🧠 Memoria agenti:", "=" * 40]
        for agent_id, mem in self.memories.items():
            try:
                history = mem.get_history() if hasattr(mem, 'get_history') else []
                lines.append(f"\n{agent_id}:")
                lines.append(f"  Eventi: {len(history)}")
                if history:
                    last = history[-1] if history else {}
                    lines.append(f"  Ultimo: {last.get('type', '?')} - {str(last.get('content', ''))[:80]}")
            except Exception as e:
                lines.append(f"  ERROR: {e}")
        return "\n".join(lines)

    def _cmd_cancel_task(self, task: dict) -> str:
        """Cancella un task (quello corrente o specificato nel context)."""
        # Estrai task_id dal context se presente
        import json
        target_id = None
        try:
            ctx = json.loads(task.get("context", "{}"))
            target_id = ctx.get("params", {}).get("task_id")
        except Exception:
            pass

        if not target_id:
            # Cancella tutti i task pending
            try:
                with self.queue._get_conn() as conn:
                    cur = conn.execute("DELETE FROM tasks WHERE status = 'pending'")
                    deleted = cur.rowcount
                    conn.commit()
                return f"🗑 Cancellati {deleted} task pending."
            except Exception as e:
                return f"ERROR: {e}"
        else:
            try:
                with self.queue._get_conn() as conn:
                    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (target_id,))
                    conn.commit()
                if cur.rowcount > 0:
                    return f"🗑 Task {target_id} cancellato."
                else:
                    return f"⚠ Task {target_id} non trovato."
            except Exception as e:
                return f"ERROR: {e}"

    def _cmd_run_audit(self) -> str:
        """Esegue un audit veloce del progetto."""
        try:
            project_root = Path(self.config["paths"]["project_root"])
            files = list(project_root.rglob("*.py"))
            total_lines = 0
            for f in files:
                try:
                    total_lines += sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
                except Exception:
                    pass

            lines = [
                "🔍 Audit progetto:",
                "=" * 40,
                f"File Python: {len(files)}",
                f"Linee totali: {total_lines}",
                f"Directory: {project_root}",
            ]
            if files:
                lines.append("\nFile:")
                for f in files[:10]:
                    lines.append(f"  - {f.relative_to(project_root)}")
                if len(files) > 10:
                    lines.append(f"  ... e altri {len(files) - 10}")
            return "\n".join(lines)
        except Exception as e:
            return f"ERROR: {e}"



    def _extract_swarm_intent(self, task: dict) -> str:
        """Estrae l'intent swarm dal task context, se presente."""
        try:
            import json
            ctx_raw = task.get("context", "")
            if not ctx_raw:
                return None
            ctx = json.loads(ctx_raw)
            intent = ctx.get("intent")
            swarm_intents = {
                "swarm_status", "list_tasks", "show_logs", "pause_swarm",
                "resume_swarm", "inspect_memory", "cancel_task", "run_audit",
                "swarm_time",
            }
            return intent if intent in swarm_intents else None
        except (json.JSONDecodeError, TypeError):
            return None

    def _handle_signal(self, signum, frame) -> None:
        self.log.info(f"signal {signum} received, shutting down...")
        self.running = False

    def _shutdown(self) -> None:
        self.log.info("stopping scheduler...")
        if getattr(self, "scheduler", None):
            self.scheduler.stop()   # Event.set: non usa join aggressivo
        self.log.info("stopping timestral...")
        if self.timestral:
            self.timestral.stop()
        self.log.info("unloading models...")
        self.models.unload_all()
        self.log.info("=== BYTE-SWARMY swarm stopped ===")


# ====================================================================
# ENTRY POINT
# ====================================================================

_OUT = sys.stdout


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "CONFIG/config.toml"
    orch = Orchestrator(config_path)
    orch.run()


if __name__ == "__main__":
    logging.basicConfig(stream=_OUT, format="%(message)s", level=logging.INFO)
    main()
