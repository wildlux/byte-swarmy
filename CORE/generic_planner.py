"""
CORE/generic_planner — Decompone task generici in Code task atomici.

Estratto da CORE/orchestrator.py per ridurre il monolite.

Usa il decision model attivo per decomporre un 'Generic Task' in una lista
di Code task da aggiungere alla coda come sottotask.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from CORE.constants import DEFAULT_NUM_CTX
from CORE.ollama_client import ModelClient
from CORE.regex_controller import DEFAULT_PATTERNS, RegexController, json_block

log = logging.getLogger("byte-swarmy.generic_planner")

_REGEX = RegexController(DEFAULT_PATTERNS)


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

    def ask_verdict(self, prompt: str):
        """Parere del decision model sul prompt (per il preflight di
        DecisionValidator). Ritorna {"valid": bool, "reason": str} o None
        se non configurato/irraggiungibile (non blocca l'accodamento).
        """
        model_cfg = self._get_active_model()
        if not model_cfg:
            return None
        model_name = model_cfg.get("name", "tev1:4b")
        system = ('Sei un validatore di task. Rispondi SOLO con JSON '
                  'compatto: {"valid": true} oppure '
                  '{"valid": false, "reason": "<motivo breve>"}')
        try:
            raw = self._call_decision_model(
                model_name, prompt, system,
                temperature=0.1,
                num_ctx=int(model_cfg.get("num_ctx", 2048)),
                max_tokens=64,
            )
        except Exception as e:
            log.warning(f"[preflight] decision model non raggiungibile: {e}")
            return None
        m = _REGEX.search("json_object", raw)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            log.warning(f"[preflight] decision model no JSON: {raw[:120]}")
            return None
        return data if isinstance(data, dict) else None

    def _get_active_model(self) -> dict:
        """Ritorna la config del decision model attivo, o None."""
        active_key = self.decision_cfg.get("active", "tev1")
        model_cfg = self.decision_cfg.get(active_key)
        if not model_cfg or not model_cfg.get("enabled", False):
            # Fallback: cerca qualsiasi decision model abilitato
            for k, v in self.decision_cfg.items():
                if isinstance(v, dict) and v.get("enabled", False) and k != "active":
                    log.info(f"[generic-planner] active model '{active_key}' "
                             f"disabled, fallback to '{k}'")
                    return v
            return None
        return model_cfg

    def decompose(self, generic_task: dict) -> list:
        """Decompone un Generic Task in Code task.

        Ritorna una lista di dict pronti da aggiungere alla coda come sottotask.
        """
        if not self.is_enabled():
            log.warning("[generic-planner] disabled or no decision model available")
            return []

        model_cfg = self._get_active_model()
        model_name = model_cfg.get("name", "tev1:4b")
        max_subtasks = self.planner_cfg.get("max_subtasks", 8)
        max_tokens = self.planner_cfg.get("max_tokens", 1500)
        system_prompt = self.planner_cfg.get("system_prompt", "")

        # Costruisci prompt utente
        user_prompt = self._build_user_prompt(generic_task)

        log.info(f"[generic-planner] calling decision model {model_name}")

        try:
            # Chiama direttamente via API Ollama (non usa ModelClient.call perché
            # il decision model non è in [models.*])
            raw = self._call_decision_model(
                model_name=model_name,
                prompt=user_prompt,
                system=system_prompt,
                temperature=model_cfg.get("temperature", 0.1),
                num_ctx=model_cfg.get("num_ctx", DEFAULT_NUM_CTX),
                max_tokens=max_tokens,
            )
        except Exception as e:
            log.error(f"[generic-planner] model call failed: {e}")
            return []

        log.debug(f"[generic-planner] raw response: {raw[:500]!r}")

        # Parse della risposta JSON
        subtasks = self._parse_response(raw, generic_task, max_subtasks)
        log.info(f"[generic-planner] decomposed into {len(subtasks)} code tasks")
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
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/chat", data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("message", {}).get("content", "").strip()

    def _parse_response(self, raw: str, parent_task: dict, max_subtasks: int) -> list:
        """Parse della risposta JSON del decision model.
        Supporta sia lista che dict con chiave 'subtasks'/'tasks'."""
        # Estrai blocco JSON (array o oggetto)
        blob = json_block(raw)
        if not blob:
            log.warning(f"[generic-planner] no JSON in response: {raw[:200]}")
            return []
        try:
            data = json.loads(blob)
        except json.JSONDecodeError as e:
            log.error(f"[generic-planner] JSON parse error: {e}")
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
                "created_at": time.time(),
                "source": f"generic:{parent_task['id']}",
                "project_path": parent_task.get("project_path"),
            })
        return result
