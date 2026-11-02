# -*- coding: utf-8 -*-
"""
scheduler_worker.py — scheduler dei task della GUI (T2.3).

Ogni `interval` secondi legge `CONFIG/scheduled_tasks.json` (scritto dal
pannello "Code Task Scheduler" della GUI) e inietta i task scaduti in
`tasks/queue.db` (via `TaskQueue.add`).

Tipologie (schema del pannello):
    {"title": str, "prompt": str, "type": "oneshot", "datetime": "YYYY-MM-DD HH:MM"}
    {"title": str, "prompt": str, "type": "interval", "interval_sec": N}
    {"title": str, "prompt": str, "type": "daily",    "time": "HH:MM"}

Il tool aggiunge questi campi nel JSON:
    "last_run": <epoch seconds>     (interval/daily — e oneshot, informativo)
    "last_run_date": "YYYY-MM-DD"   (daily: evita doppio scatto nello stesso giorno)
    "done": true                    (oneshot consumato: non re-iniettato)

Architettura: la logica di matching è `SchedulerLogic` (pura, senza I/O —
testabile con tempo fake); il thread `SchedulerWorker` fa solo I/O e
costruzione task. Stop cooperativo via `Event.wait()`: niente `time.sleep`.

Vincoli del progetto: loop single-thread, mai asyncio; SQL parametrizzato
(l'iniezione passa per `TaskQueue.add`).
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import time
from typing import Callable, Optional

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULED_FILE = os.path.join(_BASE, "CONFIG", "scheduled_tasks.json")

DEFAULT_INTERVAL = 60  # secondi tra i tick


class SchedulerLogic:
    """Logica di matching pura (nessun I/O, nessun thread).

    `now_fn` iniettabile per test deterministici (tempo fake).
    """

    def __init__(self, now_fn: Optional[Callable[[], float]] = None):
        self.now_fn = now_fn or time.time

    # -- parsing -------------------------------------------------
    @staticmethod
    def _parse_oneshot(value: str) -> Optional[float]:
        """'YYYY-MM-DD HH:MM' → epoch seconds (orario locale)."""
        try:
            return datetime.datetime.strptime(
                str(value).strip(), "%Y-%m-%d %H:%M").timestamp()
        except (ValueError, AttributeError, TypeError):
            return None

    @staticmethod
    def _parse_daily(value: str) -> tuple[Optional[int], Optional[int]]:
        """'HH:MM' → (ore, minuti) o (None, None)."""
        try:
            parts = str(value).strip().split(":")
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
        except (ValueError, IndexError, TypeError):
            pass
        return None, None

    # -- matching ------------------------------------------------
    def is_due(self, task: dict, now: Optional[float] = None) -> bool:
        """True se il task dinamici DEVE essere iniettato adesso."""
        t = (task or {}).get("type", "")
        if now is None:
            now = self.now_fn()

        if t == "oneshot":
            if task.get("done"):
                return False
            ts = self._parse_oneshot(task.get("datetime", ""))
            return ts is not None and now >= ts

        if t == "interval":
            try:
                interval = float(task.get("interval_sec", 0))
            except (TypeError, ValueError):
                return False
            if interval <= 0:
                return False
            last_run = float(task.get("last_run", 0) or 0)
            return (now - last_run) >= interval

        if t == "daily":
            h, m = self._parse_daily(task.get("time", ""))
            if h is None:
                return False
            local = datetime.datetime.fromtimestamp(now)
            today = local.date().isoformat()
            if task.get("last_run_date") == today:
                return False                     # già girato oggi
            # entro la finestra: HH:MM <= adesso < HH:MM:01 dello stesso
            # giorno (tick cada 60s → basta "oggi non ancora eseguito"
            # e che sia passato l'orario)
            minute_now = local.hour * 60 + local.minute
            return minute_now >= h * 60 + m

        return False

    # -- post-esecuzione ----------------------------------------
    def mark_run(self, task: dict, now: Optional[float] = None) -> None:
        """Nota sul task FATTO: last_run (+ data per daily) + done oneshot."""
        if now is None:
            now = self.now_fn()
        task["last_run"] = now
        if task.get("type", "") == "daily":
            task["last_run_date"] = datetime.datetime.fromtimestamp(
                now).date().isoformat()
        if task.get("type", "") == "oneshot":
            task["done"] = True

    # -- costruzione del task coda --------------------------------
    @staticmethod
    def build_queue_task(task: dict) -> dict:
        """Task schedulato → candidato per `TaskQueue.add`."""
        return {
            "title": str(task.get("title", "scheduled")),
            "description": str(task.get("prompt", "")),
            "type": "code",
            "source": "scheduler",
        }


class SchedulerWorker(threading.Thread):
    """Thread background dell'orchestratore: tick periodico non bloccante."""

    def __init__(self, queue, file_path: str = SCHEDULED_FILE,
                 interval: int = DEFAULT_INTERVAL, logger=None):
        super().__init__(daemon=True, name="scheduler")
        self.queue = queue
        self.file_path = file_path
        self.interval = max(5, int(interval))
        self.log = logger
        self.logic = SchedulerLogic()
        self._stop_event = threading.Event()
        self.injected = 0
        self.last_tick: float = 0.0

    # -- I/O JSON -------------------------------------------------
    def _load(self) -> list:
        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
            tasks = data.get("tasks", [])
            return tasks if isinstance(tasks, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, tasks: list) -> None:
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({"tasks": tasks}, f, indent=2,
                          ensure_ascii=False)
        except OSError as e:
            if self.log:
                self.log.warning(f"[scheduler] save failed: {e}")

    # -- ciclo -----------------------------------------------------
    def tick_once(self) -> int:
        """Un tick sincrono (es. GUI/test): inietta i task dinamici
        scaduti e aggiorna il JSON. Ritorna il numero di task iniettati."""
        tasks = self._load()
        if not tasks:
            return 0
        now = time.time()
        injected = 0
        mutated = False
        for task in tasks:
            if not self.logic.is_due(task, now):
                continue
            queue_task = self.logic.build_queue_task(task)
            try:
                self.queue.add(queue_task)
                injected += 1
                self.logic.mark_run(task, now)
                mutated = True
                if self.log:
                    self.log.info(
                        "[scheduler] injected task %r (type=%s)",
                        queue_task["title"], task.get("type"))
            except Exception as e:
                if self.log:
                    self.log.warning(
                        "[scheduler] inject failed per %r: %s",
                        task.get("title"), e)
        if mutated:
            self._save(tasks)
        self.last_tick = now
        self.injected += injected
        return injected

    def run(self) -> None:
        if self.log:
            self.log.info("[scheduler] thread partito (tick %ss)",
                          self.interval)
        while not self._stop_event.wait(self.interval):
            try:
                self.tick_once()
            except Exception as e:
                if self.log:
                    self.log.warning(f"[scheduler] tick error: {e}")
        if self.log:
            self.log.info("[scheduler] fermo; %d task iniettati totale",
                          self.injected)

    def stop(self) -> None:
        """Stop cooperativo: sveglia il wait e termina entro un tick."""
        self._stop_event.set()
