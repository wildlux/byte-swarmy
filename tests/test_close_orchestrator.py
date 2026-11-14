"""test_close_orchestrator.py — Test della chiusura orchestratore (closeEvent).

Verifica che alla chiusura della finestra:
  1. l'orchestratore attivo venga terminato PRIMA che la finestra si chiuda;
  2. il pid file venga validato (pid stantio / pid riutilizzato → non toccare);
  3. la scelta "keep" lasci l'orchestratore attivo;
  4. la scelta ricordata ("stop"/"keep") eviti il dialog.

I test usano un processo finto il cui cmdline contiene "orchestrator"
(argomento extra dopo -c, visibile in /proc/PID/cmdline) e un __file__
monkeypatchato per far puntare state/ a una directory temporanea —
mai sulla state/ reale del progetto.

NB: i test closeEvent usano _LogicWin, una QMainWindow minimale che
eredita i METODI REALI di ControlCenter (override a livello di classe:
il dispatch C++ dei virtual di PyQt richiede override di classe, non
attributi d'istanza). L'init completo della GUI (timer, pannelli,
device panel) rende il lifecycle del widget flaky sotto unittest; la
logica di chiusura è invece quella identica di produzione.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import GUI.control_center as cc  # noqa: E402
import GUI.cc_shutdown as cc_shutdown  # noqa: E402
from GUI import settings_store  # noqa: E402
from PyQt6.QtWidgets import QMainWindow  # noqa: E402


class _FakeOrch:
    """Processo long-lived il cui cmdline contiene 'orchestrator'."""

    def __init__(self, tmp: Path):
        self.proc = subprocess.Popen(
            [sys.executable, "-c",
             "import time; time.sleep(60)", "orchestrator-fake"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pid_file = tmp / "state" / "orchestrator.pid"
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(self.proc.pid), encoding="utf-8")

    def alive(self) -> bool:
        try:
            os.kill(self.proc.pid, 0)
            # poll() reaps: uno zombie figlio viene contabilizzato morto
            return self.proc.poll() is None
        except ProcessLookupError:
            return False

    def kill(self):
        try:
            self.proc.kill()
        except Exception:
            pass


class _LogicWin(QMainWindow):
    """Finestra minima per la logica di closeEvent (metodi di produzione)."""
    _orchestrator_pid = cc.ControlCenter._orchestrator_pid
    _pid_alive = staticmethod(cc.ControlCenter._pid_alive)
    _terminate_orchestrator_blocking = cc.ControlCenter._terminate_orchestrator_blocking
    closeEvent = cc.ControlCenter.closeEvent


def _call_pid(cls):
    """Chiama _orchestrator_pid su una istanza minimale (non serve UI)."""
    inst = cls.__new__(cls)
    return cls._orchestrator_pid(inst)


def _call_terminate(cls):
    """Chiama _terminate_orchestrator_blocking senza statusBar reale."""
    inst = cls.__new__(cls)
    # statusBar() non esiste su un'istanza non inizializzata: il metodo
    # lo gestisce con try/except.
    return cls._terminate_orchestrator_blocking(inst)


class TestCloseOrchestrator(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bsw_close_"))
        self.addCleanup(lambda: subprocess.run(
            ["pkill", "-f", "orchestrator-fake"], capture_output=True))
        self.addCleanup(lambda: __import__("shutil").rmtree(
            self.tmp, ignore_errors=True))
        # state/ fittizia + settings file fittizio (mai quelli reali)
        (self.tmp / "state").mkdir(parents=True, exist_ok=True)
        # base dir = tmp (monkeypatch del modulo che contiene i metodi di
        # chiusura: dopo il refactoring R3 vivono in GUI/cc_shutdown.py)
        self._orig_file = cc_shutdown.__file__
        cc_shutdown.__file__ = str(self.tmp / "GUI" / "cc_shutdown.py")
        self.addCleanup(setattr, cc_shutdown, "__file__", self._orig_file)
        # settings file fittizio (mai il CONFIG/settings.json reale)
        self._orig_settings = settings_store.SETTINGS_FILE
        settings_store.SETTINGS_FILE = str(self.tmp / "settings.json")
        self.addCleanup(setattr, settings_store,
                        "SETTINGS_FILE", self._orig_settings)

    # ── settings ─────────────────────────────────────────────────────
    def test_close_action_roundtrip(self):
        self.assertEqual(settings_store.get_close_action(), "")
        settings_store.set_close_action("stop")
        self.assertEqual(settings_store.get_close_action(), "stop")
        settings_store.set_close_action("keep")
        self.assertEqual(settings_store.get_close_action(), "keep")
        settings_store.set_close_action("spam")
        self.assertEqual(settings_store.get_close_action(), "")

    # ── validazione pid ──────────────────────────────────────────────
    def test_pid_valido_rilevato(self):
        fake = _FakeOrch(self.tmp)
        pid, alive = _call_pid(cc.ControlCenter)
        self.assertEqual(pid, fake.proc.pid)
        self.assertTrue(alive)
        fake.kill()

    def test_pid_non_orchestratore_ignorato(self):
        # processo innocuo (cmdline senza "orchestrator") nel pid file
        proc = subprocess.Popen(["sleep", "60"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        self.addCleanup(proc.kill)
        pid_file = self.tmp / "state" / "orchestrator.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        pid, alive = _call_pid(cc.ControlCenter)
        self.assertIsNone(pid)
        self.assertFalse(alive)
        # e il processo NON deve essere stato toccato
        self.assertTrue(proc.poll() is None)

    def test_pid_stantio_ignorato(self):
        pid_file = self.tmp / "state" / "orchestrator.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("999999", encoding="utf-8")
        pid, alive = _call_pid(cc.ControlCenter)
        self.assertIsNone(pid)

    def test_pid_non_numerico_ignorato(self):
        pid_file = self.tmp / "state" / "orchestrator.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("not-a-pid", encoding="utf-8")
        pid, alive = _call_pid(cc.ControlCenter)
        self.assertIsNone(pid)

    # ── terminazione bloccante ───────────────────────────────────────
    def test_termina_orchestratore(self):
        fake = _FakeOrch(self.tmp)
        ok = _call_terminate(cc.ControlCenter)
        self.assertTrue(ok)
        self.assertFalse(fake.alive())
        self.assertFalse(fake.pid_file.exists())

    def test_termina_senza_orchestratore(self):
        ok = _call_terminate(cc.ControlCenter)
        self.assertTrue(ok)  # niente da terminare → True

    # ── closeEvent ───────────────────────────────────────────────────
    class _FakeCloseEvent:
        """Stub di QCloseEvent: solo accept/ignore/isAccepted."""

        def __init__(self):
            self._accepted = False

        def accept(self):
            self._accepted = True

        def ignore(self):
            self._accepted = False

        def isAccepted(self):
            return self._accepted

    def _make_logic_window(self):
        """App + finestra minimale con i metodi reali di ControlCenter."""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        return _LogicWin()

    def test_closeevent_stop_termina_prima(self):
        fake = _FakeOrch(self.tmp)
        settings_store.set_close_action("stop")
        w = self._make_logic_window()
        ev = self._FakeCloseEvent()
        # Chiamata DIRETTA del closeEvent reale: sotto unittest il
        # dispatch C++ dei virtual di PyQt risulta inaffidabile, la
        # logica è quella identica di produzione.
        w.closeEvent(ev)
        self.assertTrue(ev.isAccepted(), "closeEvent non ha accettato")
        self.assertFalse(fake.alive(),
                         "orchestratore vivo DOPO la chiusura finestra")

    def test_closeevent_keep_lascia_attivo(self):
        fake = _FakeOrch(self.tmp)
        settings_store.set_close_action("keep")
        w = self._make_logic_window()
        ev = self._FakeCloseEvent()
        w.closeEvent(ev)
        self.assertTrue(ev.isAccepted(), "closeEvent non ha accettato")
        self.assertTrue(fake.alive(),
                        "orchestratore morto con scelta 'keep'")
        fake.kill()

    def test_closeevent_senza_orchestratore_chiude(self):
        settings_store.set_close_action("")
        w = self._make_logic_window()
        ev = self._FakeCloseEvent()
        w.closeEvent(ev)  # nessun dialog, nessun crash
        self.assertTrue(ev.isAccepted(), "closeEvent non ha accettato")


if __name__ == "__main__":
    unittest.main(verbosity=2)
