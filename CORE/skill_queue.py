"""CORE/skill_queue.py — Coda di skill da eseguire in sequenza.

Permette di concatenare più skill procedurali: il risultato di una skill
viene passato come contesto alla successiva. Usato dal Worker quando un
task richiede più passi procedurali (es. scaffold → implementa → testa).

Fail-open: un errore in una skill non blocca la coda (si logga e si passa
alla successiva, salvo `stop_on_error=True`).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger("byte-swarmy.skill_queue")


@dataclass
class SkillStep:
    """Un passo della coda di skill."""
    skill_id: str
    title: str = ""
    context: str = ""          # contesto aggiuntivo per questa skill
    result: Optional[str] = None
    ok: bool = False
    error: Optional[str] = None


@dataclass
class SkillQueueResult:
    """Risultato dell'esecuzione della coda."""
    steps: list[SkillStep] = field(default_factory=list)
    final_output: str = ""
    ok: bool = True

    @property
    def failed(self) -> list[SkillStep]:
        return [s for s in self.steps if not s.ok]


class SkillQueue:
    """Coda di skill da eseguire in sequenza.

    Usage:
        q = SkillQueue(skill_executor, skills_list)
        q.add("py-cli-script", context="crea hello.py")
        q.add("py-test-basic", context="testa hello.py")
        result = q.run(task, model_key="worker_coder")
    """

    def __init__(self, executor: Callable, stop_on_error: bool = False):
        self.executor = executor
        self.stop_on_error = stop_on_error
        self._steps: list[SkillStep] = []

    def add(self, skill_id: str, title: str = "", context: str = "") -> "SkillQueue":
        self._steps.append(SkillStep(skill_id=skill_id, title=title, context=context))
        return self

    def clear(self) -> None:
        self._steps.clear()

    @property
    def steps(self) -> list[SkillStep]:
        return list(self._steps)

    def run(self, task: dict, model_key: str = "worker_coder",
            context_builder: Optional[Callable[[SkillStep, str], str]] = None
            ) -> SkillQueueResult:
        """Esegue le skill in sequenza, passando il risultato precedente."""
        result = SkillQueueResult()
        accumulated = ""
        for step in self._steps:
            step.context = (step.context or "") + ("\n" + accumulated if accumulated else "")
            if context_builder is not None:
                step.context = context_builder(step, accumulated)
            try:
                r = self.executor(
                    skill_id=step.skill_id,
                    task=task,
                    context=step.context,
                    model_key=model_key,
                )
                step.result = r.get("output") if isinstance(r, dict) else str(r)
                step.ok = r.get("ok", True) if isinstance(r, dict) else True
                accumulated = step.result or accumulated
            except Exception as e:
                step.error = str(e)
                step.ok = False
                log.warning("[skill_queue] skill '%s' fallita: %s", step.skill_id, e)
                if self.stop_on_error:
                    result.ok = False
                    result.steps.append(step)
                    break
            result.steps.append(step)
            result.final_output = accumulated

        if any(not s.ok for s in result.steps):
            result.ok = False
        return result


def run_skill_pipeline(skills: list[str], task: dict,
                       executor: Callable, model_key: str = "worker_coder",
                       stop_on_error: bool = False) -> SkillQueueResult:
    """Shortcut: crea una coda, aggiunge le skill e la esegue."""
    q = SkillQueue(executor, stop_on_error=stop_on_error)
    for sid in skills:
        q.add(sid)
    return q.run(task, model_key=model_key)
PY
echo "written"