"""
test_react_tool_prompt.py — verifica offline (todo 'Tool hallucination'):
la lista dei tool è nel SYSTEM prompt del loop ReAct e viene reiniettata
nel turno di correzione dopo un errore 'unknown tool'. Nessun LLM/rete.
"""
from __future__ import annotations

import inspect
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
    tools = ToolSet(cfg, _LOG)
    return Worker("verifica", "worker_coder", tools, SimpleNamespace(),
                  SimpleNamespace(), _LOG)


def test_system_prompt_contiene_la_lista_tool(tmp_path):
    prompt = _worker(tmp_path)._build_system(
        {"title": "crea uno script", "description": "scrivi un file"})
    assert "TOOLS (code=full name, use CODE in action):" in prompt
    for code in ("read", "write", "list_tools", "bash"):
        assert code in prompt
    assert "NEVER write \"tool\" or \"run_tool\" as action" in prompt


def test_unknown_tool_rimanda_all_lista_vera(tmp_path):
    result = _worker(tmp_path)._call_tool("check_directory", [])
    assert result.startswith("ERROR: unknown tool")
    assert "list_tools()" in result


def test_cor_react_reinjecta_la_lista_dopo_unknown_tool():
    source = inspect.getsource(Worker.execute)
    assert "unknown tool" in source
    assert "Available tools:" in source
    assert "Use ONLY these tool names." in source
