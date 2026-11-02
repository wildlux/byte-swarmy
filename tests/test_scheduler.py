# -*- coding: utf-8 -*-
"""
tests/test_scheduler.py — logica pura dello scheduler (T2.3/T3.6).

Senza thread e senza I/O reale: tempo fake via `now_fn`, coda fake
(oggetto che registra le `add`). Copre:
  - oneshot scaduto / futuro / senza datetime / già done;
  - interval primo run (last_run assente), scaduto, non ancora;
  - daily orario passato, già eseguito oggi, orario futuro;
  - tipologia sconosciuta → mai dinamica;
  - build_queue_task: campi coerenti col TaskQueue;
  - tick_once del worker: iniezione + file aggiornato (tmp dir).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.scheduler_worker import SchedulerLogic, SchedulerWorker  # noqa: E402

# lun 3 nov 2025 10:00:00 locale (fisso, deterministico)
T_NOW = 1762164000.0


class FakeClock:
    def __init__(self, now: float = T_NOW):
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeQueue:
    """TaskQueue minima: registra gli add (no SQLite)."""

    def __init__(self):
        self.added: list[dict] = []

    def add(self, task: dict) -> str:
        self.added.append(task)
        return f"fake-{len(self.added)}"


class TestOneShot(unittest.TestCase):

    def setUp(self):
        self.logic = SchedulerLogic(now_fn=FakeClock(T_NOW))

    def test_past_datetime_is_due(self):
        # 1 ora fa
        t = {"type": "oneshot", "datetime": "2026-11-02 08:00"}
        # uso una datetime relativa al clock fake via target reale:
        # il parser usa l'orario locale → costruiamo l'attorno al now
        import datetime
        past = datetime.datetime.fromtimestamp(T_NOW)
        past = past - datetime.timedelta(hours=1)
        t["datetime"] = past.strftime("%Y-%m-%d %H:%M")
        self.assertTrue(self.logic.is_due(t, T_NOW))

    def test_future_datetime_not_due(self):
        import datetime
        t = {"type": "oneshot",
             "datetime": (datetime.datetime.fromtimestamp(T_NOW)
                          + datetime.timedelta(hours=1)
                          ).strftime("%Y-%m-%d %H:%M")}
        self.assertFalse(self.logic.is_due(t, T_NOW))

    def test_done_never_reinjects(self):
        import datetime
        t = {"type": "oneshot", "done": True,
             "datetime": (datetime.datetime.fromtimestamp(T_NOW)
                          - datetime.timedelta(hours=1)
                          ).strftime("%Y-%m-%d %H:%M")}
        self.assertFalse(self.logic.is_due(t, T_NOW))
        self.logic.mark_run(t, T_NOW)
        self.assertTrue(t["done"])

    def test_missing_or_bad_datetime_not_due(self):
        for bad in ({}, {"type": "oneshot", "datetime": ""},
                    {"type": "oneshot", "datetime": "32-99 99:99"}):
            self.assertFalse(self.logic.is_due(bad, T_NOW))


class TestInterval(unittest.TestCase):

    def setUp(self):
        self.logic = SchedulerLogic(now_fn=FakeClock(T_NOW))

    def test_first_run_without_last_run(self):
        t = {"type": "interval", "interval_sec": 300}
        self.assertTrue(self.logic.is_due(t, T_NOW))

    def test_halfway_not_due(self):
        t = {"type": "interval", "interval_sec": 300,
             "last_run": T_NOW - 100}
        self.assertFalse(self.logic.is_due(t, T_NOW))

    def test_elapsed_is_due(self):
        t = {"type": "interval", "interval_sec": 60,
             "last_run": T_NOW - 61}
        self.assertTrue(self.logic.is_due(t, T_NOW))

    def test_bad_interval_not_due(self):
        for bad in ({"type": "interval", "interval_sec": 0},
                    {"type": "interval", "interval_sec": -5},
                    {"type": "interval", "interval_sec": "x"}):
            self.assertFalse(self.logic.is_due(bad, T_NOW))
        t = {"type": "interval"}
        self.assertFalse(self.logic.is_due(t, T_NOW))


class TestDaily(unittest.TestCase):

    def setUp(self):
        self.logic = SchedulerLogic(now_fn=FakeClock(T_NOW))
        import datetime
        local = datetime.datetime.fromtimestamp(T_NOW)
        h = local.hour
        self.past_hhmm = f"{h - 1:02d}:{local.minute:02d}"
        self.future_hhmm = f"{(h + 1) % 24:02d}:{local.minute:02d}"

    def test_time_passed_today_is_due(self):
        t = {"type": "daily", "time": self.past_hhmm}
        self.assertTrue(self.logic.is_due(t, T_NOW))

    def test_future_time_not_due(self):
        t = {"type": "daily", "time": self.future_hhmm}
        self.assertFalse(self.logic.is_due(t, T_NOW))

    def test_already_done_today_not_due_again(self):
        t = {"type": "daily", "time": self.past_hhmm,
             "last_run_date": "oggi-fake"}
        # simula: last_run_date == oggi reale
        import datetime
        task = dict(t)
        task["last_run_date"] = datetime.datetime.fromtimestamp(
            T_NOW).date().isoformat()
        self.assertFalse(self.logic.is_due(task, T_NOW))

    def test_done_other_day_is_due(self):
        import datetime
        t = {"type": "daily", "time": self.past_hhmm,
             "last_run_date": (datetime.datetime.fromtimestamp(T_NOW)
                               - datetime.timedelta(days=1)
                               ).date().isoformat()}
        self.assertTrue(self.logic.is_due(t, T_NOW))

    def test_bad_time_not_due(self):
        for bad in ("", "25:61", "nope", "12", "12:5x"):
            self.assertFalse(self.logic.is_due({"type": "daily",
                                                "time": bad}, T_NOW))


class TestUnknownTypeAndBuild(unittest.TestCase):

    def setUp(self):
        self.logic = SchedulerLogic(now_fn=FakeClock(T_NOW))

    def test_unknown_type_never_due(self):
        for t in ({"type": "cron"},
                  {},
                  {"type": "oneshot-but-"}):
            self.assertFalse(self.logic.is_due(t, T_NOW))

    def test_mark_run_daily_sets_date(self):
        t = {"type": "daily", "time": "10:00"}
        self.logic.mark_run(t, T_NOW)
        self.assertEqual(t["last_run"], T_NOW)
        self.assertIn("last_run_date", t)

    def test_build_queue_task_fields(self):
        t = {"title": "backup", "prompt": "fai il backup",
             "model": "qwen2.5:1.5b"}
        q = SchedulerLogic.build_queue_task(t)
        self.assertEqual(q["title"], "backup")
        self.assertEqual(q["description"], "fai il backup")
        self.assertEqual(q["type"], "code")
        self.assertEqual(q["source"], "scheduler")


class TestWorkerTickOnce(unittest.TestCase):
    """I/O reale ristretto: file JSON temporaneo + coda fake."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bswarm-sched-")
        self.file = os.path.join(self.tmp, "scheduled_tasks.json")
        self.queue = FakeQueue()

    def _worker(self) -> SchedulerWorker:
        return SchedulerWorker(self.queue, file_path=self.file,
                               interval=60, logger=None)

    def test_empty_file_returns_zero(self):
        w = self._worker()
        self.assertEqual(w.tick_once(), 0)
        self.assertEqual(self.queue.added, [])

    def test_oneshot_injected_and_marked_done(self):
        import datetime
        past = (datetime.datetime.fromtimestamp(T_NOW)
                - datetime.timedelta(hours=1)) \
            .strftime("%Y-%m-%d %H:%M")
        tasks = [{"title": "p", "prompt": "x", "type": "oneshot",
                  "datetime": past}]
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump({"tasks": tasks}, f)
        w = self._worker()
        n = w.tick_once()
        self.assertEqual((n, len(self.queue.added)), (1, 1))
        self.assertEqual(self.queue.added[0]["source"], "scheduler")
        on_disk = json.load(open(self.file))["tasks"][0]
        self.assertTrue(on_disk["done"])
        self.assertIn("last_run", on_disk)

    def test_no_double_inject_on_second_tick(self):
        import datetime
        past = (datetime.datetime.fromtimestamp(T_NOW)
                - datetime.timedelta(hours=1)) \
            .strftime("%Y-%m-%d %H:%M")
        tasks = [{"title": "p", "prompt": "x", "type": "oneshot",
                  "datetime": past}]
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump({"tasks": tasks}, f)
        w = self._worker()
        self.assertEqual(w.tick_once(), 1)
        self.assertEqual(w.tick_once(), 0)

    def test_stop_sets_event(self):
        w = self._worker()
        self.assertFalse(w._stop_event.is_set())
        w.stop()
        self.assertTrue(w._stop_event.is_set())


if __name__ == "__main__":
    print("Scheduler logic test → CORE/scheduler_worker.py")
    print("=" * 60)
    unittest.main(verbosity=2)
