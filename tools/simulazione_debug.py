#!/usr/bin/env python3
"""simulazione_debug.py — demo del ponte remoto pulsanti (senza PyQt6).

Simula fedelmente il protocollo di GUI/remote_bridge.py + tools/gui_remote.py:
- stesso socket Unix assoluto (/tmp/byte-swarmy-remote.<uid>.sock)
- stesso protocollo JSON newline-delimited
- stesso inventario (id/index/text/enabled/checkable/checked/visible)
- stessi comandi: list, click (id|text|index), screenshot
- stessi codici di uscita e stessi messaggi del client vero

Uso:
    python3 simulazione_debug.py            # sessione demo completa
    python3 simulazione_debug.py --server   # solo server (per testare gui_remote.py vero)
    python3 simulazione_debug.py --client list   # solo client contro il server

Sul tuo PC, dopo aver applicato la patch, puoi far partire questo --server
in un terminale e nell'altro usare il VERO tools/gui_remote.py: parleranno
lo stesso protocollo.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional

SOCKET_PATH = f"/tmp/byte-swarmy-remote.{os.getuid()}.sock"
CHUNK_LIMIT = 64 * 1024


# ─────────────────────────────────────────────────────────────────────
# Mock Control Center: pulsanti realistici di byte-swarmy
# ─────────────────────────────────────────────────────────────────────

class MockButton:
    def __init__(self, text: str, *, object_name: str = "",
                 enabled: bool = True, checkable: bool = False,
                 checked: bool = False, on_click=None):
        self.text = text
        self.object_name = object_name
        self.enabled = enabled
        self.checkable = checkable
        self.checked = checked
        self._on_click = on_click
        self.click_log: list[str] = []

    def click(self):
        if self._on_click:
            self._on_click(self)
        self.click_log.append(time.strftime("%H:%M:%S"))


class MockControlCenter:
    """Finestra finta con i pulsanti tipici del Control Center vero."""

    def __init__(self):
        self.orchestrator_running = False
        self.tabs = ["Coda", "MCP Servers", "Logs", "Timestral", "Config"]
        self.active_tab = "Coda"
        self._build_buttons()

    def _build_buttons(self):
        def toggle_start(b):
            self.orchestrator_running = True
            b.enabled = False  # disabilita dopo il click
            # riabilita "Ferma"
            for x in self.buttons:
                if x.text == "Ferma":
                    x.enabled = True

        def toggle_stop(b):
            self.orchestrator_running = False
            b.enabled = False
            for x in self.buttons:
                if x.text == "Avvia Orchestratore":
                    x.enabled = True

        self.buttons: list[MockButton] = [
            MockButton("Avvia Orchestratore", object_name="act_start",
                       on_click=toggle_start),
            MockButton("Ferma", object_name="act_stop",
                       enabled=False, on_click=toggle_stop),
            MockButton("Esci", object_name="act_quit"),
            MockButton("Aggiungi task", object_name="btn_add_task"),
            MockButton("Reset task", object_name="btn_reset"),
            MockButton("Pulisci completati", object_name="btn_cleanup"),
            MockButton("Rileva hardware", object_name="btn_detect_hw"),
            MockButton("Avvia", object_name="btn_tab_start"),  # duplicato "Avvia"
            MockButton("Pull dal remote", object_name="btn_pull"),
            MockButton("Push su GitHub", object_name="btn_push",
                       enabled=False),  # disabilitato: orchestratore fermo
            MockButton("Apri cartella progetto", object_name="btn_open"),
        ]

    # ── inventario (stesso schema di remote_bridge._inventory) ──
    def inventory(self) -> list[dict]:
        out = []
        for i, b in enumerate(self.buttons):
            out.append({
                "id": b.object_name or _slug(b.text) or f"btn{i}",
                "index": i,
                "text": b.text,
                "object_name": b.object_name,
                "enabled": b.enabled,
                "checkable": b.checkable,
                "checked": b.checked,
                "visible": True,
            })
        return out

    def find_by_id(self, bid: str) -> Optional[MockButton]:
        if "#" in bid:
            base, n = bid.split("#", 1)
            n = int(n) if n.isdigit() else 0
        else:
            base, n = bid, 0
        seen = 0
        for b in self.buttons:
            cid = b.object_name or _slug(b.text)
            if cid == base:
                if seen == n:
                    return b
                seen += 1
        return None

    def find_by_text(self, text: str) -> Optional[MockButton]:
        for b in self.buttons:
            if text in b.text:
                return b
        return None

    def find_by_index(self, idx: int) -> Optional[MockButton]:
        if 0 <= idx < len(self.buttons):
            return self.buttons[idx]
        return None


def _slug(text: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "btn"


# ─────────────────────────────────────────────────────────────────────
# Server: protocollo identico a remote_bridge.py (newline-delimited JSON)
# ─────────────────────────────────────────────────────────────────────

class BridgeServer:
    def __init__(self, path: str = SOCKET_PATH):
        self.path = path
        self.cc = MockControlCenter()
        self._stop = threading.Event()

    def start(self):
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        self.sock.listen(8)
        self.sock.settimeout(0.5)
        sys.stderr.write(f"[remote-bridge] in ascolto su '{self.path}' "
                         f"(tools/gui_remote.py)\n")
        sys.stderr.flush()

    def stop(self):
        self._stop.set()
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    def serve_forever(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        buf = b""
        try:
            while not self._stop.is_set():
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > CHUNK_LIMIT:
                    conn.sendall(b'{"ok":false,"error":"payload troppo grande"}\n')
                    buf = b""
                    continue
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    if not line.strip():
                        continue
                    try:
                        cmd = json.loads(line.decode())
                        resp = self._dispatch(cmd if isinstance(cmd, dict) else {})
                    except json.JSONDecodeError as e:
                        resp = {"ok": False, "error": f"json invalido: {e}"}
                    conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n")
                                 .encode())
        finally:
            conn.close()

    def _dispatch(self, cmd: dict) -> dict:
        op = str(cmd.get("op", ""))
        if op == "list":
            return {"ok": True, "buttons": self.cc.inventory()}
        if op == "click":
            b = self._find(cmd)
            if b is None:
                return {"ok": False, "error": "pulsante non trovato"}
            if not b.enabled:
                return {"ok": False, "error": f"'{b.text}' è disabilitato"}
            b.click()
            return {"ok": True, "clicked": b.text or b.object_name}
        if op == "screenshot":
            path = str(cmd.get("path", ""))
            if not path:
                return {"ok": False, "error": "path mancante"}
            # scrive un PNG fittizio di 1x1 (la GUI vera farebbe grab())
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
            return {"ok": True, "path": path, "size": [800, 600]}
        return {"ok": False, "error": f"op sconosciuta: {op!r}"}

    def _find(self, cmd):
        bid = cmd.get("id")
        if bid is not None:
            return self.cc.find_by_id(str(bid))
        text = cmd.get("text")
        if text is not None:
            return self.cc.find_by_text(str(text))
        idx = cmd.get("index")
        if isinstance(idx, int):
            return self.cc.find_by_index(idx)
        return None


# ─────────────────────────────────────────────────────────────────────
# Client: stesso output di tools/gui_remote.py
# ─────────────────────────────────────────────────────────────────────

def client_roundtrip(socket_path: str, cmd: dict, raw: bool = False) -> int:
    """Replica esattamente l'output umano di tools/gui_remote.py._roundtrip."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(4)
        s.connect(socket_path)
    except (FileNotFoundError, ConnectionRefusedError):
        print(f"❌ GUI non raggiungibile su '{socket_path}' "
              f"(Connection refused).", file=sys.stderr)
        print("   Avvia la GUI con ./byte-swarm.sh gui (bridge attivo di default).",
              file=sys.stderr)
        return 2

    s.sendall((json.dumps(cmd) + "\n").encode())
    buf = b""
    s.settimeout(4)
    while b"\n" not in buf:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            print(f"❌ Nessuna risposta dalla GUI (timeout).", file=sys.stderr)
            return 3
        if not chunk:
            print("❌ Connessione chiusa dalla GUI.", file=sys.stderr)
            return 3
        buf += chunk

    line, _, _ = buf.partition(b"\n")
    try:
        resp = json.loads(line.decode())
    except json.JSONDecodeError as e:
        print(f"❌ Risposta non JSON: {e}\n{line[:200]!r}", file=sys.stderr)
        return 3

    s.close()

    if raw:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0 if resp.get("ok") else 1

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


