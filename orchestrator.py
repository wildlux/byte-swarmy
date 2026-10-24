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

# Python 3.11+ ha tomllib, fallback a tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("ERROR: serve Python 3.11+ o `pip install tomli`")
        sys.exit(1)

from tools import ToolSet
from memory import AgentMemory
from ollama_client import ModelClient
from thermal_manager import TimestralManager


# ====================================================================
# LOGGER
# ====================================================================

def setup_logger(config) -> logging.Logger:
    log_cfg = config.get("logging", {})
    log_file = log_cfg.get("file", "./logs/byte-swarmy.log")
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

    return logger


# ====================================================================
# CONFIG LOADER
# ====================================================================

def load_config(path: str = "config.toml") -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


# ====================================================================
# TASK QUEUE (persistente su file)
# ====================================================================

class TaskQueue:
    """Coda task persistente. Un file JSON, semplice, ispezionabile."""

    def __init__(self, tasks_dir: Path, logger):
        self.dir = tasks_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "queue.json"
        self.log = logger
        self.tasks: list = self._load()

    def _load(self) -> list:
        if not self.file.exists():
            return []
        try:
            return json.loads(self.file.read_text())
        except Exception as e:
            self.log.error(f"corrupted queue, starting fresh: {e}")
            # backup del file corrotto
            if self.file.exists():
                self.file.rename(self.file.with_suffix(".corrupt.json"))
            return []

    def _save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.tasks, ensure_ascii=False, indent=2))
        tmp.replace(self.file)

    def add(self, task: dict) -> str:
        """Aggiunge un task. Ritorna l'id."""
        task_id = f"task-{int(time.time()*1000)}-{len(self.tasks)}"
        task.setdefault("id", task_id)
        task.setdefault("status", "pending")
        task.setdefault("attempts", 0)
        task.setdefault("created_at", time.time())
        task.setdefault("subtasks", [])
        task.setdefault("parent", None)
        self.tasks.append(task)
        self._save()
        self.log.info(f"queue: added {task_id} - {task.get('title', '')[:80]}")
        return task_id

    def next_pending(self) -> Optional[dict]:
        """Estrae il prossimo task in stato 'pending' o 'retry'."""
        for t in self.tasks:
            if t["status"] in ("pending", "retry"):
                t["status"] = "running"
                t["started_at"] = time.time()
                self._save()
                return t
        return None

    def mark_done(self, task_id: str, result: str) -> None:
        for t in self.tasks:
            if t["id"] == task_id:
                t["status"] = "done"
                t["result"] = result[:500]
                t["completed_at"] = time.time()
                self._save()
                return

    def mark_failed(self, task_id: str, reason: str) -> None:
        for t in self.tasks:
            if t["id"] == task_id:
                t["attempts"] = t.get("attempts", 0) + 1
                if t["attempts"] >= 10:
                    t["status"] = "stuck"
                    t["failure_reason"] = reason
                else:
                    t["status"] = "retry"
                    t["last_error"] = reason[:300]
                self._save()
                return

    def needs_human(self, task_id: str, reason: str) -> None:
        for t in self.tasks:
            if t["id"] == task_id:
                t["status"] = "needs_human"
                t["reason"] = reason
                self._save()
                return

    def stats(self) -> dict:
        counts = {}
        for t in self.tasks:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        return counts


# ====================================================================
# PLANNER — decompone task complessi
# ====================================================================

