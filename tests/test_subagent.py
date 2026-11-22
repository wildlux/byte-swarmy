# -*- coding: utf-8 -*-
"""Test offline del registry subagent (2026-11-22).

Nessuna rete e nessun LLM: modello, runner e temperatura sono fake.
Verifica creazione, limiti, gate termico/pause, report e integrazione tool.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import auto_tool  # noqa: E402
from CORE.subagent import SubagentRegistry  # noqa: E402
from CORE.tools import TOOL_SIGNATURES, ToolSet  # noqa: E402
from CORE.worker import Worker  # noqa: E402

_LOG = SimpleNamespace(info=lambda *a, **k: None,
                       warning=lambda *a, **k: None,
                       error=lambda *a, **k: None)
_MODELS = SimpleNamespace()


def _config(tmp_path):
    return {
        "paths": {"project_root": str(tmp_path / "project"),
                  "state_dir": str(tmp_path / "state")},
        "models": {"worker_coder": {"name": "fake-coder:3b"},
                   "worker_general": {"name": "fake:1.5b"},
                   "planner": {"name": "fake-planner"}},
        "security": {},
    }


def _registry(tmp_path, runner=None, temp=35.0):
    cfg = _config(tmp_path)
    (tmp_path / "project").mkdir(exist_ok=True)
    return SubagentRegistry(cfg, _MODELS, _LOG, temp_fn=lambda: temp,
                            runner=runner)


def _spawn(reg, task="analizza il modulo", model="worker_coder"):
    out = reg.spawn("worker-worker_coder", model, task)
    assert out.startswith("OK"), out
    return re.search(r"'([^']+)'", out).group(1)


def test_spawn_non_chiama_llm_e_valida_modello(tmp_path):
    calls = []
    reg = _registry(tmp_path, runner=lambda w, t: calls.append(t) or "OK: done")
    aid = _spawn(reg)
    assert aid.startswith("sub-worker-worker_coder-")
    assert calls == []
    assert reg.model_keys() == {"worker_coder", "worker_general"}
    assert reg.spawn("padre", "planner", "x").startswith("ERROR")
    assert reg.spawn("padre", "inesistente", "x").startswith("ERROR")
    assert reg.spawn("padre", "worker_coder", "").startswith("ERROR")
    assert reg.spawn("padre/../", "worker_coder", "x").startswith("ERROR")


def test_limiti_profondita_e_figli(tmp_path):
    reg = _registry(tmp_path, runner=lambda w, t: "OK: done")
    assert reg.spawn("padre", "worker_coder", "x", depth=1).startswith("ERROR")
    ids = [reg.spawn("padre", "worker_coder", f"task {i}")
           for i in range(4)]
    assert all(x.startswith("OK") for x in ids)
    assert reg.spawn("padre", "worker_coder", "quinto").startswith("ERROR")


def test_report_roundtrip_idempotente(tmp_path):
    calls = []

    def runner(worker, task):
        calls.append(worker.agent_id)
        return f"OK: report di {worker.agent_id}"

    reg = _registry(tmp_path, runner=runner)
    aid = _spawn(reg, task="scrivi un test")
    out = reg.get_report(aid)
    assert out == f"OK: report di {aid}"
    assert reg.get_report(aid) == out
    assert calls == [aid]
    assert aid in reg.list_agents()


def test_gate_pause_e_temperatura(tmp_path):
    calls = []
    reg = _registry(tmp_path, runner=lambda w, t: calls.append(1) or "OK: done")
    aid = _spawn(reg)
    pause = tmp_path / "state" / "pause.flag"
    pause.write_text("", encoding="utf-8")
    assert "BLOCKED" in reg.get_report(aid)
    pause.unlink()
    reg.temp_fn = lambda: 75.0
    assert "60" in reg.get_report(aid)
    reg.temp_fn = lambda: None
    assert "BLOCKED" in reg.get_report(aid)
    assert calls == []


def test_timeout_fail_open(tmp_path):
    reg = _registry(tmp_path, runner=lambda w, t: time.sleep(2) or "OK: tardi")
    aid = _spawn(reg)
    assert reg.run(aid, timeout=1).startswith("TIMEOUT")
    assert "failed" in reg.list_agents()


def test_errori_non_sollevano(tmp_path):
    reg = _registry(tmp_path, runner=lambda w, t: "OK: done")
    for probe in ("", None, 1, "inesistente", "../etc"):
        out = reg.get_report(probe)
        assert isinstance(out, str) and out.startswith("ERROR")
    reg.runner = lambda w, t: (_ for _ in ()).throw(RuntimeError("boom"))
    assert reg.get_report(_spawn(reg)).startswith("ERROR")


def test_tool_e_worker_registrati():
    for name in ("spawn_subagent", "get_subagent_report", "list_subagents"):
        assert name in TOOL_SIGNATURES
    cfg = _config(Path("/tmp/subagent-registry-check"))
    tools = ToolSet(cfg, _LOG)
    assert {"spawn_subagent", "get_subagent_report", "list_subagents"} <= tools.allowed_tools()
    assert tools.spawn_subagent("worker_coder", "x").startswith("ERROR")
    assert Worker.TOOL_CODE_MAP["spawn"] == "spawn_subagent"
    assert Worker.TOOL_CODE_MAP["subreport"] == "get_subagent_report"
    assert "spawn_subagent" in auto_tool.detect_names("crea subagent")


def test_worker_inietta_registry_senza_llm(tmp_path):
    cfg = _config(tmp_path)
    (tmp_path / "project").mkdir(exist_ok=True)
    tools = ToolSet(cfg, _LOG)
    worker = Worker("padre", "worker_coder", tools, SimpleNamespace(),
                    _MODELS, _LOG)
    assert tools.subagents is not None
    out = tools.spawn_subagent("worker_coder", "analizza x")
    assert out.startswith("OK")
