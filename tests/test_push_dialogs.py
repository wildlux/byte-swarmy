"""Test per C1 (conferma push) e C2 (riepilogo errori).

Verifica la logica senza mostrare QMessageBox modal (bloccante in offscreen).
Testiamo:
- _git_push_one ritorna None se successo, stringa errore se fallito
- _show_push_summary usa le icone giuste in base a success/errors
- _confirm_push ritorna bool in base al pulsante scelto
"""
import sys, os, json, shutil
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication, QMessageBox

# Evita dialog reali nei test
QMessageBox.exec = lambda self, *a, **k: 1

app = QApplication.instance() or QApplication(sys.argv)


def test_git_push_one_returns_none_on_success():
    """_git_push_one ritorna None se tutto OK."""
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    # Mock subprocess.run per simulare successo totale
    def fake_run(cmd, **kw):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "Everything up to date"
        result.stderr = ""
        return result
    with patch("subprocess.run", side_effect=fake_run):
        err = panel._git_push_one("origin", "https://github.com/test/repo.git", "token123")
    assert err is None, f"Atteso None, ottenuto: {err!r}"


def test_git_push_one_returns_error_on_push_fail():
    """_git_push_one ritorna stringa errore se push fallisce."""
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    # Simula: git add OK, commit OK, push FAIL
    calls = [
        # git add
        MagicMock(returncode=0, stdout="", stderr=""),
        # git commit
        MagicMock(returncode=0, stdout="[main abc1234] Auto-sync", stderr=""),
        # git rev-parse --abbrev-ref HEAD
        MagicMock(returncode=0, stdout="main\n", stderr=""),
        # git push — fallisce
        MagicMock(returncode=1, stdout="", stderr="! [rejected] main -> main (fetch first)"),
    ]
    with patch("subprocess.run", side_effect=calls):
        err = panel._git_push_one("origin", "https://github.com/test/repo.git", "tok")
    assert err is not None
    assert "rejected" in err or "fetch first" in err


def test_git_push_one_returns_error_on_timeout():
    """_git_push_one ritorna errore se subprocess va in timeout."""
    import subprocess
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=1)):
        err = panel._git_push_one("origin", "https://github.com/test/repo.git", "tok")
    assert err is not None
    assert "timeout" in err.lower()


def test_show_push_summary_no_errors_calls_information():
    """C2: con 0 errori, mostra information dialog."""
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    info_calls = []
    with patch.object(QMessageBox, "information", lambda *a, **k: info_calls.append(a)):
        panel._show_push_summary(
            total=2, errors=[],
            remote_list=[("origin", "url1"), ("gitlab", "url2")],
        )
    assert len(info_calls) == 1
    assert "Push completato" in info_calls[0][1]


def test_show_push_summary_all_errors_calls_critical():
    """C2: tutti falliti → critical."""
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    # Patch QMessageBox ctor + exec
    created = []
    class FakeQMB:
        Icon = QMessageBox.Icon
        StandardButton = QMessageBox.StandardButton
        def __init__(self, *a, **k):
            self.icon = None
            self.text = ""
            created.append(self)
        def setWindowTitle(self, t): self.title = t
        def setIcon(self, i): self.icon = i
        def setText(self, t): self.text = t
        def exec(self): return 1
    with patch("PyQt6.QtWidgets.QMessageBox", FakeQMB):
        panel._show_push_summary(
            total=2,
            errors=[("origin", "rejected"), ("gitlab", "timeout 120s")],
            remote_list=[("origin", "url1"), ("gitlab", "url2")],
        )
    assert len(created) == 1
    assert "fallito su tutti" in created[0].title
    assert created[0].icon == QMessageBox.Icon.Critical


def test_show_push_summary_partial_calls_warning():
    """C2: parziale → warning."""
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    created = []
    class FakeQMB:
        Icon = QMessageBox.Icon
        StandardButton = QMessageBox.StandardButton
        def __init__(self, *a, **k):
            self.icon = None
            self.text = ""
            created.append(self)
        def setWindowTitle(self, t): self.title = t
        def setIcon(self, i): self.icon = i
        def setText(self, t): self.text = t
        def exec(self): return 1
    with patch("PyQt6.QtWidgets.QMessageBox", FakeQMB):
        panel._show_push_summary(
            total=3,
            errors=[("gitlab", "401 unauthorized")],
            remote_list=[("origin", "u1"), ("gitlab", "u2"), ("test", "u3")],
        )
    assert len(created) == 1
    # success = 3 - 1 = 2, quindi titolo è "Push parziale: 2/3 OK"
    assert "2/3" in created[0].title
    assert created[0].icon == QMessageBox.Icon.Warning


def test_confirm_push_yes_returns_true():
    """C1: utente preme Yes → ritorna True."""
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    class FakeQMB:
        # Mantieni accesso a enum/StandardButton per compatibilità codice
        Icon = QMessageBox.Icon
        StandardButton = QMessageBox.StandardButton
        def __init__(self, *a, **k): pass
        def setWindowTitle(self, t): pass
        def setIcon(self, i): pass
        def setText(self, t): pass
        def setStandardButtons(self, b): pass
        def setDefaultButton(self, b): pass
        def exec(self): return QMessageBox.StandardButton.Yes
    with patch("PyQt6.QtWidgets.QMessageBox", FakeQMB):
        result = panel._confirm_push("test", [("origin", "url", "github")])
    assert result is True


def test_confirm_push_no_returns_false():
    """C1: utente preme No → ritorna False."""
    from GUI.control_center import DevicePanel
    panel = DevicePanel()
    class FakeQMB:
        Icon = QMessageBox.Icon
        StandardButton = QMessageBox.StandardButton
        def __init__(self, *a, **k): pass
        def setWindowTitle(self, t): pass
        def setIcon(self, i): pass
        def setText(self, t): pass
        def setStandardButtons(self, b): pass
        def setDefaultButton(self, b): pass
        def exec(self): return QMessageBox.StandardButton.No
    with patch("PyQt6.QtWidgets.QMessageBox", FakeQMB):
        result = panel._confirm_push("test", [("origin", "url")])
    assert result is False


if __name__ == "__main__":
    # Run senza pytest se non installato
    import traceback
    tests = [
        test_git_push_one_returns_none_on_success,
        test_git_push_one_returns_error_on_push_fail,
        test_git_push_one_returns_error_on_timeout,
        test_show_push_summary_no_errors_calls_information,
        test_show_push_summary_all_errors_calls_critical,
        test_show_push_summary_partial_calls_warning,
        test_confirm_push_yes_returns_true,
        test_confirm_push_no_returns_false,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n=== {passed}/{len(tests)} test passati ===")