class Planner:
    """Decompone un task in sottotask. Usa il modello planner (phi3:mini)."""

    SYSTEM = (
        "Sei un pianificatore software. Decomponi il task in 2-5 sottotask "
        "atomici e sequenziali. Ogni sottotask deve essere implementabile in "
        "massimo 200 righe di codice. Rispondi SOLO in formato JSON:\n"
        '{"subtasks": [{"title": "...", "description": "...", "type": "implement|test|fix"}]}\n'
        "Niente testo fuori dal JSON."
    )

    def __init__(self, model_client: ModelClient, logger):
        self.models = model_client
        self.log = logger

    def decompose(self, task: dict) -> list:
        prompt = (
            f"TASK: {task.get('title', '')}\n\n"
            f"DESCRIZIONE: {task.get('description', '')}\n\n"
            f"CONTESTO PROGETTO: {task.get('context', 'nuovo progetto')}\n\n"
            "Decomponi in sottotask:"
        )

        try:
            raw = self.models.call(
                model_key="planner",
                prompt=prompt,
                system=self.SYSTEM,
                max_tokens=1024,
            )
            subtasks = self._parse_response(raw, task)
            self.log.info(f"planner: decomposed into {len(subtasks)} subtasks")
            return subtasks
        except Exception as e:
            self.log.error(f"planner failed: {e}")
            return []

    def _parse_response(self, raw: str, parent_task: dict) -> list:
        # Estrai il blocco JSON anche se circondato da ```json ... ```
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            self.log.warning(f"planner: no JSON in response: {raw[:200]}")
            return []
        try:
            data = json.loads(m.group(0))
            subs = data.get("subtasks", [])
            result = []
            for s in subs:
                result.append({
                    "id": f"{parent_task['id']}-sub-{len(result)+1}",
                    "title": s.get("title", ""),
                    "description": s.get("description", ""),
                    "type": s.get("type", "implement"),
                    "status": "pending",
                    "parent": parent_task["id"],
                    "attempts": 0,
                    "created_at": time.time(),
                })
            return result
        except json.JSONDecodeError as e:
            self.log.error(f"planner: JSON parse error: {e}")
            return []


# ====================================================================
# WORKER — esegue un singolo task
# ====================================================================

