"""
test_clarifier_gui_bridge.py — verifica offline del todo 'Clarifier GUI dialog'.

Il worker chiede chiarimenti scrivendo state/clarification.txt; il main thread
della GUI fa polling con un QTimer e scrive clarification_answer.txt. Nessun
QApplication avviato, nessuna finestra mostrata, nessun LLM/rete.
"""
from __future__ import annotations

import inspect
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import worker as worker_module  # noqa: E402
from CORE.tools import ToolSet  # noqa: E402
from CORE.worker import Worker  # noqa: E402
from GUI.center_area import CenterArea  # noqa: E402

_LOG = SimpleNamespace(info=lambda *a, **k: None,
                       warning=lambda *a, **k: None,
                       error=lambda *a, **k: None)


def _ask_fn(tmp_path, monkeypatch):
    cfg = {
        "paths": {"project_root": str(tmp_path / "project"),
                  "state_dir": str(tmp_path / "state")},
        "models": {"worker_coder": {"name": "fake-coder:3b"}},
        "security": {},
    }
    (tmp_path / "project").mkdir(exist_ok=True)
    tools = ToolSet(cfg, _LOG)
    worker = Worker("chiarimento", "worker_coder", tools, SimpleNamespace(),
                    SimpleNamespace(), _LOG)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: False))
    real_sleep = time.sleep
    # 30 iterazioni × 0,05 s = 1,5 s: margine sufficiente perché il thread
    # rispondi venga schedulato anche su runner carichi (0,01 s → 0,3 s
    # era troppo stretto e il worker faceva fail-open con risposta vuota).
    monkeypatch.setattr(worker_module.time, "sleep",
                        lambda seconds: real_sleep(0.05))
    return worker._make_clarify_ask_fn()


def test_ponte_file_porteda_la_risposta_al_worker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ask = _ask_fn(tmp_path, monkeypatch)

    def rispondi():
        question = tmp_path / "state" / "clarification.txt"
        for _ in range(300):
            if question.is_file() and "Domanda?" in question.read_text(
                    encoding="utf-8"):
                (tmp_path / "state" / "clarification_answer.txt").write_text(
                    "1,2,1", encoding="utf-8")
                return
            time.sleep(0.01)

    thread = threading.Thread(target=rispondi)
    thread.start()
    assert ask("Domanda?") == "1,2,1"
    thread.join(timeout=3)
    state = tmp_path / "state"
    assert not (state / "clarification.txt").exists()
    assert not (state / "clarification_answer.txt").exists()


def test_senza_risposta_fail_open(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _ask_fn(tmp_path, monkeypatch)("Domanda?") == ""


def test_gui_polla_sul_thread_principale_con_qtimer():
    source = inspect.getsource(CenterArea.__init__)
    for token in ("QTimer", "timeout.connect", "clarification.txt",
                  "clarification_answer.txt", "QInputDialog"):
        assert token in source
