"""
CORE/tool_registry.py — Tool registry leggero per BYTE-SWARMY.

Estratto da CORE/tools.py per ridurre il monolite.

Nuovi tool possono essere registrati senza toccare ToolSet. I metodi
esistenti di ToolSet continuano a funzionare; il registry serve per
tool esterni/plugin e per il dispatch dinamico.
"""

from __future__ import annotations

from typing import Callable, Optional

TOOL_REGISTRY: dict[str, Callable] = {}


def register_tool(name: str):
    """Decorator per registrare un tool nel registry.

    Esempio:
        @register_tool("mio_tool")
        def mio_tool(ctx, path: str) -> str:
            return "ok"

    Poi: ``get_tool("mio_tool")(ctx, path)``.
    """
    def deco(fn):
        TOOL_REGISTRY[name] = fn
        return fn
    return deco


def get_tool(name: str) -> Optional[Callable]:
    """Ritorna il tool registrato con quel nome, o None."""
    return TOOL_REGISTRY.get(name)


def list_tools() -> list:
    """Lista dei nomi dei tool registrati."""
    return sorted(TOOL_REGISTRY)
