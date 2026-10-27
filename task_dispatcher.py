"""
task_dispatcher.py — Manages task queue, routing and worker execution.
"""
from typing import Optional
from constants import TaskStatus

class TaskDispatcher:
    def __init__(self, queue, planner, generic_planner, models, tools, logger):
        self.queue = queue
        self.planner = planner
        self.generic_planner = generic_planner
        self.models = models
        self.tools = tools
        self.log = logger
        self.memories = {}

    def dispatch_next(self, task_id: Optional[str] = None):
        """Processes the next available task in the queue."""
        task = self.queue.next_pending()
        if not task:
            return None

        self.log.info(f"dispatching {task['id']}: {task.get('title', '')[:80]}")

        # 1. Generic Task Handling
        if task.get("type") == "generic" or task.get("source", "").startswith("generic"):
            if self.generic_planner.is_enabled():
                subtasks = self.generic_planner.decompose(task)
                if subtasks:
                    for st in subtasks: self.queue.tasks.append(st)
                    self.queue._save()
                    for t in self.queue.tasks:
                        if t["id"] == task["id"]:
                            t["status"] = TaskStatus.PLANNED.value
                            t["subtask_ids"] = [s["id"] for s in subtasks]
                    self.queue._save()
                    return f"Decomposed into {len(subtasks)} tasks"
        
        # 2. Classic Planning
        if self._needs_planning(task):
            subtasks = self.planner.decompose(task)
            if subtasks:
                for st in subtasks: self.queue.tasks.append(st)
                self.queue._save()
                for t in self.queue.tasks:
                    if t["id"] == task["id"]:
                        t["status"] = TaskStatus.PLANNED.value
                        t["subtask_ids"] = [s["id"] for s in subtasks]
                self.//_save()
                return "Planned"

        # 3. Worker Execution
        return self._execute_with_worker(task)

    def _needs_planning(self, task: dict) -> bool:
        if task.get("parent") is not None: return False
        text = (task.get("title", "") + " " + task.get("description", "")).lower()
        # simplified routing for brevity in refactor
        if any(w in text for w in ["complesso", "multi", "sistema"]): return True
        return False

    def _execute_with_worker(self, task: dict):
        # In a real refactor, we'd use the Worker class from orchestrator.py
        # For now, we'll let Orchestrator handle the actual Worker instance to avoid circular imports
        return "DELEGATE_TO_ORCHESTRATOR"

    def _select_worker(self, task: dict) -> str:
        text = (task.get("title", "") + " " + task.get("description", "")).lower()
        return "worker_coder" if "code" in text else "worker_general"
