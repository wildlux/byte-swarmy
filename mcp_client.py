"""
mcp_client.py — MCPClient class
Client MCP (Model Context Protocol) per ricevere task da server esterni.

Supporta:
- Connessione via SSE (Server-Sent Events) HTTP
- Discovery dei tool esposti dal server
- Polling periodico di un tool "get_pending_tasks" (convenzione)
- Riconnessione automatica

Il modulo `mcp` è opzionale: se non installato, la GUI funziona comunque
solo con task locali.
"""

from __future__ import annotations

import json
import time
import threading
import urllib.request
import urllib.error
from typing import Optional, Callable
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Fallback se il package `mcp` non è installato
# ---------------------------------------------------------------------------

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    MCP_AVAILABLE = True
    MCP_IMPORT_ERROR = None
except ImportError as e:
    MCP_AVAILABLE = False
    MCP_IMPORT_ERROR = str(e)
    ClientSession = None
    sse_client = None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class McpServerConfig:
    """Configurazione di un server MCP esterno."""
    name: str
    url: str                       # es. http://localhost:8080/sse
    enabled: bool = True
    poll_interval: int = 30        # secondi tra un poll e l'altro
    tool_name: str = "get_pending_tasks"   # convenzione: il server espone questo tool
    last_poll: float = 0.0
    last_status: str = "disconnected"      # disconnected | connecting | connected | error
    last_error: str = ""
    tasks_received: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name, "url": self.url, "enabled": self.enabled,
            "poll_interval": self.poll_interval, "tool_name": self.tool_name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "McpServerConfig":
        return cls(
            name=d.get("name", "unnamed"),
            url=d.get("url", ""),
            enabled=d.get("enabled", True),
            poll_interval=d.get("poll_interval", 30),
            tool_name=d.get("tool_name", "get_pending_tasks"),
        )


# ---------------------------------------------------------------------------
# MCP Client
# ---------------------------------------------------------------------------

