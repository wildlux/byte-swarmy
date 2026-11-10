"""
CORE/planner.py — Decompone task complessi in sottotask atomici.

Estratto da CORE/orchestrator.py per ridurre il monolite.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List

from CORE.ollama_client import ModelClient
from CORE.regex_controller import DEFAULT_PATTERNS, RegexController

log = logging.getLogger("byte-swarmy.planner")

_REGEX = RegexController(DEFAULT_PATTERNS)


class Planner:
    """Decompone un task in sottotask. Usa il modello planner (phi3:mini)."""

    SYSTEM = (
        "You are a software planner. Decompose the task into 2-5 atomic, "
        "sequential subtasks. Each subtask must be implementable in at most "
        "200 lines of code. Reply with JSON ONLY:\n"
        '{"subtasks": [{"title": "...", "description": "...", "type": "implement|test|fix"}]}\n'
        "No text outside the JSON."
    )

    # Costituzione dell'Agente Worker: regole ferree di sicurezza e qualità.
    # Versione compatta per modelli piccoli (3-4B su CPU).
    WORKER_CONSTRAINTS = (
        "RULES:\n"
        "1. Work only inside project/ directory.\n"
        '2. Use ONLY the tools listed in TOOLS section. In "action" write the '
        'exact tool NAME (e.g. "write_file"): never "tool".\n'
        "3. write_file(path, content) to CREATE files.\n"
        "4. patch_code(path, old_string, new_string) to MODIFY files.\n"
        "5. After writing, run run_test_suite() to verify.\n"
        "6. When done: set done=true with a short result string.\n"
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
        m = _REGEX.search("json_object", raw)
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
                    "project_path": parent_task.get("project_path"),
                })
            return result
        except json.JSONDecodeError as e:
            self.log.error(f"planner: JSON parse error: {e}")
            return []
