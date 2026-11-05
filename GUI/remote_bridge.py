"""remote_bridge.py — ponte remoto per simulare i pulsanti della GUI.

Servizio IN ASCOLTO dentro il processo Qt: un `QLocalServer` (socket Unix
locale, solo lo stesso utente) riceve comandi JSON riga-per-riga:

    {"op": "list"}                            → inventario pulsanti
    {"op": "click", "id": "..."}              → click per id univoco
    {"op": "click", "text": "..."}            → click per testo (contiene)
    {"op": "click", "index": 3}               → click per posizione
    {"op": "screenshot", "path": "/tmp/x.png"} → grab della finestra

Client ufficiale: `tools/gui_remote.py` (subcommand list/click/screenshot).
Zero thread dedicati: dispatch via segnale newConnection sull'event loop
Qt — nessun blocco del main thread. Abilitato di default; per disattivare:
env BYTE_SWARMY_REMOTE=0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QByteArray
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QPushButton, QToolButton, QWidget,
)

BRIDGE_NAME = "byte-swarmy-remote"
_CHUNK_LIMIT = 64 * 1024


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "btn"


class ButtonBridge(QObject):
    """Inventario e simulazione click dei pulsanti della finestra."""

    def __init__(self, window: QWidget, name: str = BRIDGE_NAME) -> None:
        super().__init__(window)
        self._window = window
        self._server: Optional[QLocalServer] = None
        self._sock: Dict[Any, dict] = {}   # socket -> buffer stato parziale
        self._name = ""
        self._alive = True
        self.destroyed.connect(lambda: setattr(self, "_alive", False))
        self.listen(name)

    # ── Server ──────────────────────────────────────────────────────
    def listen(self, name: str) -> bool:
        name = self._cleanup_and_listen(name)
        if self._server is None:
            # fallback: nome con pid (istanza multipla)
            self._cleanup_and_listen(f"{name}-{os.getpid()}")
        return self._server is not None

    def _cleanup_and_listen(self, name: str) -> None:
        QLocalServer.removeServer(name)   # elimina socket stantio
        srv = QLocalServer(self)
        srv.newConnection.connect(self._on_connection)
        if srv.listen(name):
            self._server = srv
            self._name = name
        else:
            srv.deleteLater()

    @property
    def name(self) -> str:
        return self._name

    def close(self) -> None:
        """Arresta il server e disconnette i client ancora aperti."""
        self._alive = False
        for sock in list(self._sock):
            try:
                sock.disconnectFromServer()
            except RuntimeError:
                pass
        self._sock.clear()
        if self._server is not None:
            try:
                self._server.close()
                self._server.deleteLater()
            except RuntimeError:
                pass
            self._server = None

    # ── Inventario ──────────────────────────────────────────────────
    def _buttons(self) -> List[type]:
        out: List[type] = list(self._window.findChildren(QPushButton))
        out += list(self._window.findChildren(QToolButton))
        return out

    def _targets(self) -> List[tuple]:
        """[(base_id, occorrenza_n, pulsante)] — fonte unica di id."""
        seen: Dict[str, int] = {}
        out: List[tuple] = []
        for i, b in enumerate(self._buttons()):
            base = b.objectName() or _slug(b.text() or "") or f"btn{i}"
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.append((base, n, b))
        return out

    def _inventory(self) -> List[Dict[str, Any]]:
        inv: List[Dict[str, Any]] = []
        for i, (base, n, b) in enumerate(self._targets()):
            text = (b.text() or "").strip().replace("\n", " ")
            inv.append({
                "id": base if n == 0 else f"{base}#{n}",
                "index": i,
                "text": text,
                "object_name": b.objectName(),
                "enabled": b.isEnabled(),
                "checkable": b.isCheckable(),
                "checked": b.isChecked(),
                "visible": b.isVisible(),
            })
        return inv

    # ── Dispatch comandi ────────────────────────────────────────────
    def _handle(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        op = str(cmd.get("op", ""))
        if op == "list":
            return {"ok": True, "buttons": self._inventory()}
        if op == "click":
            b = self._find_target(cmd)
            if b is None:
                return {"ok": False, "error": "pulsante non trovato"}
            if not b.isEnabled():
                return {"ok": False,
                        "error": f"'{b.text()}' è disabilitato"}
            b.click()
            return {"ok": True, "clicked": (b.text() or b.objectName())}
        if op == "screenshot":
            path = str(cmd.get("path", ""))
            if not path:
                return {"ok": False, "error": "path mancante"}
            pm = self._window.grab()
            ok = bool(pm.save(path)) if pm else False
            return {"ok": ok, "path": path,
                    "size": [pm.width(), pm.height()] if pm else None}
        return {"ok": False, "error": f"op sconosciuta: {op!r}"}

    def _find_target(self, cmd: Dict[str, Any]) -> Optional[QWidget]:
        bid = cmd.get("id")
        if bid is not None:
            want_base, want_n = str(bid), 0
            if "#" in want_base:
                want_base, want_n = want_base.split("#", 1)
                want_n = int(want_n) if want_n.isdigit() else 0
            for base, n, b in self._targets():
                if base == want_base and n == want_n:
                    return b
            return None
        text = cmd.get("text")
        if text is not None:
            matches = [b for b in self._buttons()
                       if str(text) in b.text()]
            return matches[0] if matches else None
        index = cmd.get("index")
        if isinstance(index, int) and 0 <= index < len(self._buttons()):
            return self._buttons()[index]
        return None

    # ── Socket I/O (event-driven) ───────────────────────────────────
    def _on_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            if sock is None:
                continue
            self._sock[sock] = {"buf": bytearray()}
            sock.readyRead.connect(lambda s=sock: self._on_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_closed(s))

    def _on_read(self, sock: Any) -> None:
        if not self._alive:
            return
        st = self._sock.get(sock)
        if st is None:
            return
        data: QByteArray = sock.readAll()
        st["buf"] += bytes(data)
        if len(st["buf"]) > _CHUNK_LIMIT:
            sock.write(b'{"ok":false,"error":"payload troppo grande"}\n')
            st["buf"].clear()
            return
        while b"\n" in st["buf"]:
            line, _, rest = bytes(st["buf"]).partition(b"\n")
            st["buf"] = bytearray(rest)
            if not line.strip():
                continue
            try:
                cmd = json.loads(line.decode("utf-8"))
                resp = self._handle(cmd if isinstance(cmd, dict) else {})
            except json.JSONDecodeError as e:
                resp = {"ok": False, "error": f"json invalido: {e}"}
            sock.write((json.dumps(resp, ensure_ascii=False) + "\n")
                       .encode("utf-8"))
            sock.flush()

    def _on_closed(self, sock: Any) -> None:
        if not self._alive:
            return
        self._sock.pop(sock, None)
        try:
            sock.deleteLater()
        except RuntimeError:
            pass


def start_button_bridge(window: QWidget) -> Optional[ButtonBridge]:
    """Avvia il bridge sulla finestra principale del Control Center.

    Opt-out via env BYTE_SWARMY_REMOTE=0. Mai raise: la GUI deve partire
    anche se il socket locale non è disponibile.
    """
    if os.environ.get("BYTE_SWARMY_REMOTE", "1").strip() == "0":
        return None
    try:
        bridge = ButtonBridge(window)
        if bridge.name:
            print(f"[remote-bridge] in ascolto su '{bridge.name}' "
                  f"(tools/gui_remote.py)", file=sys.stderr)
            return bridge
        return None
    except Exception as e:   # pragma: no cover - fail-open per la GUI
        print(f"[remote-bridge] non disponibile: {e}", file=sys.stderr)
        return None
