"""CORE/tool_queue.py — Coda di tool da eseguire in sequenza.

Permette di concatenare più tool: l'output di un tool viene passato come
argomento al successivo (pipeline). Usato dal Worker per task multi-step
deterministici (es. read_file → lint_code → run_test_suite).

Fail-open: un errore in un tool non blocca la coda (si logga e si passa
al successivo, salvo `stop_on_error=True`).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger("byte-swarmy.tool_queue")


@dataclass
class ToolStep:
    """Un passo della coda di tool."""
    name: str
    args: list = field(default_factory=list)
    result: Optional[str] = None
    ok: bool = True
    error: Optional[str] = None


@dataclass
class ToolQueueResult:
    """Risultato dell'esecuzione della coda."""
    steps: list[ToolStep] = field(default_factory=list)
    final_output: str = ""
    ok: bool = True

    @property
    def failed(self) -> list[ToolStep]:
        return [s for s in self.steps if not s.ok]


class ToolQueue:
    """Coda di tool da eseguire in sequenza.

    Usage:
        q = ToolQueue(tool_caller)
        q.add("read_file", ["path/to/file.py"])
        q.add("lint_code", ["{{prev}}"])   # {{prev}} = output precedente
        result = q.run()
    """

    def __init__(self, caller: Callable, stop_on_error: bool = False):
        self.caller = caller
        self.stop_on_error = stop_on_error
        self._steps: list[ToolStep] = []

    def add(self, name: str, args: list | None = None) -> "ToolQueue":
        self._steps.append(ToolStep(name=name, args=list(args or [])))
        return self

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> list[ToolStep]:
        return list(self._steps)

    def run(self) -> ToolQueueResult:
        """Esegue i tool in sequenza, sostituendo {{prev}} con l'output precedente."""
        result = ToolQueueResult()
        prev = ""
        for step in self._steps:
            args = [a.replace("{{prev}}", prev) if isinstance(a, str) else a
                    for a in step.args]
            try:
                out = self.caller(step.name, args)
                step.result = out if isinstance(out, str) else str(out)
                step.ok = not (isinstance(out, str) and out.startswith("ERROR:"))
                prev = step.result or prev
            except Exception as e:
                step.error = str(e)
                step.ok = False
                step.result = f"ERROR: {e}"
                log.warning("[tool_queue] tool '%s' fallito: %s", step.name, e)
                if self.stop_on_error:
                    result.ok = False
                    result.steps.append(step)
                    break
            result.steps.append(step)
            result.final_output = prev

        if any(not s.ok for s in result.steps):
            result.ok = False
        return result


def run_tool_pipeline(tools: list[tuple[str, list]], caller: Callable,
                      stop_on_error: bool = False) -> ToolQueueResult:
    """Shortcut: crea una coda, aggiunge i tool e la esegue."""
    q = ToolQueue(caller, stop_on_error=stop_on_error)
    for name, args in tools:
        q.add(name, args)
    return q.run()
PY
.venv/bin/python -m py_compile CORE/skill_queue.py CORE/tool_queue.py && echo "COMPILE_OK"