class Worker:
    """Esegue un task usando i tool e il modello LLM. Loop ReAct base."""

    SYSTEM = (
        "You are an autonomous coding agent. You have these tools:\n"
        "  read_file(path), write_file(path, content), run_bash(cmd),\n"
        "  git_commit(message), git_diff(rev),\n"
        "  search(pattern, glob), git_status(), git_log(n=10),\n"
        "  git_branch(action, name), git_merge(branch),\n"
        "  git_pull(remote, branch), git_push(remote, branch),\n"
        "  git_remote(action, name, url)\n\n"
        "Respond with ONE JSON object per turn, no other text:\n"
        '{"thought": "one line", "action": "tool_name", "args": ["arg1", "arg2"], "done": false}\n\n'
        "Rules:\n"
        "- action MUST be one of: read_file, write_file, run_bash, git_commit, git_diff, "
        "search, git_status, git_log, git_branch, git_merge, git_pull, git_push, git_remote\n"
        "- args MUST be a JSON array of strings\n"
        "- when the task is complete, set done=true and add a 'result' field\n"
        "- NEVER output text before or after the JSON\n"
        "- keep thought under 100 chars\n"
        "- ALWAYS save files under project/ (NOT in sourceCode/ or root)\n"
        "- before declaring done, run a test with run_bash if applicable"
    )

    MAX_STEPS = 12

    def __init__(self, agent_id: str, model_key: str,
                 tools: ToolSet, memory: AgentMemory,
                 model_client: ModelClient, logger):
        self.agent_id = agent_id
        self.model_key = model_key
        self.tools = tools
        self.memory = memory
        self.models = model_client
        self.log = logger

    def execute(self, task: dict) -> str:
        """Esegue un task. Ritorna il risultato testuale."""
        self.memory.reset_short_term()
        self.memory.add_event({
            "type": "task_start",
            "content": f"{task.get('title', '')}: {task.get('description', '')[:200]}",
        })

        # Costruisci prompt iniziale
        context = self.memory.build_context(max_tokens=1500)
        prompt = self._build_initial_prompt(task, context)

        wrote_file = False
        last_tool_result = ""

        for step in range(self.MAX_STEPS):
            self.memory.heartbeat()
            self.log.info(f"[{self.agent_id}] step {step+1}/{self.MAX_STEPS}")

            try:
                raw = self.models.call(
                    model_key=self.model_key,
                    prompt=prompt,
                    system=self.SYSTEM,
                    max_tokens=1024,
                )
            except Exception as e:
                self.log.error(f"[{self.agent_id}] model call failed: {e}")
                return f"ERROR: model unavailable: {e}"

            # Logga la risposta grezza per debug (primi 300 char)
            self.log.debug(f"[{self.agent_id}] raw response: {raw[:300]!r}")
            self.log.info(f"[{self.agent_id}] response: {raw[:200]}")

            action = self._parse_action(raw)
            if not action:
                self.memory.add_event({"type": "parse_error", "content": raw[:300]})
                # Riprova con un prompt più assertivo
                prompt = (
                    "ERRORE: la risposta non era JSON valido. "
                    "Rispondi con SOLO un oggetto JSON, niente testo prima o dopo.\n"
                    "Formato: {\"thought\": \"...\", \"action\": \"tool_name\", "
                    "\"args\": [...], \"done\": false}\n\n"
                    "Riprova ora:"
                )
                continue

            self.memory.add_event({"type": "thought", "content": action.get("thought", "")[:200]})

            if action.get("done"):
                result = action.get("result", "(no result)")
                self.memory.add_event({"type": "task_done", "content": result[:200]})
                return result

            # Esegui il tool
            tool_name = action.get("action")
            args = action.get("args", [])
            tool_result = self._call_tool(tool_name, args)

            if tool_name == "write_file" and tool_result.startswith("OK:"):
                wrote_file = True
            last_tool_result = tool_result

            self.memory.add_event({
                "type": "tool_result",
                "content": f"{tool_name}({args}) -> {tool_result[:200]}",
            })
            self.log.info(f"[{self.agent_id}] tool {tool_name}({args[:1] if args else ''}) -> {tool_result[:120]}")

            # Aggiungi al prompt per il prossimo step
            prompt = (
                f"Last action: {tool_name}({args})\n"
                f"Result:\n{tool_result[:2000]}\n\n"
                "Next step (JSON only):"
            )

        # FALLBACK: se abbiamo scritto almeno un file con successo, consideriamo done
        if wrote_file:
            self.log.info(f"[{self.agent_id}] max steps reached but file was written, declaring done")
            self.memory.add_event({"type": "fallback_done", "content": "file written but no explicit done"})
            return f"COMPLETED (fallback): file scritto. Ultimo risultato tool: {last_tool_result[:200]}"

        self.memory.add_event({"type": "max_steps_reached"})
        return "ERROR: max steps reached without completion"

    def _build_initial_prompt(self, task: dict, context: str) -> str:
        return (
            f"## TASK\n{task.get('title', '')}\n\n"
            f"## DESCRIPTION\n{task.get('description', '')}\n\n"
            f"## CONTEXT\n{context}\n\n"
            f"## PROJECT STATE\n{self._project_state()}\n\n"
            "Plan: 1) write_file to create the code, 2) run_bash to test/compile, "
            "3) git_commit, 4) done=true with result.\n\n"
            "First step (JSON only):"
        )

    def _project_state(self) -> str:
        """Snapshot veloce dello stato del progetto (file listing)."""
        try:
            r = self.tools.run_bash("find . -type f -not -path './.git/*' | head -20")
            return r[:1000]
        except Exception:
            return "(cannot read project state)"

    def _parse_action(self, raw: str) -> Optional[dict]:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

    def _call_tool(self, name: str, args: list) -> str:
        try:
            if name == "read_file":
                return self.tools.read_file(args[0])
            elif name == "write_file":
                return self.tools.write_file(args[0], args[1])
            elif name == "run_bash":
                return self.tools.run_bash(args[0])
            elif name == "git_commit":
                return self.tools.git_commit(args[0] if args else "auto")
            elif name == "git_diff":
                return self.tools.git_diff(args[0] if args else "HEAD~1")
            elif name == "search":
                return self.tools.search(args[0], args[1] if len(args) > 1 else "*")
            elif name == "git_status":
                return self.tools.git_status()
            elif name == "git_log":
                return self.tools.git_log(int(args[0]) if args else 10)
            elif name == "git_branch":
                return self.tools.git_branch(
                    args[0] if args else "list",
                    args[1] if len(args) > 1 else ""
                )
            elif name == "git_merge":
                return self.tools.git_merge(args[0] if args else "")
            elif name == "git_pull":
                return self.tools.git_pull(
                    args[0] if args else "origin",
                    args[1] if len(args) > 1 else ""
                )
            elif name == "git_push":
                return self.tools.git_push(
                    args[0] if args else "origin",
                    args[1] if len(args) > 1 else ""
                )
            elif name == "git_remote":
                return self.tools.git_remote(
                    args[0] if args else "list",
                    args[1] if len(args) > 1 else "",
                    args[2] if len(args) > 2 else ""
                )
            else:
                return f"ERROR: unknown tool '{name}'"
        except IndexError:
            return f"ERROR: missing args for {name}"
        except Exception as e:
            return f"ERROR: {e}"


