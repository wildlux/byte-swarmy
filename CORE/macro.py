"""CORE/macro.py — Macro: pipeline che combina skill + tool + MCP.

Una macro è una sequenza di passi (skill, tool, mcp) eseguiti in ordine,
dove l'output di un passo diventa contesto per il successivo. Serve a
trattare una "famiglia di problemi" (analisi → implementazione → test →
deploy) come un'unica operazione composta.

Tipi di passo:
  - {"type": "skill", "id": "...", "context": "..."}
  - {"type": "tool",  "name": "...", "args": [...]}
  - {"type": "mcp",   "server": "...", "tool": "...", "args": {...}}

Fail-open: un passo fallito non blocca la macro (salvo stop_on_error).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger("byte-swarmy.macro")


@dataclass
class MacroStep:
    """Un passo della macro."""
    type: str  # skill | tool | mcp
    payload: dict = field(default_factory=dict)
    result: Optional[str] = None
    ok: bool = True
    error: Optional[str] = None


@dataclass
class MacroResult:
    """Risultato dell'esecuzione della macro."""
    steps: list[MacroStep] = field(default_factory=list)
    final_output: str = ""
    ok: bool = True

    @property
    def failed(self) -> list[MacroStep]:
        return [s for s in self.steps if not s.ok]


class MacroRunner:
    """Esegue una macro (sequenza di skill/tool/mcp).

    Usage:
        runner = MacroRunner(skill_executor, tool_caller, mcp_client)
        runner.add_skill("py-cli-script", context="crea hello.py")
        runner.add_tool("lint_code", ["project/hello.py"])
        runner.add_tool("run_test_suite", [])
        result = runner.run(task, model_key="worker_coder")
    """

    def __init__(self, skill_executor: Optional[Callable] = None,
                 tool_caller: Optional[Callable] = None,
                 mcp_client: Optional[Any] = None,
                 stop_on_error: bool = False):
        self.skill_executor = skill_executor
        self.tool_caller = tool_caller
        self.mcp_client = mcp_client
        self.stop_on_error = stop_on_error
        self._steps: list[MacroStep] = []

    def add(self, step_type: str, **payload) -> "MacroRunner":
        self._steps.append(MacroStep(type=step_type, payload=payload))
        return self

    def add_skill(self, skill_id: str, context: str = "", title: str = "") -> "MacroRunner":
        return self.add("skill", skill_id=skill_id, context=context, title=title)

    def add_tool(self, name: str, args: list | None = None) -> "MacroRunner":
        return self.add("tool", name=name, args=list(args or []))

    def add_mcp(self, server: str, tool: str, args: dict | None = None) -> "MacroRunner":
        return self.add("mcp", server=server, tool=tool, args=dict(args or {}))

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> list[MacroStep]:
        return list(self._steps)

    def run(self, task: dict, model_key: str = "worker_coder") -> MacroResult:
        result = MacroResult()
        accumulated = ""
        for step in self._steps:
            step.payload.setdefault("context", step.payload.get("context", "") + (
                ("\n" + accumulated) if accumulated else ""))
            try:
                if step.type == "skill":
                    if self.skill_executor is None:
                        raise RuntimeError("skill_executor non disponibile")
                    r = self.skill_executor(
                        skill_id=step.payload.get("skill_id", ""),
                        task=task,
                        context=step.payload.get("context", ""),
                        model_key=model_key,
                    )
                    step.result = r.get("output") if isinstance(r, dict) else str(r)
                    step.ok = r.get("ok", True) if isinstance(r, dict) else True

                elif step.type == "tool":
                    if self.tool_caller is None:
                        raise RuntimeError("tool_caller non disponibile")
                    out = self.tool_caller(step.payload.get("name", ""),
                                           step.payload.get("args", []))
                    step.result = out if isinstance(out, str) else str(out)
                    step.ok = not (isinstance(out, str) and out.startswith("ERROR:"))

                elif step.type == "mcp":
                    if self.mcp_client is None:
                        raise RuntimeError("mcp_client non disponibile")
                    # MCP: chiama il tool sul server (best-effort)
                    srv = self.mcp_client.servers.get(step.payload.get("server", ""))
                    if srv is None:
                        raise RuntimeError(f"server MCP '{step.payload.get('server')}' non trovato")
                    # Uso discover_tools per verificare; esecuzione via _do_call_tool se esiste
                    if hasattr(self.mcp_client, "_do_call_tool"):
                        out = self.mcp_client._do_call_tool(srv, step.payload.get("tool", ""), step.payload.get("args", {}))
                        step.result = str(out)
                        step.ok = True
                    else:
                        step.result = "MCP call non supportato"
                        step.ok = False

                else:
                    raise ValueError(f"tipo passo sconosciuto: {step.type}")

                accumulated = step.result or accumulated

            except Exception as e:
                step.error = str(e)
                step.ok = False
                step.result = f"ERROR: {e}"
                log.warning("[macro] passo %s fallito: %s", step.type, e)
                if self.stop_on_error:
                    result.ok = False
                    result.steps.append(step)
                    break

            result.steps.append(step)
            result.final_output = accumulated

        if any(not s.ok for s in result.steps):
            result.ok = False
        return result


def run_macro(steps: list[dict], task: dict, skill_executor=None,
              tool_caller=None, mcp_client=None,
              model_key: str = "worker_coder",
              stop_on_error: bool = False) -> MacroResult:
    """Shortcut: crea una macro da una lista di dict e la esegue."""
    runner = MacroRunner(skill_executor, tool_caller, mcp_client, stop_on_error)
    for st in steps:
        runner.add(st.get("type", "tool"), **{k: v for k, v in st.items() if k != "type"})
    return runner.run(task, model_key=model_key)
PY
.venv/bin/python -m py_compile CORE/macro.py && echo "COMPILE_OK"