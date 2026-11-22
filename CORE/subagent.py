"""
CORE/subagent.py — registry deterministico di subagent a un solo livello.

Un subagent è un `Worker` con `agent_id`, `AgentMemory` e `model_key` propri,
creato da un worker padre per un sotto-task delimitato. Il modulo:

- valida il modello richiesto contro `[models.*]` del config (nessun ruolo nuovo
  inventato al volo);
- vieta l'annidamento (profondità max 1) e limita il numero di figli;
- non chiama MAI l'LLM in fase di costruzione: il figlio gira solo quando
  `run()`/`get_subagent_report()` lo richiede, con cap wall-clock;
- applica i gate termico (≤60 °C) e `state/pause.flag` prima di ogni run.

I test usano `temp_fn` e `runner` iniettati: zero LLM, zero rete.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

MAX_DEPTH = 1
MAX_CHILDREN = 4
MAX_TOTAL = 32
MAX_TASK_CHARS = 4000
TEMP_LIMIT = 60.0
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
EXCLUDED_MODELS = frozenset({"orchestrator", "planner", "embedding"})


def read_max_temp() -> float | None:
    """Temperatura massima letta dai sensori sysfs (None se non disponibile)."""
    values = []
    for sensor in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            values.append(float(sensor.read_text().strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    return max(values) if values else None


class SubagentRegistry:
    """Registry locale di figli: creazione, esecuzione limitata, report."""

    def __init__(self, config: dict, model_client, logger,
                 temp_fn: Callable[[], float | None] | None = None,
                 pause_file: Path | None = None,
                 runner: Callable | None = None):
        self.config = config
        self.models = model_client
        self.log = logger
        self.temp_fn = temp_fn or read_max_temp
        state = config.get("paths", {}).get("state_dir", "state")
        self.pause_file = Path(pause_file or Path(state) / "pause.flag")
        self.runner = runner
        self._children: dict[str, list[str]] = {}
        self._records: dict[str, dict] = {}

    def model_keys(self) -> set[str]:
        """Ruoli modello utilizzabili come subagent (solo worker esistenti)."""
        return {
            key for key, value in self.config.get("models", {}).items()
            if isinstance(value, dict) and value.get("name")
            and key not in EXCLUDED_MODELS
        }

    def spawn(self, parent_id: str, model_key: str, task: str,
              depth: int = 0) -> str:
        """Crea un figlio senza eseguirlo. Ritorna il suo agent_id."""
        if not isinstance(parent_id, str) or not SAFE_ID.fullmatch(parent_id):
            return "ERROR: parent_id non valido ([A-Za-z0-9_-], 1-64 caratteri)."
        if not isinstance(model_key, str) or model_key not in self.model_keys():
            valid = ", ".join(sorted(self.model_keys()))
            return f"ERROR: modello '{model_key}' non valido. Disponibili: {valid}."
        if not isinstance(task, str) or not task.strip():
            return "ERROR: task del subagent vuoto."
        if len(task) > MAX_TASK_CHARS:
            return f"ERROR: task troppo lungo (>{MAX_TASK_CHARS} caratteri)."
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
            return "ERROR: profondità non valida."
        if depth >= MAX_DEPTH:
            return f"ERROR: annidamento vietato (profondità max {MAX_DEPTH})."
        if len(self._children.get(parent_id, [])) >= MAX_CHILDREN:
            return f"ERROR: limite di {MAX_CHILDREN} figli per agente raggiunto."
        if len(self._records) >= MAX_TOTAL:
            return f"ERROR: limite globale di {MAX_TOTAL} subagent raggiunto."

        agent_id = f"sub-{parent_id}-{uuid.uuid4().hex[:8]}"
        try:
            worker = self._build_worker(agent_id, model_key)
        except Exception as e:
            return f"ERROR: creazione subagent fallita: {e}"

        self._records[agent_id] = {
            "agent_id": agent_id, "parent": parent_id, "model_key": model_key,
            "task": task.strip(), "depth": depth, "worker": worker,
            "status": "pending", "report": None,
            "created": time.strftime("%Y%m%d-%H%M%S"),
        }
        self._children.setdefault(parent_id, []).append(agent_id)
        return (f"OK: subagent '{agent_id}' creato (modello {model_key}, "
                f"profondità {depth}). "
                f"Usa get_subagent_report('{agent_id}') per eseguirlo e "
                f"ottenere il report.")

    def _build_worker(self, agent_id: str, model_key: str):
        """Costruisce Worker + AgentMemory + ToolSet senza chiamare l'LLM."""
        from CORE.memory import AgentMemory
        from CORE.tools import ToolSet
        from CORE.worker import Worker

        state = Path(self.config.get("paths", {}).get("state_dir", "state"))
        state.mkdir(parents=True, exist_ok=True)
        memory = AgentMemory(agent_id=agent_id, state_dir=state,
                             model_client=self.models, logger=self.log)
        tools = ToolSet(self.config, self.log)
        return Worker(agent_id=agent_id, model_key=model_key, tools=tools,
                      memory=memory, model_client=self.models, logger=self.log)

    def _gate(self) -> str | None:
        """Blocco termico / pause. Ritorna il motivo oppure None."""
        if self.pause_file.exists():
            return "BLOCKED: state/pause.flag presente, run subagent sospeso."
        try:
            temp = self.temp_fn()
        except Exception as e:
            return f"BLOCKED: temperatura non verificata ({e})."
        if temp is None:
            return "BLOCKED: temperatura non rilevata, run subagent sospeso."
        if temp > TEMP_LIMIT:
            return (f"BLOCKED: {temp:.1f}°C supera il limite di "
                    f"{TEMP_LIMIT:.0f}°C.")
        return None

    def _invoke(self, record: dict, timeout: int) -> str:
        """Esegue il figlio con cap wall-clock, restituendo il report."""
        task = {"id": record["agent_id"],
                "title": record["task"][:80],
                "description": record["task"]}
        holder = {"out": None, "exc": None}

        def target():
            try:
                if self.runner is not None:
                    holder["out"] = self.runner(record["worker"], task)
                else:
                    holder["out"] = record["worker"].execute(task)
            except Exception as e:  # noqa: BLE001 - report come testo, mai sollevare
                holder["exc"] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(max(1, int(timeout)))
        if thread.is_alive():
            return f"TIMEOUT: subagent '{record['agent_id']}' oltre {timeout}s."
        if holder["exc"] is not None:
            return f"ERROR: subagent fallito: {holder['exc']}"
        return str(holder["out"] or "")

    def run(self, agent_id: str, timeout: int = 60) -> str:
        """Esegue un figlio creato, rispettando i gate. Idempotente su done."""
        record = self._records.get(str(agent_id).strip())
        if record is None:
            return f"ERROR: subagent '{agent_id}' non trovato."
        if record["status"] == "done":
            return record["report"]
        blocked = self._gate()
        if blocked:
            return blocked
        report = self._invoke(record, timeout)
        record["report"] = report
        record["status"] = ("done" if report.startswith("OK")
                            or not report.startswith(("TIMEOUT", "ERROR", "BLOCKED"))
                            else "failed")
        return report

    def get_report(self, agent_id: str) -> str:
        """Report del figlio; se pending lo esegue prima di rispondere."""
        record = self._records.get(str(agent_id).strip())
        if record is None:
            return f"ERROR: subagent '{agent_id}' non trovato."
        if record["status"] == "pending":
            return self.run(agent_id)
        return record["report"]

    def list_agents(self) -> str:
        """Elenco testuale dei figli con stato e modello."""
        if not self._records:
            return "Nessun subagent creato."
        lines = [f"SUBAGENT ({len(self._records)}):"]
        for agent_id, rec in sorted(self._records.items()):
            lines.append(f"  {agent_id} · {rec['model_key']} · "
                         f"{rec['status']} · {rec['created']}")
        return "\n".join(lines)
