"""
example_mcp_server.py — Server MCP di esempio per testare la GUI.

Espone il tool `get_pending_tasks` che ritorna una lista di task hardcoded.
Avvio:
    pip install mcp uvicorn
    python example_mcp_server.py

Poi nella GUI:
    Tab "MCP Servers" → "Aggiungi Server"
    Nome: example
    URL:  http://localhost:8080/sse
    Tool name: get_pending_tasks

Vedrai i task arrivare nella coda ogni 30s.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# MCP SDK
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
import uvicorn


server = Server("byte-swarmy-example")

# File dove tiene i task "in uscita"
TASKS_OUTBOX = Path("./example_mcp_outbox.json")


def _load_outbox() -> list:
    if not TASKS_OUTBOX.exists():
        # Crea con 2 task di esempio
        sample = [
            {
                "title": "Implementa reverse string in Python",
                "description": "Funzione reverse_string(s) che ritorna la stringa invertita. "
                               "Salva in project/reverse.py. Test: reverse_string('hello') == 'olleh'.",
                "context": "progetto nuovo",
            },
            {
                "title": "Implementa fattoriale iterativo",
                "description": "Funzione factorial(n) che calcola n! in modo iterativo. "
                               "Salva in project/factorial.py. Test: factorial(5) == 120.",
                "context": "progetto nuovo",
            },
        ]
        TASKS_OUTBOX.write_text(json.dumps(sample, indent=2))
        return sample
    return json.loads(TASKS_OUTBOX.read_text())


def _save_outbox(tasks: list) -> None:
    TASKS_OUTBOX.write_text(json.dumps(tasks, indent=2))


@server.list_tools()
async def list_tools():
    from mcp.types import Tool
    return [
        Tool(
            name="get_pending_tasks",
            description="Returns the list of pending tasks to be executed by BYTE-SWARMY.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="add_task",
            description="Add a new task to the outbox. Useful for external systems to push work.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        ),
        Tool(
            name="clear_outbox",
            description="Empty the outbox (mark all tasks as delivered).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    from mcp.types import TextContent

    if name == "get_pending_tasks":
        tasks = _load_outbox()
        # Svuota la outbox dopo averli inviati (convenzione: una tantum)
        _save_outbox([])
        return [TextContent(
            type="text",
            text=json.dumps(tasks, ensure_ascii=False)
        )]

    elif name == "add_task":
        tasks = _load_outbox()
        new_task = {
            "title": arguments["title"],
            "description": arguments["description"],
            "context": arguments.get("context", ""),
            "added_at": time.time(),
        }
        tasks.append(new_task)
        _save_outbox(tasks)
        return [TextContent(type="text", text=json.dumps({"ok": True, "count": len(tasks)}))]

    elif name == "clear_outbox":
        _save_outbox([])
        return [TextContent(type="text", text=json.dumps({"ok": True}))]

    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool {name}"}))]


# SSE transport
sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (r, w):
        await server.run(r, w, server.create_initialization_options())


app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)


if __name__ == "__main__":
    print("=== Example MCP Server ===")
    print(f"Endpoint SSE: http://localhost:8080/sse")
    print(f"Outbox file: {TASKS_OUTBOX.absolute()}")
    print("Tool esposti: get_pending_tasks, add_task, clear_outbox")
    print()
    print("Nella GUI BYTE-SWARMY:")
    print("  Tab MCP Servers → Aggiungi Server")
    print("  Nome: example")
    print("  URL:  http://localhost:8080/sse")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
