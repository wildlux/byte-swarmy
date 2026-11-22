# -*- coding: utf-8 -*-
"""A3 (2026-11-22): curazione stratificata del corpus — test CLI offline.

JSONL finti in una state dir temporanea: nessun LLM, nessuna rete, nessuna
lettura del corpus reale. Verifica conteggi per verdict, dedup, cap e flag
`--only-done` (comportamento storico).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from CORE import feedback_corpus as fc  # noqa: E402
import curate_corpus as cc  # noqa: E402


def _sample(task_id, verdict, output):
    return fc.Triple(task_id=task_id, kind="code", title=task_id,
                     description="d", refs=(), output=output, verdict=verdict,
                     first_try=verdict == "done", attempts=1, model="fake:1b",
                     reason="reason", ts=1.0)


def _state(samples):
    tmp = Path(tempfile.mkdtemp(prefix="bswarm-curate-"))
    by_task = {}
    for s in samples:
        by_task.setdefault(s.task_id, []).append(s)
    for tid, triples in by_task.items():
        for t in triples:
            fc.append_triple(t, state_dir=tmp)
    return tmp


def _run_json(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cc.main(list(args))
    assert code == 0
    return json.loads(buf.getvalue())


def test_curate_default_include_done_e_corrected():
    s = [
        _sample("t1", "done", "a"), _sample("t1", "corrected", "b"),
        _sample("t1", "failed_definitively", "c"), _sample("t2", "done", "d"),
    ]
    result = cc.curate(s)
    assert [t.output for t in result] == ["a", "b", "d"]
    assert all(t.verdict != "failed_definitively" for t in result)


def test_curate_only_done_e_dedup():
    s = [_sample("t1", "done", "a"), _sample("t1", "done", "a"),
         _sample("t1", "corrected", "b")]
    assert [t.output for t in cc.curate(s, only_done=True)] == ["a"]
    assert [t.output for t in cc.curate(s)] == ["a", "b"]


def test_curate_max_per_verdict():
    s = [_sample("t1", "done", "a"), _sample("t2", "done", "b"),
         _sample("t3", "corrected", "c"), _sample("t4", "corrected", "d")]
    result = cc.curate(s, max_per_verdict=1)
    assert [t.output for t in result] == ["a", "c"]


def test_cli_json_conteggi_per_verdetto():
    state = _state([
        _sample("t1", "done", "a"), _sample("t1", "corrected", "b"),
        _sample("t2", "failed_definitively", "c"),
    ])
    report = _run_json("--state-dir", str(state), "--json")
    assert report["samples"] == 3
    assert report["curated"] == 2
    assert report["counts"] == {"corrected": 1, "done": 1,
                                "failed_definitively": 1}
    assert report["excluded_failed"] == 1
    assert report["only_done"] is False


def test_cli_only_done_ripristina_vecchio_comportamento():
    state = _state([
        _sample("t1", "done", "a"), _sample("t1", "corrected", "b"),
    ])
    report = _run_json("--state-dir", str(state), "--only-done", "--json")
    assert report["curated"] == 1
    assert report["counts"]["corrected"] == 1
    assert report["only_done"] is True
