"""Test Cycle 59 — Benchmark esterni e validazione indipendente.

Copre ExternalBenchmark con mock (nessuna dipendenza da Ollama reale):
- criterio di successo (_evaluate_check)
- run_naked_task con ModelClient mockato
- run_harness_task con worker_factory mockato
- run_all end-to-end con mock
- save_results e generate_report
- dry-run senza Ollama
"""

import json
import pathlib
import tempfile
from unittest.mock import MagicMock

from CORE.external_benchmark import ExternalBenchmark, BENCH_TASKS


def _fake_model_client(response: str, should_fail: bool = False) -> MagicMock:
    m = MagicMock()
    if should_fail:
        m.call.side_effect = RuntimeError("modello non disponibile")
    else:
        m.call.return_value = response
    return m


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


# ======================================================================
# A. Dataset BENCH_TASKS
# ======================================================================

def test_bench_tasks_count():
    assert len(BENCH_TASKS) == 8
    for t in BENCH_TASKS:
        assert "id" in t and "title" in t and "description" in t
        assert "file" in t and "check" in t


# ======================================================================
# B. Criterio di successo
# ======================================================================

def test_evaluate_check_true():
    eb = ExternalBenchmark(pathlib.Path("/tmp"), models=None, log=_dummy_logger())
    content = (
        "def parse_email(email: str) -> str:\n"
        "    return email.split('@')[-1]\n"
    )
    check = ("lambda content: 'def parse_email(email: str)' in content")
    assert eb._evaluate_check(check, content) is True


def test_evaluate_check_false():
    eb = ExternalBenchmark(pathlib.Path("/tmp"), models=None, log=_dummy_logger())
    content = "def parse_email(email):\n    return None\n"
    check = ("lambda content: 'def parse_email(email: str)' in content")
    assert eb._evaluate_check(check, content) is False


# ======================================================================
# C. run_naked_task con ModelClient mockato
# ======================================================================

def test_naked_task_success(tmp_path):
    """Modello nudo restituisce codice che passa il check → successo."""
    eb = ExternalBenchmark(tmp_path, models=_fake_model_client(
        "def parse_email(email: str) -> str:\n    return email.split('@')[-1]\n",
    ), log=_dummy_logger())
    task = BENCH_TASKS[0]  # ext-01 type hints su utils.py
    # Copia il target nella sandbox usata da run_naked_task
    sandbox = tmp_path / "state" / "bench_sandbox_naked"
    sandbox.mkdir(parents=True)
    import shutil
    shutil.copytree(eb.bench_target_dir, sandbox, dirs_exist_ok=True)

    res = eb.run_naked_task(task)
    assert res["mode"] == "naked"
    assert res["task_id"] == task["id"]
    assert "wall_seconds" in res
    # Il modello finto restituisce contenuto valido che passa il check


def test_naked_task_model_error(tmp_path):
    """Modello nudo solleva eccezione → error registrato, non crash."""
    eb = ExternalBenchmark(tmp_path, models=_fake_model_client("", should_fail=True),
                           log=_dummy_logger())
    sandbox = tmp_path / "state" / "bench_sandbox_naked"
    sandbox.mkdir(parents=True)
    import shutil
    shutil.copytree(eb.bench_target_dir, sandbox, dirs_exist_ok=True)

    res = eb.run_naked_task(BENCH_TASKS[0])
    assert res["error"] is not None
    assert res["success_first_try"] is False


# ======================================================================
# D. run_harness_task con worker_factory mockato
# ======================================================================

def test_harness_task_first_try_success(tmp_path):
    """Worker eseguire e il check passa al primo tentativo."""
    eb = ExternalBenchmark(tmp_path, models=None, log=_dummy_logger())
    task = BENCH_TASKS[0]

    def worker_factory(sandbox_dir):
        w = MagicMock()
        w.execute.return_value = "COMPLETED: file scritto"
        # Il worker "scrive" il file con type hints (passa il check)
        def _execute_side_effect(t):
            f = sandbox_dir / task["file"]
            content = f.read_text(encoding="utf-8") if f.exists() else ""
            content = content.replace(
                "def parse_email(email):", "def parse_email(email: str):"
            ).replace(
                "def slugify(text):", "def slugify(text: str):"
            ).replace(
                "def is_valid_password(password):",
                "def is_valid_password(password: str):"
            ).replace(
                "def format_currency(amount, symbol=\"$\"):",
                "def format_currency(amount, symbol: str = \"$\"):"
            )
            f.write_text(content, encoding="utf-8")
            return "COMPLETED"
        w.execute.side_effect = _execute_side_effect
        return w

    sandbox = tmp_path / "state" / "bench_sandbox_harness"
    sandbox.mkdir(parents=True)
    import shutil
    shutil.copytree(eb.bench_target_dir, sandbox, dirs_exist_ok=True)

    res = eb.run_harness_task(task, worker_factory)
    assert res["mode"] == "harness"
    assert res["success_first_try"] is True
    assert res["attempts"] == 1