# ====================================================================
# GENERIC TASK PLANNER — usa un decision model per decomporre task generici
# ====================================================================

class GenericTaskPlanner:
    """Usa il decision model attivo (d3, tev1, nimble, clef, etc.) per
    decomporre un 'Generic Task' in una lista di Code task atomici.

    Un Generic Task è un task con type='generic' o source='generic'.
    Il planner legge la descrizione (es. 'voglio un tool per fare X'),
    chiama il decision model, e produce 2-8 Code task.

    I Code task vengono aggiunti alla coda come sottotask del Generic Task.
    """

    def __init__(self, config: dict, model_client: ModelClient, logger):
        self.config = config
        self.models = model_client
        self.log = logger
        self.planner_cfg = config.get("generic_task_planner", {})
        self.decision_cfg = config.get("decision_models", {})

    def is_enabled(self) -> bool:
        return self.planner_cfg.get("enabled", False) and self._get_active_model() is not None

    def _get_active_model(self) -> dict:
        """Ritorna la config del decision model attivo, o None."""
        active_key = self.decision_cfg.get("active", "tev1")
        model_cfg = self.decision_cfg.get(active_key)
        if not model_cfg or not model_cfg.get("enabled", False):
            # Fallback: cerca qualsiasi decision model abilitato
            for k, v in self.decision_cfg.items():
                if isinstance(v, dict) and v.get("enabled", False) and k != "active":
                    self.log.info(f"[generic-planner] active model '{active_key}' "
                                  f"disabled, fallback to '{k}'")
                    return v
            return None
        return model_cfg

    def decompose(self, generic_task: dict) -> list:
        """Decompone un Generic Task in Code task.

        Ritorna una lista di dict pronti da aggiungere alla coda come sottotask.
        """
        if not self.is_enabled():
            self.log.warning("[generic-planner] disabled or no decision model available")
            return []

        model_cfg = self._get_active_model()
        model_name = model_cfg.get("name", "tev1:4b")
        max_subtasks = self.planner_cfg.get("max_subtasks", 8)
        max_tokens = self.planner_cfg.get("max_tokens", 1500)
        system_prompt = self.planner_cfg.get("system_prompt", "")

        # Costruisci prompt utente
        user_prompt = self._build_user_prompt(generic_task)

        self.log.info(f"[generic-planner] calling decision model {model_name}")

        try:
            # Chiama direttamente via API Ollama (non usa ModelClient.call perché
            # il decision model non è in [models.*])
            raw = self._call_decision_model(
                model_name=model_name,
                prompt=user_prompt,
                system=system_prompt,
                temperature=model_cfg.get("temperature", 0.1),
                num_ctx=model_cfg.get("num_ctx", 4096),
                max_tokens=max_tokens,
            )
        except Exception as e:
            self.log.error(f"[generic-planner] model call failed: {e}")
            return []

        self.log.debug(f"[generic-planner] raw response: {raw[:500]!r}")

        # Parse della risposta JSON
        subtasks = self._parse_response(raw, generic_task, max_subtasks)
        self.log.info(f"[generic-planner] decomposed into {len(subtasks)} code tasks")
        return subtasks

    def _build_user_prompt(self, task: dict) -> str:
        """Costruisce il prompt utente per il decision model."""
        title = task.get("title", "")
        description = task.get("description", "")
        context = task.get("context", "")
        return (
            f"## GENERIC TASK\n{title}\n\n"
            f"## DESCRIPTION\n{description}\n\n"
            f"## CONTEXT\n{context or '(none)'}\n\n"
            f"## PROJECT STATE\n{self._project_state()}\n\n"
            "Decompose this into atomic code tasks. Output JSON list only."
        )

    def _project_state(self) -> str:
        """Snapshot veloce: file nel project/."""
        try:
            project_root = Path(self.config["paths"]["project_root"])
            files = []
            for f in project_root.rglob("*"):
                if ".git" in f.parts:
                    continue
                if f.is_file():
                    files.append(str(f.relative_to(project_root)))
                if len(files) >= 30:
                    break
            return "\n".join(files) if files else "(empty project)"
        except Exception:
            return "(cannot read project state)"

    def _call_decision_model(self, model_name: str, prompt: str, system: str,
                              temperature: float, num_ctx: int,
                              max_tokens: int) -> str:
        """Chiama direttamente Ollama con il decision model specificato."""
        import urllib.request, json as _json
        host = self.config["ollama"]["host"].rstrip("/")
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": max_tokens,
            },
            "stream": False,
        }
        data = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/chat", data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        return data.get("message", {}).get("content", "").strip()

    def _parse_response(self, raw: str, parent_task: dict, max_subtasks: int) -> list:
        """Parse della risposta JSON del decision model.
        Supporta sia lista che dict con chiave 'subtasks'/'tasks'."""
        import json as _json, re
        # Estrai blocco JSON
        m = re.search(r"\[[\s\S]*\]", raw) or re.search(r"\{[\s\S]*\}", raw)
        if not m:
            self.log.warning(f"[generic-planner] no JSON in response: {raw[:200]}")
            return []
        try:
            data = _json.loads(m.group(0))
        except _json.JSONDecodeError as e:
            self.log.error(f"[generic-planner] JSON parse error: {e}")
            return []

        # Normalizza: estrai lista
        if isinstance(data, dict):
            if "subtasks" in data:
                items = data["subtasks"]
            elif "tasks" in data:
                items = data["tasks"]
            else:
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            return []

        # Limita e normalizza
        items = items[:max_subtasks]
        result = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            result.append({
                "id": f"{parent_task['id']}-sub-{i+1}",
                "title": str(item.get("title", f"Subtask {i+1}"))[:120],
                "description": str(item.get("description", "")),
                "type": item.get("type", "implement"),
                "priority": int(item.get("priority", 3)),
                "depends_on": item.get("depends_on", []),
                "status": "pending",
                "parent": parent_task["id"],
                "attempts": 0,
                "created_at": __import__("time").time(),
                "source": f"generic:{parent_task['id']}",
            })
        return result


