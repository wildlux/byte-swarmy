"""Test del ponte remoto dei pulsanti (GUI/remote_bridge.py).

Round-trip in-process: QLocalServer nel processo di test + QLocalSocket
client. Offscreen; nessun wait bloccante della suite (busy-loop
processEvents con scadenza via QElapsedTimer).

I socket vengono creati in tmp_path (path assoluti ermetici): niente
dipendenza da $XDG_RUNTIME_DIR, niente collisioni tra test, niente
socket stantii tra esecuzioni.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from PyQt6.QtCore import QElapsedTimer
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from GUI.remote_bridge import ButtonBridge, _slug  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)


class _Client:
    """Client sincrono minimal per i test (non usa tools/gui_remote)."""

    def __init__(self, socket_path: str):
        from PyQt6.QtNetwork import QLocalSocket
        self.sock = QLocalSocket()
        self.sock.connectToServer(socket_path)
        _app.processEvents()
        ok = self.sock.waitForConnected(2000)
        assert ok, f"client non connesso a {socket_path}: {self.sock.errorString()}"

    def ask(self, cmd: dict, timeout_ms: int = 3000) -> dict:
        self.sock.write((json.dumps(cmd) + "\n").encode("utf-8"))
        self.sock.flush()
        buf = b""
        t = QElapsedTimer()
        t.start()
        while b"\n" not in buf and not t.hasExpired(timeout_ms):
            _app.processEvents()
            if self.sock.bytesAvailable():
                buf += bytes(self.sock.readAll())
        line, _, _ = buf.partition(b"\n")
        assert line, "nessuna risposta dal bridge (timeout)"
        return json.loads(line.decode("utf-8"))


@pytest.fixture()
def bridge_and_window(tmp_path):
    """Finestra con pulsanti noti + bridge in ascolto (teardown pulito).

    socket_path in tmp_path: ermetico, niente $XDG_RUNTIME_DIR, niente
    collisioni tra test paralleli.
    """
    w = QWidget()
    clicks: list[str] = []
    b1 = QPushButton("Avvia")
    b2 = QPushButton("Avvia")            # duplicato → id avvia#1
    b1.clicked.connect(lambda: clicks.append("b1"))
    b2.clicked.connect(lambda: clicks.append("b2"))
    b3 = QPushButton("Fermo")
    b3.setEnabled(False)
    b3.clicked.connect(lambda: clicks.append("b3"))
    lay = QVBoxLayout(w)
    for b in (b1, b2, b3):
        lay.addWidget(b)
    w.show()
    _app.processEvents()

    sock = str(tmp_path / "t-bridge.sock")
    br = ButtonBridge(w, socket_path=sock)
    assert br.name, f"bridge non in ascolto su {sock}"
    try:
        yield w, br, clicks, tmp_path
    finally:
        br.close()
        _app.processEvents()
        w.deleteLater()
        _app.processEvents()


def test_list_inventory(bridge_and_window):
    w, br, _clicks, _tp = bridge_and_window
    r = _Client(br.name).ask({"op": "list"})
    assert r["ok"]
    ids = [b["id"] for b in r["buttons"]]
    # slug da testo: due "Avvia" → avvia e avvia#1; il disabled c'è
    assert "avvia" in ids and "avvia#1" in ids and "fermo" in ids
    st = {b["id"]: b["enabled"] for b in r["buttons"]}
    assert st["fermo"] is False and st["avvia"] is True


def test_click_by_id_and_duplicate(bridge_and_window):
    w, br, clicks, _tp = bridge_and_window
    c = _Client(br.name)
    assert c.ask({"op": "click", "id": "avvia"})["ok"]
    assert clicks == ["b1"]
    assert c.ask({"op": "click", "id": "avvia#1"})["ok"]
    assert clicks == ["b1", "b2"]


def test_click_by_index_and_disabled(bridge_and_window):
    w, br, clicks, _tp = bridge_and_window
    c = _Client(br.name)
    r = c.ask({"op": "click", "index": 2})   # "Fermo"
    assert r["ok"] is False and "disabilitato" in r["error"]
    assert clicks == []
    assert c.ask({"op": "click", "index": 0})["clicked"] == "Avvia"


def test_click_by_text_and_screenshot(bridge_and_window, tmp_path):
    w, br, clicks, _tp = bridge_and_window
    c = _Client(br.name)
    assert c.ask({"op": "click", "text": "Fermo"})["ok"] is False
    out = str(tmp_path / "grab.png")
    r = c.ask({"op": "screenshot", "path": out})
    assert r["ok"] and Path(out).exists() and Path(out).stat().st_size > 0


def test_bad_ops(bridge_and_window):
    w, br, _clicks, _tp = bridge_and_window
    c = _Client(br.name)
    assert c.ask({"op": "nope"})["ok"] is False
    r = c.ask({"op": "click", "id": "inesistente"})
    assert r["ok"] is False and "non trovato" in r["error"]
    # json invalido
    c.sock.write(b"questo non e' json\n")
    c.sock.flush()
    buf = b""
    t = QElapsedTimer()
    t.start()
    while b"\n" not in buf and not t.hasExpired(2000):
        _app.processEvents()
        if c.sock.bytesAvailable():
            buf += bytes(c.sock.readAll())
    assert buf, "nessuna risposta dal bridge (timeout)"
    resp = json.loads(buf.split(b"\n")[0].decode("utf-8"))  # noqa: E203
    assert resp["ok"] is False and "json invalido" in resp["error"]


def test_slug():
    assert _slug("  Rileva hardware di nuovo! ") == "rileva_hardware_di_nuovo"
    assert _slug("—") == "btn"


def test_socket_path_resolution(monkeypatch):
    """Verifica la risoluzione deterministica del path del socket."""
    from GUI.remote_bridge import _socket_path, BRIDGE_NAME

    # 1. env override vince su tutto
    monkeypatch.setenv("BYTE_SWARMY_REMOTE_SOCKET", "/custom/path.sock")
    assert _socket_path() == "/custom/path.sock"

    # 2. XDG_RUNTIME_DIR scrivibile → tmpfs per-user
    monkeypatch.delenv("BYTE_SWARMY_REMOTE_SOCKET", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    assert _socket_path() == "/run/user/1000/byte-swarmy-remote.sock"

    # 3. basename custom
    assert _socket_path("altro") == "/run/user/1000/altro.sock"

    # 4. fallback /tmp se XDG non è scrivibile
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/nonexistent/xyz")
    p = _socket_path()
    assert p.startswith("/tmp/") and p.endswith(".sock")
    assert str(os.getuid()) in p or BRIDGE_NAME in p