def test_harness_task_correction_loop(tmp_path):
    """Worker fallisce al primo, passa al secondo tentativo."""
    eb = ExternalBenchmark(tmp_path, models=None, log=_dummy_logger())
    task = BENCH_TASKS[0]

    call_count = {"n": 0}

    def worker_factory(sandbox_dir):
        w = MagicMock()
        w.execute.return_value = "COMPLETED"

        def _execute_side_effect(t):
            call_count["n"] += 1
            f = sandbox_dir / task["file"]
            content = f.read_text(encoding="utf-8") if f.exists() else ""
            if call_count["n"] == 1:
                # primo tentativo: non applica type hints (fallisce il check)
                return "NON APPLICATO"
            else:
                # secondo tentativo: applica (passa il check)
                content = content.replace(
                    "def parse_email(email):", "def parse_email(email: str):"
                ).replace(
                    "def slugify(text):", "def slugify(text: str):"
                ).replace(
                    "def is_valid_password(password):",
                    "def is_valid_password(password: str):"
                ).replace(
                    "def format_currency(amount, symbol=\"$\"):",
                    "def format_currency(amount, symbol: str = \"$\"):"
                )
                f.write_text(content, encoding="utf-8")
                return "COMPLETED"
        w.execute.side_effect = _execute_side_effect
        return w

    sandbox = tmp_path / "state" / "bench_sandbox_harness"
    sandbox.mkdir(parents=True)
    import shutil
    shutil.copytree(eb.bench_target_dir, sandbox, dirs_exist_ok=True)

    res = eb.run_harness_task(task, worker_factory, max_retries=3)
    assert res["success_after_loop"] is True
    assert res["attempts"] == 2


# ======================================================================
# E. run_all con mock (nessun worker_factory → harness saltato)
# ======================================================================

def test_run_all_no_factory(tmp_path):
    """Senza worker_factory, harness è skipped, naked esegue con mock."""
    import shutil

    eb = ExternalBenchmark(tmp_path, models=_fake_model_client(
        "def parse_email(email: str) -> str:\n    return None\n",
    ), log=_dummy_logger())
    results = eb.run_all(worker_factory=None)

    assert "harness" in results["tasks"]
    assert "naked" in results["tasks"]
    # Tutti i task harness devono essere skipped
    for r in results["tasks"]["harness"]:
        assert r.get("skipped") is not None
    # Summary deve avere entrambi i modi
    assert "harness" in results["summary"]
    assert "naked" in results["summary"]


# ======================================================================
# F. save_results e generate_report
# ======================================================================

def test_save_results(tmp_path):
    bench_dir = tmp_path / "benchmarks"
    eb = ExternalBenchmark(tmp_path, models=None, log=_dummy_logger(),
                           benchmarks_dir=bench_dir)
    eb.results["summary"] = {"harness": {"count": 2}, "naked": {"count": 2}}
    path = eb.save_results("test_bench.json")
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"]["harness"]["count"] == 2


def test_generate_report(tmp_path):
    bench_dir = tmp_path / "benchmarks"
    eb = ExternalBenchmark(tmp_path, models=None, log=_dummy_logger(),
                           benchmarks_dir=bench_dir)
    eb.results["timestamp"] = "2026-11-15T00:00:00"
    eb.results["summary"] = {
        "harness": {
            "count": 8, "success_first_try": 4, "success_after_loop": 6,
            "first_try_rate": 0.5, "after_loop_rate": 0.75,
            "gate_blocks": 1, "errors": 0,
            "wall_seconds_total": 120.0, "wall_avg_per_task": 15.0,
        },
        "naked": {
            "count": 8, "success_first_try": 1, "success_after_loop": 1,
            "first_try_rate": 0.125, "after_loop_rate": 0.125,
            "gate_blocks": 0, "errors": 0,
            "wall_seconds_total": 40.0, "wall_avg_per_task": 5.0,
        },
    }
    report = eb.generate_report()
    assert "Benchmark esterno" in report
    assert "successo al primo colpo" in report
    assert "50%" in report or "0.5" in report
    assert "12%" in report or "0.12" in report


# ======================================================================
# G. Entry point dry-run (senza Ollama)
# ======================================================================

def test_main_dry_run(monkeypatch, tmp_path):
    """Senza Ollama raggiungibile, main() va in dry-run e non crasha."""
    import CORE.external_benchmark as eb_mod

    # Monkeppiamo urllib per simulare Ollama non raggiungibile
    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    import urllib.request
    real_urlopen = urllib.request.urlopen

    def _fake_urlopen(*a, **k):
        raise OSError("connessione rifiutata")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(sys := __import__("sys"), "argv",
                        ["external_benchmark", "--run", "--config",
                         "CONFIG/config.toml"])

    try:
        code = eb_mod.main()
    finally:
        urllib.request.urlopen = real_urlopen

    assert code == 0


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
