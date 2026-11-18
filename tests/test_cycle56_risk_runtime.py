"""Test Cycle 56 — Risk classifier deterministico + Runtime verification harness.

Copre:
- Classificazione rischio (low/medium/high/critical) via regole deterministiche.
- Runtime verifier: py_compile OK / SYNTAX ERROR, pipeline task files, boot smoke.
- TaskQueue.mark_awaiting_human → stato awaiting_human_approval.
"""

import pathlib

from SAFETY.risk_classifier import (
    classify,
    requires_human,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
)
from CORE.runtime_verifier import RuntimeVerifier
from CORE.task_queue import TaskQueue


def _dummy_logger():
    class _L:
        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

        def debug(self, *a, **k):
            pass
    return _L()


def _mk_verifier(tmp_path) -> RuntimeVerifier:
    return RuntimeVerifier(tmp_path, _dummy_logger())


def _write(tmp_path, rel: str, content: str) -> pathlib.Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ======================================================================
# A. Risk classifier — deterministico, nessun LLM
# ======================================================================

def test_classify_critical_path_high():
    # Path critico (CORE/tools.py) → alto (non critical: task non architetturale).
    r = classify({"title": "fix tool write", "description": "patch write_file",
                 "type": "fix"}, touched_paths=["CORE/tools.py"])
    assert r["level"] == RISK_HIGH
    assert "critical_paths=CORE/tools.py" in r["reasons"]
    assert requires_human(r["level"]) is True


def test_classify_critical_path_refactor_critical():
    # Path critico + refactoring → critical.
    r = classify({"title": "refactor orchestrator", "description": "struttura",
                 "type": "refactor"}, touched_paths=["SAFETY/risk_classifier.py"])
    assert r["level"] == RISK_CRITICAL
    assert requires_human(r["level"]) is True


def test_classify_refactor_high():
    r = classify({"title": "refactor memory module", "description": "",
                 "type": "refactor"})
    assert r["level"] == RISK_HIGH


def test_classify_diff_size_escalation():
    # Diff > 50 righe / > 3 file → alto.
    r = classify({"title": "add feature x", "description": "implement",
                 "type": "implement"}, diff_lines=60, diff_files=2)
    assert r["level"] == RISK_HIGH


def test_classify_normal_task_medium():
    r = classify({"title": "add feature x", "description": "implement",
                 "type": "implement"})
    assert r["level"] == RISK_MEDIUM
    assert requires_human(r["level"]) is False


def test_classify_api_change_high():
    r = classify({"title": "expose new api endpoint", "description": "",
                 "type": "implement"})
    assert r["level"] == RISK_HIGH


# ======================================================================
# B. Runtime verifier
# ======================================================================

def test_verify_python_ok(tmp_path):
    p = _write(tmp_path, "ok_mod.py", "def hello():\n    return 1\n")
    v = _mk_verifier(tmp_path)
    assert v.verify_python(p).startswith("OK")


def test_verify_python_syntax_error(tmp_path):
    p = _write(tmp_path, "broken_mod.py", "def broken(:\n    pass\n")
    v = _mk_verifier(tmp_path)
    res = v.verify_python(p)
    assert res.startswith("ERROR")


def test_verify_task_files_mixed(tmp_path):
    _write(tmp_path, "good_mod.py", "def ok():\n    return 1\n")
    bad = _write(tmp_path, "bad_mod.py", "def broken(:\n")
    v = _mk_verifier(tmp_path)
    res = v.verify_task_files([str(tmp_path / "good_mod.py"),
                               str(bad)])
    assert res.startswith("ERROR")
    assert "bad_mod.py" in res


def test_verify_task_files_non_py_ok(tmp_path):
    md = _write(tmp_path, "README.md", "# hello\n")
    v = _mk_verifier(tmp_path)
    assert v.verify_task_files([str(md)]).startswith("OK")


# ======================================================================
# C. TaskQueue — mark_awaiting_human
# ======================================================================

def test_task_queue_mark_awaiting_human(tmp_path):
    q = TaskQueue(tmp_path / "tasks", _dummy_logger())
    tid = q.add({
        "title": "t", "description": "d", "context": "",
        "status": "pending", "attempts": 0, "created_at": 0.0,
        "parent": None, "type": "implement", "source": "manual",
        "project_path": None,
    })
    q.mark_awaiting_human(tid, "RISK_BLOCK: level=high")
    t = q.get_by_id(tid)
    assert t is not None
    assert t.get("status") == "awaiting_human_approval"
    assert "RISK_BLOCK" in (t.get("reason") or "")


# ======================================================================
# D. Entry point
# ======================================================================

if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
