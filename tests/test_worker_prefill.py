"""test_worker_prefill.py — igiene performance (todo 'ridurre il prefill').

Verifica offline che T1 seleziona solo i tool rilevanti e T10 cacha il SYSTEM
prompt per famiglia di task. Nessun LLM, rete, GPU o run della suite completa.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.tools import ToolSet  # noqa: E402
from CORE.worker import Worker  # noqa: E402

_LOG = SimpleNamespace(info=lambda *a, **k: None,
                       warning=lambda *a, **k: None,
                       error=lambda *a, **k: None)


def _worker(tmp_path):
    cfg = {
        "paths": {"project_root": str(tmp_path / "project"),
                  "state_dir": str(tmp_path / "state")},
        "models": {"worker_coder": {"name": "fake-coder:3b"}},
        "security": {},
    }
    (tmp_path / "project").mkdir(exist_ok=True)
    return Worker("prefill", "worker_coder", ToolSet(cfg, _LOG),
                  SimpleNamespace(), SimpleNamespace(), _LOG)


def test_classificazione_riduce_i_tool(tmp_path):
    worker = _worker(tmp_path)
    crea = worker._classify_task_tools(
        {"title": "crea uno script", "description": "scrivi un file"})
    tutto = worker._classify_task_tools(
        {"title": "operazione generica", "description": ""})
    assert "git_commit" not in crea
    assert "analyze" not in crea
    assert {"read", "write", "list_tools"} <= crea
    assert crea < tutto


def test_prompt_selettivo_e_piu_corto_del_fallback(tmp_path):
    worker = _worker(tmp_path)
    short = worker._build_system(
        {"title": "crea uno script", "description": "scrivi un file"})
    full = worker._build_system(
        {"title": "operazione generica", "description": ""})
    assert len(short) < len(full)
    assert "TOOLS (code=full name, use CODE in action):" in short
    assert "git_commit" not in short


def test_cache_riutilizza_lo_stesso_prompt(tmp_path):
    worker = _worker(tmp_path)
    task = {"title": "crea uno script", "description": "primo"}
    first = worker._build_system(task)
    second = worker._build_system(
        {"title": "crea un altro script", "description": "secondo"})
    assert first is second