# ─────────────────────────────────────────────────────────────────────
# Demo: sessione di debug completa
# ─────────────────────────────────────────────────────────────────────

def banner(title: str):
    print()
    print("═" * 70)
    print(f"  {title}")
    print("═" * 70)


def shell(cmd: str):
    """Stampa il prompt shell come se lo avessi digitato."""
    print(f"\n\033[1;32m$\033[0m {cmd}")


def run_client(socket_path: str, cmd: dict, raw: bool = False) -> int:
    rc = client_roundtrip(socket_path, cmd, raw=raw)
    print(f"  \033[2m# exit code: {rc}\033[0m")
    return rc


def main():
    demo = "--server" not in sys.argv and "--client" not in sys.argv

    if "--server" in sys.argv:
        srv = BridgeServer()
        srv.start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            srv.stop()
        return 0

    if "--client" in sys.argv:
        # modalita' client standalone: prendi il subcommand da argv
        args = [a for a in sys.argv[1:] if a != "--client"]
        if not args:
            print("uso: --client <list|click|screenshot> [...]", file=sys.stderr)
            return 2
        sub = args[0]
        if sub == "list":
            return client_roundtrip(SOCKET_PATH, {"op": "list"})
        if sub == "click" and len(args) >= 2:
            return client_roundtrip(SOCKET_PATH, {"op": "click", "id": args[1]})
        if sub == "screenshot" and len(args) >= 2:
            return client_roundtrip(SOCKET_PATH, {"op": "screenshot", "path": args[1]})
        return 2

    # ── DEMO COMPLETO ──────────────────────────────────────────────
    print("\n" + "🐝  BYTE-SWARMY — simulazione debug ponte remoto pulsanti")
    print("    (protocollo identico a GUI/remote_bridge.py + tools/gui_remote.py)")
    print(f"    socket: {SOCKET_PATH}")

    # 1. Avvio server (mock GUI) in background
    banner("1. AVVIO GUI (mock) — il bridge parte in ascolto")
    srv = BridgeServer(SOCKET_PATH)
    srv.start()
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    print("  [GUI] Control Center pronto. Bridge attivo (parent=window).")

    # 2. list
    banner("2. INVENTARIO PULSANTI")
    shell(".venv/bin/python tools/gui_remote.py list")
    run_client(SOCKET_PATH, {"op": "list"})

    # 3. click per id
    banner("3. CLICK PER ID — Avvia Orchestratore")
    shell(".venv/bin/python tools/gui_remote.py click act_start")
    run_client(SOCKET_PATH, {"op": "click", "id": "act_start"})
    print(f"  [GUI] orchestrator_running = {srv.cc.orchestrator_running}")

    # 4. riprova lo stesso pulsante (ora disabilitato)
    banner("4. CLICK SU PULSANTE ORA DISABILITATO")
    shell(".venv/bin/python tools/gui_remote.py click act_start")
    run_client(SOCKET_PATH, {"op": "click", "id": "act_start"})

    # 5. click per testo
    banner("5. CLICK PER TESTO — 'Ferma'")
    shell('.venv/bin/python tools/gui_remote.py click --text "Ferma"')
    run_client(SOCKET_PATH, {"op": "click", "text": "Ferma"})
    print(f"  [GUI] orchestrator_running = {srv.cc.orchestrator_running}")

    # 6. click per indice
    banner("6. CLICK PER INDICE — index 5 (Pulisci completati)")
    shell(".venv/bin/python tools/gui_remote.py click --index 5")
    run_client(SOCKET_PATH, {"op": "click", "index": 5})

    # 7. screenshot
    banner("7. SCREENSHOT DELLA FINESTRA")
    out_png = "/tmp/cc-debug.png"
    shell(f".venv/bin/python tools/gui_remote.py screenshot {out_png}")
    run_client(SOCKET_PATH, {"op": "screenshot", "path": out_png})
    print(f"  [filesystem] {out_png} ({Path(out_png).stat().st_size} byte)")

    # 8. id inesistente
    banner("8. ERRORE — id inesistente")
    shell(".venv/bin/python tools/gui_remote.py click does_not_exist")
    run_client(SOCKET_PATH, {"op": "click", "id": "does_not_exist"})

    # 9. op sconosciuta (raw mode)
    banner("9. ERRORE — op sconosciuta (modalità --raw)")
    shell('.venv/bin/python tools/gui_remote.py list --raw   # solo per demo op=nope')
    run_client(SOCKET_PATH, {"op": "nope"}, raw=True)

    # 10. list di nuovo (stato mutato)
    banner("10. INVENTARIO DOPO I CLICK (stato mutato)")
    shell(".venv/bin/python tools/gui_remote.py list")
    run_client(SOCKET_PATH, {"op": "list"})

    # 11. raw mode su list (prime 3 righe sfilate)
    banner("11. MODALITÀ --raw (JSON puro, per pipe/scripts)")
    shell(".venv/bin/python tools/gui_remote.py list --raw | head -20")
    # per la demo stampiamo solo i primi 20 elementi del JSON
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCKET_PATH)
    s.sendall(b'{"op":"list"}\n')
    buf = b""
    while b"\n" not in buf:
        buf += s.recv(4096)
    s.close()
    resp = json.loads(buf.split(b"\n")[0].decode())
    # stampa solo primi 3 bottoni per non annegare
    resp["buttons"] = resp["buttons"][:3]
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    print(f"  \033[2m# (troncati a 3 pulsanti per la demo)\033[0m")

    # chiusura
    banner("12. CHIUSURA")
    shell("^C  # chiudi la GUI")
    srv.stop()
    print("  [GUI] Control Center chiuso. Socket rimosso.")
    print(f"  [filesystem] {SOCKET_PATH} exists: {Path(SOCKET_PATH).exists()}")

    print("\n✓ Simulazione completata. Sul tuo PC, dopo la patch, l'output sara'")
    print("  identico: cambia solo che il server e' la GUI PyQt6 vera e il")
    print("  screenshot sara' un PNG reale della finestra.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
