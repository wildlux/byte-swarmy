#!/usr/bin/env python
"""gui_remote.py — client del ponte remoto dei pulsanti della GUI.

Uso:
    .venv/bin/python tools/gui_remote.py list                     # inventario
    .venv/bin/python tools/gui_remote.py click avvia              # click per id
    .venv/bin/python tools/gui_remote.py click --text "Avvia"     # per testo
    .venv/bin/python tools/gui_remote.py click --index 5          # per posizione
    .venv/bin/python tools/gui_remote.py screenshot /tmp/g.png    # grab finestra
    .venv/bin/python tools/gui_remote.py <cmd> --raw              # solo JSON

Il servizio è dentro la GUI (QLocalServer, vedi GUI/remote_bridge.py):
la GUI deve essere attiva. Socket: vedi SOCKET_PATH in remote_bridge
($XDG_RUNTIME_DIR/byte-swarmy-remote.sock di default).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from PyQt6.QtNetwork import QLocalSocket

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from GUI.remote_bridge import SOCKET_PATH  # noqa: E402

TIMEOUT_MS = 4000


def _roundtrip(cmd: Dict[str, Any], raw: bool = False) -> int:
    sock = QLocalSocket()
    # Path assoluto → fullServerName() non viene risolto da Qt, mai "Invalid name".
    sock.connectToServer(SOCKET_PATH)
    if not sock.waitForConnected(TIMEOUT_MS):
        print(f"❌ GUI non raggiungibile su '{SOCKET_PATH}' "
              f"({sock.errorString()}).", file=sys.stderr)
        print("   Avvia la GUI con ./byte-swarm.sh gui (bridge attivo di default).",
              file=sys.stderr)
        return 2

    payload = (json.dumps(cmd) + "\n").encode("utf-8")
    sock.write(payload)
    sock.flush()

    buf = b""
    while b"\n" not in buf:
        if not sock.waitForReadyRead(TIMEOUT_MS):
            print(f"❌ Nessuna risposta dalla GUI "
                  f"({sock.errorString()}).", file=sys.stderr)
            return 3
        buf += bytes(sock.readAll())

    line, _, _ = buf.partition(b"\n")
    try:
        resp = json.loads(line.decode("utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ Risposta non JSON: {e}\n{line[:200]!r}", file=sys.stderr)
        return 3

    sock.disconnectFromServer()

    if raw:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0 if resp.get("ok") else 1

    # Umano
    if cmd.get("op") == "list":
        for b in resp.get("buttons", []):
            flag = "✓" if b["enabled"] else "✗"
            mark = "☑" if b.get("checked") else " "
            extra = f" aria={b['object_name']}" if b["object_name"] else ""
            print(f"  [{flag}][{mark}] {b['id']:<40} «{b['text'][:46]}»{extra}")
        n = len(resp.get("buttons", []))
        print(f"  ({n} pulsanti — simula con: click <id>)")
        return 0

    if resp.get("ok"):
        print(f"✅ {json.dumps(resp, ensure_ascii=False)}")
        return 0
    print(f"❌ {resp.get('error', 'errore')}", file=sys.stderr)
    return 1


def main(argv: Optional[list] = None) -> int:
    # QCoreApplication serve per risolvere i nomi dei socket locali;
    # core (non GUI) basta per il client sincrono.
    from PyQt6.QtCore import QCoreApplication
    if QCoreApplication.instance() is None:
        QCoreApplication(sys.argv)

    p = argparse.ArgumentParser(description="Client ponte pulsanti GUI")
    p.add_argument("--raw", action="store_true", help="output JSON puro")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="inventario pulsanti")

    c = sub.add_parser("click", help="simula un click")
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("id", nargs="?", help="id dell'inventario")
    g.add_argument("--text", help="match sul testo del pulsante")
    g.add_argument("--index", type=int, help="posizione nell'inventario")

    s = sub.add_parser("screenshot", help="grab della finestra")
    s.add_argument("path", help="file PNG di destinazione")

    a = p.parse_args(argv)
    if a.cmd == "list":
        return _roundtrip({"op": "list"}, a.raw)
    if a.cmd == "click":
        body: Dict[str, Any] = {"op": "click"}
        if a.id is not None:
            body["id"] = a.id
        elif a.text is not None:
            body["text"] = a.text
        else:
            body["index"] = a.index
        return _roundtrip(body, a.raw)
    if a.cmd == "screenshot":
        return _roundtrip({"op": "screenshot", "path": a.path})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