class MCPClient:
    """
    Gestisce una o più connessioni a server MCP esterni.
    Esegue il polling in un thread separato e notifica via callback
    quando riceve nuovi task.

    Uso tipico (da GUI Qt):
        client = MCPClient(on_task_received=my_callback)
        client.add_server(McpServerConfig(name="local", url="http://localhost:8080/sse"))
        client.start()   # avvia thread di polling
        # ...
        client.stop()
    """

    def __init__(self,
                 on_task_received: Optional[Callable[[str, dict], None]] = None,
                 on_status_changed: Optional[Callable[[str, str], None]] = None,
                 logger=None):
        self.servers: dict[str, McpServerConfig] = {}
        self.on_task_received = on_task_received
        self.on_status_changed = on_status_changed
        self.log = logger

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Stato della connessione corrente (per tool discovery)
        self._available_tools: dict[str, list[str]] = {}  # server_name -> [tool_name]

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def add_server(self, config: McpServerConfig) -> None:
        if not self._valid_url(config.url):
            self._log("error", f"invalid MCP url for {config.name}: {config.url!r}")
            return
        with self._lock:
            self.servers[config.name] = config
        self._notify_status(config.name, config.last_status)

    def remove_server(self, name: str) -> None:
        with self._lock:
            self.servers.pop(name, None)
            self._available_tools.pop(name, None)

    def update_server(self, name: str, **kwargs) -> None:
        with self._lock:
            if name not in self.servers:
                return
            srv = self.servers[name]
            for k, v in kwargs.items():
                if hasattr(srv, k):
                    setattr(srv, k, v)

    def list_servers(self) -> list[McpServerConfig]:
        with self._lock:
            return list(self.servers.values())

    def start(self) -> bool:
        """Avvia il thread di polling. Ritorna True se partito."""
        if not MCP_AVAILABLE:
            self._log("error", f"mcp package not available: {MCP_IMPORT_ERROR}")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="mcp-poll")
        self._thread.start()
        self._log("info", "MCP polling thread started")
        return True

    def stop(self) -> None:
        """Ferma il thread di polling (graceful)."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._log("info", "MCP polling thread stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def discover_tools(self, server_name: str) -> list[str]:
        """Forza la discovery dei tool di un server. Ritorna la lista nomi."""
        if not MCP_AVAILABLE:
            return []
        with self._lock:
            srv = self.servers.get(server_name)
            if not srv:
                return []
        try:
            tools = self._do_list_tools(srv)
            with self._lock:
                self._available_tools[server_name] = tools
            return tools
        except Exception as e:
            self._log("error", f"discover_tools({server_name}) failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Loop di polling (private)
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Loop principale: ogni secondo guarda quale server va pollato."""
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                servers = list(self.servers.values())

            for srv in servers:
                if self._stop_event.is_set():
                    break
                if not srv.enabled:
                    continue
                if now - srv.last_poll < srv.poll_interval:
                    continue

                self._poll_one(srv)
                srv.last_poll = now

            self._stop_event.wait(timeout=1.0)

    def _poll_one(self, srv: McpServerConfig) -> None:
        """Polla un singolo server MCP per nuovi task."""
        if not self._valid_url(srv.url):
            srv.last_error = "invalid url"
            self._set_status(srv, "error")
            return
        self._set_status(srv, "connecting")

        try:
            # Usa l'API sincrona di mcp client via SSE
            tasks = self._do_get_tasks(srv)
            self._set_status(srv, "connected")

            for task in tasks:
                srv.tasks_received += 1
                if self.on_task_received:
                    try:
                        self.on_task_received(srv.name, task)
                    except Exception as e:
                        self._log("error", f"on_task_received callback failed: {e}")

        except Exception as e:
            srv.last_error = str(e)
            self._set_status(srv, "error")
            self._log("warning", f"poll {srv.name} failed: {e}")

    def _do_get_tasks(self, srv: McpServerConfig) -> list[dict]:
        """Apre una sessione MCP via SSE, chiama il tool, chiude."""
        if not MCP_AVAILABLE:
            return []

        # Pattern ufficiale: async context manager
        import asyncio
        return asyncio.run(self._async_get_tasks(srv))

    async def _async_get_tasks(self, srv: McpServerConfig) -> list[dict]:
        """Versione async della chiamata MCP via SSE."""
        async with sse_client(url=srv.url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Verifica che il tool esista
                tools_resp = await session.list_tools()
                tool_names = [t.name for t in tools_resp.tools]
                with self._lock:
                    self._available_tools[srv.name] = tool_names

                if srv.tool_name not in tool_names:
                    self._log("warning",
                              f"server {srv.name} has no tool '{srv.tool_name}'. "
                              f"Available: {tool_names}")
                    return []

                # Chiama il tool
                result = await session.call_tool(srv.tool_name, {})
                return self._parse_tool_result(result)

    def _do_list_tools(self, srv: McpServerConfig) -> list[str]:
        """Lista i tool esposti da un server MCP."""
        if not MCP_AVAILABLE:
            return []
        import asyncio
        return asyncio.run(self._async_list_tools(srv))

    async def _async_list_tools(self, srv: McpServerConfig) -> list[str]:
        async with sse_client(url=srv.url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resp = await session.list_tools()
                return [t.name for t in resp.tools]

    def _parse_tool_result(self, result) -> list[dict]:
        """Parse della risposta del tool MCP. Supporta vari formati."""
        # result è CallToolResult con .content (lista di content items)
        tasks = []
        if not hasattr(result, "content"):
            return tasks

        for item in result.content:
            # item può essere TextContent, ImageContent, ecc.
            text = getattr(item, "text", None)
            if not text:
                continue
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    tasks.extend(data)
                elif isinstance(data, dict):
                    if "tasks" in data and isinstance(data["tasks"], list):
                        tasks.extend(data["tasks"])
                    else:
                        tasks.append(data)
            except json.JSONDecodeError:
                # text non è JSON, lo trattiamo come descrizione singola
                tasks.append({"title": "task-from-mcp", "description": text})
        return tasks

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _valid_url(url: str) -> bool:
        """Solo http/https con host: niente file://, schemi esotici o URL vuoti."""
        if not isinstance(url, str) or not url.strip():
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url.strip())
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def _set_status(self, srv: McpServerConfig, status: str) -> None:
        srv.last_status = status
        self._notify_status(srv.name, status)

    def _notify_status(self, name: str, status: str) -> None:
        if self.on_status_changed:
            try:
                self.on_status_changed(name, status)
            except Exception:
                pass

    def _log(self, level: str, msg: str) -> None:
        if self.log:
            getattr(self.log, level, self.log.info)(f"[MCP] {msg}")
