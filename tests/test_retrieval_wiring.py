# -*- coding: utf-8 -*-
"""A4 (2026-11-22): `retrieve_similar_task` nel dispatch del worker.

Il retrieval resta **chiamabile ma non automatico**: il test verifica mapping,
prompt, allowlist, dispatch con retriever finto e keyword auto-tool. Zero LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import auto_tool  # noqa: E402
from CORE.tools import TOOL_SIGNATURES, ToolSet  # noqa: E402
from CORE.worker import Worker  # noqa: E402

_LOG = SimpleNamespace(info=lambda *a, **k: None,
                       warning=lambda *a, **k: None,
                       error=lambda *a, **k: None)
_MODELS = SimpleNamespace()


def _worker(tmp_path):
    cfg = {
        "paths": {"project_root": str(tmp_path / "project"),
                  "state_dir": str(tmp_path / "state")},
        "models": {"worker": {"name": "fake:1b"}},
        "security": {},
    }
    (tmp_path / "project").mkdir(exist_ok=True)
    tools = ToolSet(cfg, _LOG)
    return Worker("worker-test", "worker", tools, SimpleNamespace(),
                  _MODELS, _LOG), tools


def test_nome_in_mapping_prompt_e_allowlist(tmp_path):
    worker, tools = _worker(tmp_path)
    assert Worker.TOOL_CODE_MAP["retrieve"] == "retrieve_similar_task"
    assert "retrieve_similar_task(query,k=3)" in Worker.SYSTEM
    prompt = worker._build_system({"title": "trova un task simile"})
    assert "retrieve_similar_task" in prompt
    assert "retrieve_similar_task" in tools.allowed_tools()
    assert "retrieve_similar_task" in TOOL_SIGNATURES


def test_dispatch_con_retriever_finto(tmp_path):
    worker, tools = _worker(tmp_path)
    seen = {}

    def fake(query, k=3):
        seen["query"], seen["k"] = query, k
        return "OK: 1 risultato per " + query

    tools.retrieve_similar_task = fake
    out = worker._call_tool("retrieve_similar_task", ["aggiungi cache", 2])
    assert out == "OK: 1 risultato per aggiungi cache"
    assert seen == {"query": "aggiungi cache", "k": 2}


def test_dispatch_default_k_e_argomenti_non_validi(tmp_path):
    worker, tools = _worker(tmp_path)
    tools.retrieve_similar_task = lambda q, k=3: f"{q}:{k}"
    assert worker._call_tool("retrieve_similar_task", ["x"]) == "x:3"
    assert worker._call_tool("retrieve_similar_task", []) == ":3"


def test_auto_tool_keyword():
    assert "retrieve_similar_task" in auto_tool.detect_names("cerca un task simile")