# ====================================================================
# ORCHESTRATOR — il main loop
# ====================================================================

class Orchestrator:
    """Ciclo principale. Singolo processo, singolo thread."""

    def __init__(self, config_path: str = "config.toml"):
        self.config = load_config(config_path)
        self.log = setup_logger(self.config)

        # Crea directory necessarie
        for k in ("project_root", "state_dir", "tasks_dir", "logs_dir", "backups_dir"):
            Path(self.config["paths"][k]).mkdir(parents=True, exist_ok=True)

        # Inizializza git nel project_root se non già fatto
        self._init_git()

        # Componenti
        self.models = ModelClient(self.config, self.log)
        self.tools = ToolSet(self.config, self.log)
        self.queue = TaskQueue(Path(self.config["paths"]["tasks_dir"]), self.log)
        self.planner = Planner(self.models, self.log)
        self.generic_planner = GenericTaskPlanner(self.config, self.models, self.log)

        # Timestral (thermal manager) — opzionale
        self.timestral = None
        if self.config.get("thermal", {}).get("enabled", False):
            try:
                self.timestral = TimestralManager(
                    self.config, self.log,
                    base_dir=Path(self.config["paths"]["state_dir"]).parent,
                )
                self.timestral.start()
                self.log.info("[timestral] thermal monitoring enabled")
            except Exception as e:
                self.log.warning(f"[timestral] init failed: {e}")
                self.timestral = None

        # Memorie agenti (lazy create)
        self.memories: dict[str, AgentMemory] = {}

        # Timers (timestamps dell'ultima esecuzione)
        self.last_health_check = 0.0
        self.last_git_snapshot = 0.0
        self.last_memory_compaction = 0.0
        self.last_backup = 0.0

        # Shutdown flag
        self.running = True

        # Installa signal handler
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self.log.info("=== BYTE-SWARMY swarm started ===")
        self.log.info(f"models available: {self.models.list_models()}")
        self.log.info(f"queue stats: {self.queue.stats()}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

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

    def _tick(self) -> None:
        """Singolo tick del loop."""

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

        self.log.info(f"dispatching {task['id']}: {task.get('title', '')[:80]}")

        # 6a. Generic Task? Usa GenericTaskPlanner (decision model)
        if task.get("type") == "generic" or task.get("source", "").startswith("generic"):
            self.log.info(f"generic task {task['id']}: decomposing with decision model")
            if self.generic_planner.is_enabled():
                subtasks = self.generic_planner.decompose(task)
                if subtasks:
                    # Aggiungi sottotask alla coda
                    for st in subtasks:
                        self.queue.tasks.append(st)
                    self.queue._save()
                    # Marca il task generic come 'planned'
                    for t in self.queue.tasks:
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
                    self.queue.tasks.append(st)
                self.queue._save()
                # Marca il task parent come 'planned'
                for t in self.queue.tasks:
                    if t["id"] == task["id"]:
                        t["status"] = "planned"
                        t["subtask_ids"] = [s["id"] for s in subtasks]
                self.queue._save()
                return
            # Se il planner fallisce, esegui il task direttamente

        # 6c. Esegui con worker
        model_key = self._select_worker(task)
        worker = self._build_worker(task["id"], model_key)

        try:
            result = worker.execute(task)
            if result.startswith("ERROR"):
                self.queue.mark_failed(task["id"], result)
                self.log.warning(f"task {task['id']} failed: {result[:100]}")
            else:
                self.queue.mark_done(task["id"], result)
                self.tools.git_commit(f"task {task['id']}: {task.get('title', '')[:50]}")
                self.log.info(f"task {task['id']} DONE")
        except Exception as e:
            self.queue.mark_failed(task["id"], str(e))
            self.log.error(f"task {task['id']} exception: {e}", exc_info=True)

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

    def _handle_signal(self, signum, frame) -> None:
        self.log.info(f"signal {signum} received, shutting down...")
        self.running = False

    def _shutdown(self) -> None:
        self.log.info("stopping timestral...")
        if self.timestral:
            self.timestral.stop()
        self.log.info("unloading models...")
        self.models.unload_all()
        self.log.info("=== BYTE-SWARMY swarm stopped ===")


# ====================================================================
# ENTRY POINT
# ====================================================================

def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
    orch = Orchestrator(config_path)
    orch.run()


if __name__ == "__main__":
    main()
