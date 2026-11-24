"""Cycle 147 — A/B: il contesto iniziale non eredita i run precedenti.

Nessun LLM, rete o GPU: modello scriptato. Verifica che `working`, letto da
`AgentMemory.build_context()`, venga azzerato insieme a `long_term` e
`short_term` prima della prima chiamata al modello.
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.memory import AgentMemory  # noqa: E402
from CORE.orchestrator import Worker  # noqa: E402
from CORE.tools import ToolSet  # noqa: E402

logger = logging.getLogger("test-context-reset")


class _CapturingModel:
    """Modello scriptato che registra i prompt ricevuti."""

    def __init__(self, actions: list):
        self.actions = actions
        self.prompts: list[str] = []
        self.i = 0

    def call_streaming(self, **kwargs):
        self.prompts.append(kwargs.get("prompt", ""))
        if self.i < len(self.actions):
            out = json.dumps(self.actions[self.i])
            self.i += 1
            return out
        return json.dumps({"thought": "finito", "action": "none",
                           "args": [], "done": True, "result": "DONE-OK"})

    def call(self, **kwargs):
        return next(iter(self.call_streaming(**kwargs)), "")


class TestContextReset(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-ctx-"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        (self.tmp / "state").mkdir()
        cfg = {
            "paths": {"project_root": str(self.project),
                      "state_dir": str(self.tmp / "state")},
            "routing": {"max_file_size_readable": 50_000, "timeout_bash": 5},
            "security": {"enabled": True, "max_output_chars": 5_000,
                         "max_file_size_write": 200_000,
                         "max_file_size_bytes": 2_000_000,
                         "max_memory_mb": 256},
        }
        self.tools = ToolSet(cfg, logger)

    def test_reset_azzera_working_e_long_term(self):
        memory = AgentMemory("ctx-reset", self.tmp / "state", None, logger)
        memory.working.append({"type": "max_steps_reached", "content": "stale"})
        memory.long_term.append({"summary": "fallback_done di un run vecchio"})
        memory.add_event({"type": "thought", "content": "tool allucinato"})

        worker = Worker("ctx-reset", "worker_coder", self.tools, memory,
                        _CapturingModel([]), logger)
        worker._reset_task_memory()

        self.assertEqual(memory.working, [])
        self.assertEqual(memory.long_term, [])
        ctx = memory.build_context(max_tokens=800)
        self.assertNotIn("max_steps_reached", ctx)
        self.assertNotIn("fallback_done", ctx)
        self.assertNotIn("allucinato", ctx)

    def test_prompt_iniziale_non_contiene_eventi_del_run_precedente(self):
        memory = AgentMemory("ctx-prompt", self.tmp / "state", None, logger)
        memory.working.extend([
            {"type": "parse_error", "content": "JSON non valido precedente"},
            {"type": "max_steps_reached", "content": ""},
            {"type": "circuit_breaker_stop",
             "content": "write_file bloccato dopo 3 tentativi"},
        ])
        model = _CapturingModel([
            {"thought": "faccio il task", "action": "none", "args": [],
             "done": True, "result": "OK"},
        ])
        worker = Worker("ctx-prompt", "worker_coder", self.tools, memory,
                        model, logger)
        worker.execute({"id": "ctx-1", "title": "contesto pulito",
                        "description": "nessuna eredità da run precedenti"})

        self.assertTrue(model.prompts, "nessuna chiamata al modello")
        initial = model.prompts[0]
        for stale in ("parse_error", "max_steps_reached",
                      "circuit_breaker_stop", "JSON non valido precedente"):
            self.assertNotIn(stale, initial)


if __name__ == "__main__":
    unittest.main()
