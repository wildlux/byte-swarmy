# -*- coding: utf-8 -*-
"""A1 (2026-11-22): verità della verifica del `done` — test offline, zero LLM.

Le funzioni pure in `CORE/worker.py` classificano lo stato, applicano
l'override esplicito e costruiscono la riga tracciata nel report. Nessun
modello, nessuna rete, nessun file: chiamate deterministiche.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import feedback_corpus as fc  # noqa: E402
from CORE import worker as w  # noqa: E402
from CORE.memory import AgentMemory  # noqa: E402
from CORE.tools import ToolSet  # noqa: E402


def test_verified_dopo_test_verde():
    assert w.classify_verification({}, True) == "verified"
    stop, mode = w.verification_gate("verified", False)
    assert (stop, mode) == (True, "verified")
    assert w.verification_report_line("verified", "verified") == ""


def test_import_fail_e_verificato_failed():
    status = w.classify_verification({"mod.py": ["foo"]}, True)
    assert status == "failed"
    stop, mode = w.verification_gate(status, False)
    assert (stop, mode) == (True, "unverified")
    line = w.verification_report_line(status, mode)
    assert "UNVERIFIED" in line and "failed" in line
    assert stop is True  # non si continua all'infinito: imp/export già ritentati


def test_test_fail_e_verificato_failed():
    status = w.classify_verification({}, False)
    assert status == "failed"
    assert w.verification_gate(status, False) == (True, "unverified")
    assert "UNVERIFIED" in w.verification_report_line(status, "unverified")


def test_mai_testato_richiede_verifica():
    status = w.classify_verification({}, None)
    assert status == "not_tested"
    assert w.verification_gate(status, False) == (False, "retry")
    assert w.verification_gate(status, False, retries=2) == (True, "unverified")
    assert w.verification_override({"title": "x"}) is False


def test_override_esplicito_e_tracciato():
    assert w.verification_override({"allow_unverified_done": True}) is True
    assert w.verification_override({"context": {"verification_override": True}}) is True
    assert w.verification_override({"context": {"verification_override": "yes"}}) is False
    assert w.verification_gate("failed", True) == (True, "override")
    line = w.verification_report_line("failed", "override")
    assert "override" in line and "failed" in line


def test_stati_gate_e_verdetto_corpus():
    assert w.VERIFICATION_STATUSES == {"verified", "failed", "not_tested"}
    assert w.verification_gate("stato_sconosciuto", False) == (True, "unverified")


def test_integrazione_marker_nel_report_non_nel_result(tmp_path, monkeypatch):
    """Il result resta pulito; UNVERIFIED finisce in memoria e nel corpus."""
    monkeypatch.chdir(tmp_path)

    class DoneModel:
        def call_streaming(self, **kwargs):
            yield json.dumps({"thought": "done", "action": "none",
                              "args": [], "done": True, "result": "completed"})

    state = tmp_path / "state"
    project = tmp_path / "project"
    state.mkdir(parents=True, exist_ok=True)
    project.mkdir()
    cfg = {"paths": {"project_root": str(project), "state_dir": str(state)},
           "models": {"worker": {"name": "fake:1b"}}, "security": {}}
    logger = logging.getLogger("verify-integration")
    logger.addHandler(logging.NullHandler())
    tools = ToolSet(cfg, logger)
    memory = AgentMemory("verify-test", state, None, logger)
    worker = w.Worker("verify-test", "worker", tools, memory,
                      DoneModel(), logger)

    result = worker.execute({"id": "verify-1", "title": "t", "description": "d"})

    assert result == "completed"  # contratto execute() invariato
    assert worker.last_verification_status == "not_tested"
    events = [e for e in memory.get_history() if e.get("type") == "verification"]
    assert events and "UNVERIFIED" in events[-1]["content"]
    samples = fc.load_task("verify-1", state_dir=state)
    assert samples and "UNVERIFIED" in samples[-1].reason
    # il gate ha richiesto run_test_suite (2 retry) → correction tracciata
    assert samples[-1].verdict == "corrected"
    assert samples[-1].attempts >= 2
