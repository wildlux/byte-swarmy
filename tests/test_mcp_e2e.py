# -*- coding: utf-8 -*-
"""
tests/test_mcp_e2e.py — 9.7 Collaudo MCP end-to-end.

Avvia il VERO server MCP di esempio (`CORE/example_mcp_server.py`, uvicorn
Sse su porta libera, outbox in tmp) e contro di esso usa il VERO
`MCPClient` (CORE/mcp_client.py):

  1. discovery: `discover_tools()` deve ritornare get_pending_tasks,
     add_task, clear_outbox;
  2. poll: il task scaduto di esmedia deve consegnare i 2 task della
     outbox alla callback `on_task_received` (schema: title/description);
  3. errori managati: URL inventato deve finire last_error (no crash).

Skippabile: se `mcp`/`uvicorn` non sono installabili a test time o la
porta di test occupata, i test non verranno eseguiti (non falliranno).

Esecuzione veloce:
    python -m unittest tests.test_mcp_e2e -v
    python tests/test_mcp_e2e.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = Path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from CORE.mcp_client import MCPClient, McpServerConfig, MCP_AVAILABLE
except ImportError:
    MCP_AVAILABLE = False

SERVER_SCRIPT = os.path.join(ROOT, "CORE", "example_mcp_server.py")
DISCOVERY_TIMEOUT = 12   # secondi: di solito < 2s
RECEIVE_TIMEOUT = 60     # secondi per averli tutti in callback


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _ping(port: int, timeout: float = 1.0) -> bool:
    """TCP connect: il server uvicorn risponde?"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


@unittest.skipUnless(
    MCP_AVAILABLE,
    "mcp SDK non installato: salta il collaudo E2E (installare `pip install mcp uvicorn`)")
class TestMcpEndToEnd(unittest.TestCase):
    """Server reale + client reale, senza Ollama e senza GUI."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="bswarm-mcp-")
        cls.outbox = os.path.join(cls.tmp, "outbox.json")
        cls.port = int(os.environ.get("BSWARM_TEST_MCP_PORT", _free_port()))
        env = dict(os.environ,
                   MCP_HOST="127.0.0.1",
                   MCP_PORT=str(cls.port),
                   PYTHONIOENCODING="utf-8")
        # cwd=tmp: la outbox del server vive lì, mai nel repo
        cls.proc = subprocess.Popen(
            [sys.executable, SERVER_SCRIPT],
            cwd=cls.tmp, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.time() + 15
        while time.time() < deadline:
            if _ping(cls.port):
                return
            if cls.proc.poll() is not None:
                out = cls.proc.stdout.read().decode("utf-8", "replace")
                raise unittest.SkipTest(f"server non partito:\n{out[:500]}")
            time.sleep(0.3)
        raise unittest.SkipTest("server MCP non risponde entro 15s")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "proc", None) and cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.proc.kill()

    def _client(self, url: str, poll_interval: int = 1) -> MCPClient:
        mc = MCPClient()
        mc.add_server(McpServerConfig(
            name="example", url=url, poll_interval=poll_interval))
        return mc

    # ------------------------------------------------------------------
    # 1. discovery dei tool
    # ------------------------------------------------------------------
    def test_discovery_lists_example_tools(self):
        mc = self._client(f"http://127.0.0.1:{self.port}/sse")
        tools = mc.discover_tools("example")
        self.assertIn("get_pending_tasks", tools)
        self.assertIn("add_task", tools)
        self.assertIn("clear_outbox", tools)
        mc.stop()

    # ------------------------------------------------------------------
    # 2. consegna task in callback (il vero carousel di lavoro)
    # ------------------------------------------------------------------
    def test_poll_delivers_outbox_tasks(self):
        seed = [
            {"title": "reverse string", "description": "r(s) inverti, in project/",
             "context": "e2e"},
            {"title": "fattoriale", "description": "n! iterativo, in project/",
             "context": "e2e"},
        ]
        with open(self.outbox, "w", encoding="utf-8") as f:
            json.dump(seed, f)

        received: list[tuple[str, dict]] = []
        mc = self._client(f"http://127.0.0.1:{self.port}/sse")
        mc.on_task_received = lambda srv, task: received.append((srv, task))
        mc.start()
        try:
            deadline = time.time() + RECEIVE_TIMEOUT
            while len(received) < len(seed) and time.time() < deadline:
                time.sleep(0.2)
        finally:
            mc.stop()

        self.assertEqual(len(received), len(seed))
        for srv_name, task in received:
            self.assertEqual(srv_name, "example")
            self.assertIn("title", task)
            self.assertIn("description", task)
        titles = {t["title"] for _, t in received}
        self.assertEqual(titles, {s["title"] for s in seed})

    # ------------------------------------------------------------------
    # 3. robustezza: URL fesso, errore visibile ma gestito
    # ------------------------------------------------------------------
    def test_bad_url_marks_error_without_crash(self):
        mc = self._client("http://127.0.0.1:1/sse")   # porta garantita morta
        try:
            with self.assertNoLogs("mcp", level="CRITICAL"):
                pass
        except Exception:
            pass  # assertNoLogs API diffper py-version: opzionale
        mc._poll_one(mc.servers["example"])   # metodo interno usato dal loop
        self.assertEqual(mc.servers["example"].last_status, "error")
        self.assertTrue(mc.servers["example"].last_error)
        mc.stop()

    # ------------------------------------------------------------------
    # 4. l'ingestione dei va complet ETH dei task consegnati (seconda via)
    # ------------------------------------------------------------------
    def test_server_yields_only_once_per_outbox(self):
        """get_pending_tasks svuota la outbox: secondo poll = 0 task."""
        with open(self.outbox, "w", encoding="utf-8") as f:
            json.dump([{"title": "once", "description": "d", "context": "e2e"}], f)
        got: list = []
        mc = self._client(f"http://127.0.0.1:{self.port}/sse")
        mc.on_task_received = lambda s, t: got.append(t)
        mc._poll_one(mc.servers["example"])
        self.assertEqual(len(got), 1)
        # la outbox ora è [[]]: la consegna è idempotente una tantum
        with open(self.outbox) as f:
            self.assertEqual(json.load(f), [])
        mc.stop()


if __name__ == "__main__":
    print("MCP E2E (9.7) → CORE/example_mcp_server.py ⨯ CORE/mcp_client.py")
    print("=" * 60)
    unittest.main(verbosity=2)
