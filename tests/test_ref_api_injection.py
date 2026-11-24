"""Cycle 145 — A/B di una sola leva: ref API, harness Cycle 143 ripristinato.

Nessun LLM, rete o GPU: verifica solo che le cheat sheet API raggiungano il
prompt del worker. Il comportamento di routing/workspace resta quello del
run accettato Cycle 143.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.worker import Worker  # noqa: E402
from tools import run_eval as reval  # noqa: E402


def test_ref_taskqueue_raggiunge_il_prompt():
    worker = Worker(
        "ref-ab", "worker_coder",
        SimpleNamespace(project_root=ROOT),
        SimpleNamespace(), SimpleNamespace(), logging.getLogger("test"),
    )
    block = worker._build_refs_block({
        "title": "Usa TaskQueue.add correttamente",
        "description": "Scrivi codice che usa TaskQueue per aggiungere un task alla coda.",
    })
    assert "TaskQueue" in block
    assert "add(" in block


def test_harness_non_e_isolato_e_routing_presente():
    # Niente factory.harness: il run usa project/ e state/ condivisi come
    # nella misura accettata Cycle 143.
    factory = reval.build_default_worker_factory("worker_coder")
    assert not hasattr(factory, "harness")
