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


# Caricamento dinamico dei tool generati (approvati via tool_proposer).
try:
    import importlib.util
    from pathlib import Path
    _gen = Path(__file__).resolve().parent / "generated_tools.py"
    if _gen.exists():
        _spec = importlib.util.spec_from_file_location("CORE.generated_tools", _gen)
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            for _name in getattr(_mod, "__all__", []):
                _obj = getattr(_mod, _name, None)
                if callable(_obj):
                    TOOL_REGISTRY[_name] = _obj
except Exception:
    pass

# Registrazione on-demand di re_tools (reverse engineering).
try:
    from CORE.re_tools import call_re_tool, get_re_tool_descriptions

    def _re_tool(name: str, *args) -> str:
        return call_re_tool(name, list(args))

    TOOL_REGISTRY["re_tool"] = _re_tool
    TOOL_REGISTRY["re_tools_list"] = lambda *a, **k: get_re_tool_descriptions()
except Exception:
    pass
