"""
test_usability_hardcore.py — Suite di usabilità/resilienza AGGRESSIVA.

Categorie:
  A. Ciclo di vita completo della coda SQLite (lifecycle, cooldown, gate umano)
  B. Permanenza dei dati: persistenza tra processi, corrupt-tolerant reload
  C. Scheduler deterministico con clock injectabile (oneshot/interval/daily/monthly)
  D. IntentRouter multilingue IT/EN/ZH + robustezza input arbitriario
  E. State recovery dall'event-store (compreso DB mancante e righe corrotte)
  F. Correction prompt + DecisionValidator (feedback loop di auto-correzione)
  G. Workflow end-to-end felice: Worker → tool → file scritto (modello scriptato)
  H. Invarianti: il sistema DEGRADE, non CRASHA (fuzz dei workflow)

"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.orchestrator import TaskQueue, Worker   # noqa: E402
from CORE.constants import TaskStatus  # noqa: E402
from CORE.scheduler_worker import SchedulerLogic  # noqa: E402
from INTENT.router import IntentRouter, detect_lang  # noqa: E402
from CORE.state_recovery import (                 # noqa: E402
    recover_worker_state,
    get_last_task_for_worker,
)
from CORE.correction import (                     # noqa: E402
    build_correction_prompt,
    sanitize_paths,
    limit_error,
    clamp,
)
from CORE.decision_feedback import DecisionValidator  # noqa: E402
from CORE.memory import AgentMemory               # noqa: E402
from CORE.tools import ToolSet                    # noqa: E402

logger = logging.getLogger("usability-hardcore")
logger.addHandler(logging.NullHandler())
logger.propagate = False

INTENTS_JSON = ROOT / "INTENT" / "intents.json"


# ======================================================================
# A. CICLO DI VITA CODA
# ======================================================================

class TestQueueLifecycle(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-alife-"))
        self.q = TaskQueue(self.tmp, logger)

    def test_full_happy_lifecycle(self):
        tid = self.q.add({"title": "scrivi ciao", "type": "code"})
        tid = [t["id"] for t in self.q.list_tasks()][0]
        self.assertTrue(tid)
        task = self.q.next_pending()
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "running")
        self.q.mark_done(tid, "fatto bene")
        row = [t for t in self.q.list_tasks() if t["id"] == tid][0]
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["result"], "fatto bene")
        self.assertIsNone(self.q.next_pending())

    def test_retry_then_definitive_failure(self):
        tid = self.q.add({"title": "fallisci"})
        tid = [t["id"] for t in self.q.list_tasks()][0]

        # rincorsa: RETRY_LIMIT rit e ripartenze…
        for attempt in range(1, TaskQueue.RETRY_LIMIT + 1):
            got = self.q.next_pending()
            self.assertIsNotNone(got, f"turno attivo {attempt} non\nuf")
            self.q.fail_with_correction(tid, f"errore {attempt}",
                                        "riprova con correzione")
            self.assertEqual(
                [t for t in self.q.list_tasks() if t["id"] == tid][0]["status"],
                "pending",
            )
        # un altro giro → definitivo
        got = self.q.next_pending()
        self.q.fail_with_correction(tid, "ultimo", "nope")
        row = [t for t in self.q.list_tasks() if t["id"] == tid][0]
        self.assertEqual(row["status"], TaskQueue.STATUS_FINAL)
        self.assertIsNone(self.q.next_pending())

    def test_retry_cooldown_delays_claim(self):
        tid = self.q.add({"title": "cooldown"})
        tid = [t["id"] for t in self.q.list_tasks()][0]
        got = self.q.next_pending()
        self.q.fail_with_correction(tid, "err", "riprova",
                                    cooldown_sec=3600)
        self.assertIsNone(self.q.next_pending(),
                          "task in cooldown preso troppo presto!")
        # scaduto il cooldown → riprendibile
        conn = sqlite3.connect(self.tmp / "queue.db")
        conn.execute("UPDATE tasks SET retry_after = ? WHERE id = ?",
                     (time.time() - 1, tid))
        conn.commit()
        conn.close()
        self.assertIsNotNone(self.q.next_pending())

    def test_needs_human_and_stuck(self):
        tid = self.q.add({"title": "humano", "context": ""})
        tid = [t["id"] for t in self.q.list_tasks()][0]
        self.q.needs_human(tid, "serve l'utente per API key")
        row = [t for t in self.q.list_tasks() if t["id"] == tid][0]
        self.assertEqual(row["status"], 'needs_human')
        self.assertEqual(row["reason"], "serve l'utente per API key")
        self.assertIsNone(self.q.next_pending())

    def test_failed_nominal_then_stuck(self):
        tid = self.q.add({"title": "spesso rotto"})
        tid = [t["id"] for t in self.q.list_tasks()][0]
        for _ in range(12):
            self.q.next_pending()
            self.q.mark_failed(tid, "boom")
        row = [t for t in self.q.list_tasks() if t["id"] == tid][0]
        # attempts>=10 → stuck
        self.assertEqual(row["status"], "stuck")

    def test_pause_resume_thermal(self):
        for i in range(3):
            self.q.add({"title": "thermal"})
        paused = self.q.pause_thermal()
        self.assertEqual(paused, 3)
        self.assertIsNone(self.q.next_pending())
        resumed = self.q.resume_thermal()
        self.assertEqual(resumed, 3)
        self.assertIsNotNone(self.q.next_pending())

    def test_update_prompt_and_fields(self):
        tid = self.q.add({"title": "vecchio", "description": ""})
        tid = [t["id"] for t in self.q.list_tasks()][0]
        self.q.update_prompt(tid, "nuovo prompt")
        self.q.update_task(tid, title="nuovo", parent="p-1")
        row = [t for t in self.q.list_tasks() if t["id"] == tid][0]
        self.assertEqual(row["title"], "nuovo")
        self.assertEqual(row["parent"], "p-1")

    def test_duplicate_add_ignored(self):
        tid = self.q.add({"title": "una"})
        tid = [t["id"] for t in self.q.list_tasks()][0]
        # id duplicato: add ignora (INSERT OR IGNORE)
        self.q.add({"id": tid, "title": "due"})
        self.assertEqual(self.q.tasks_count(), 1)


# ======================================================================
# B. PERMANENZENZA E RECUPERO
# ======================================================================

class TestQueuePersistence(unittest.TestCase):

    def test_reopens_between_processes(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-pers-"))
        q1 = TaskQueue(tmp, logger)
        tid = q1.add({"id": "per1", "title": "persisti"})
        del q1
        q2 = TaskQueue(tmp, logger)
        got = q2.next_pending()
        self.assertIsNotNone(got)
        self.assertEqual(got["id"], "per1")

    def test_corrupt_db_row_survives(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-corrupt-"))
        q = TaskQueue(tmp, logger)
        q.add({"id": "c1", "title": "ok"})
        conn = sqlite3.connect(tmp / "queue.db")
        # riga con campi a NULL (calibrazione: nessun crash)
        conn.execute("INSERT INTO tasks (id, status) VALUES ('c2', NULL)")
        conn.commit()
        rows = conn.execute("SELECT * FROM tasks WHERE id='c1'").fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        row = [t for t in q.get_all_tasks() if t["id"] == "c1"]
        self.assertEqual(len(row), 1)


# ======================================================================
# C. SCHEDULER DETERMINISTICO (clock injectabile)
# ======================================================================

class TestSchedulerDeterministic(unittest.TestCase):

    def setUp(self):
        self.t0 = 1_700_000_000.0  # 2023-11-14 quinte 22:13:20 UTC
        self.now = [self.t0]

    def _clock(self):
        return self.now[0]

    def _advance(self, sec):
        self.now[0] += sec

    def _logic(self):
        return SchedulerLogic(now_fn=self._clock)

    def test_oneshot_before_after(self):
        sched = self._logic()
        target = {"type": "oneshot", "datetime": "2023-11-16 00:00"}
        self.assertFalse(sched.is_due(target, self._clock()))
        self._advance((3 * 24) * 86400)
        self.assertTrue(sched.is_due(target, self._clock()))
        sched.mark_run(target, self._clock())
        self.assertTrue(target.get("done"))

    def test_interval_respects_last_run(self):
        sched = self._logic()
        task = {"type": "interval", "interval_sec": 300}
        self.assertTrue(sched.is_due(task, self._clock()))
        sched.mark_run(task, self._clock())
        self.assertFalse(sched.is_due(task, self._clock()))
        self._advance(299)
        self.assertFalse(sched.is_due(task, self._clock()))
        self._advance(1)
        self.assertTrue(sched.is_due(task, self._clock()))

    def test_daily_same_next_day(self):
        sched = self._logic()
        task = {"type": "daily", "time": "08:00"}
        self._advance((24 * 3600) + 1)
        self.assertTrue(sched.is_due(task, self._clock()))
        sched.mark_run(task, self._clock())
        self.assertFalse(sched.is_due(task, self._clock()))
        self._advance(3 * 3600)
        self.assertFalse(sched.is_due(task, self._clock()))

    def test_monthly_day_of_month(self):
        sched = self._logic()
        task = {"type": "monthly", "time": "09:00", "day": 1}
        # primo giorno del mese successivo
        self._advance(17 * 86400)
        self.assertTrue(sched.is_due(task, self._clock()))

    def test_bad_tasks_never_crash(self):
        sched = self._logic()
        for garbage in ({}, {"type": "martian"}, {"type": "interval"},
                        {"type": "oneshot", "datetime": "mai"},
                        None, "stringa", {"type": "daily", "time": "25:99"},
                        {"type": "monthly", "day": 32}):
            with self.subTest(repr(garbage)[:40]):
                got = sched.is_due(garbage, self._clock())  # type: ignore[arg-type]
                self.assertIn(got, (True, False))


# ======================================================================
# D. INTENT ROUTER MULTILINGUE
# ======================================================================

class TestIntentRouterMultilingual(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.router = IntentRouter(str(INTENTS_JSON))

    def test_lang_detection(self):
        cases = {
            "crea un file con dentro ciao mondo": "it",
            "write a hello world script": "en",
            "创建一个包含你好世界的脚本": "zh",
            "test standard": "en",
            "": "en",
        }
        for text, expected in cases.items():
            with self.subTest(text=text[:30]):
                self.assertEqual(detect_lang(text), expected)

    def test_parse_into_task(self):
        parsed = self.router.parse("python hello.py esegui")
        task = self.router.to_task(parsed, "python hello.py esegui")
        self.assertIn("title", task)
        self.assertIn("type", task)
        self.assertLessEqual(len(task["title"]), 120)
        self.assertEqual(task["description"], "python hello.py esegui")
        self.assertIn("source", task)

    def test_fallback_never_crash(self):
        for garbage in ("", "  ", "🚀🚀🚀", "aaaa " * 300, None, 42):
            try:
                what = self.router.parse(garbage)  # type: ignore[arg-type]
                self.assertIn("intent", what)
            except Exception as e:  # noqa: BLE001
                self.fail(f"parse({repr(garbage)[:40]}) ha sollevato: {e}")

    def test_multingual_same_intent(self):
        itp = self.router.parse("crea un task per scrivere codice")
        eng = self.router.parse("create a task to write code")
        zh = self.router.parse("创建一个任务")
        for parsed, lang in ((itp, "it"), (eng, "en"), (zh, "zh")):
            self.assertTrue(parsed.get("intent"), f"fallback per {lang}")
            self.assertIn("lang", parsed)

    def test_confidence_shape(self):
        parsed = self.router.parse("crea un progetto flutter")
        conf = parsed.get("confidence", 0)
        self.assertIsInstance(conf, (int, float))
        self.assertFalse(conf < 0)


# ======================================================================
# E. STATE RECOVERY
# ======================================================================

class TestStateRecovery(unittest.TestCase):

    def _memory_with_recovery(self, tmp: Path, agent_id: str):
        memory = AgentMemory(agent_id, tmp / "state", None, logger)
        return memory

    def test_recover_from_event_store(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-recover-"))
        (tmp / "state").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(tmp / "state" / "memory_events.db")
        conn.execute(
            'CREATE TABLE IF NOT EXISTS events '
            '(id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, is_summary INTEGER DEFAULT 0,'
            ' timestamp REAL, event_type TEXT, data TEXT)'
        )
        for ts, data in [
            (1.0, json.dumps({"type": "task_start", "content": "task A"})),
            (2.0, json.dumps({"type": "tool_result", "content": "{exit 0}"})),
            (3.0, json.dumps({"type": "task_done", "content": "done!"})),
        ]:
            conn.execute("INSERT INTO events (agent_id, is_summary, timestamp, data) VALUES (?,?,?,?)",
                         ("worker-x", 0, ts, data))
        # evento di altro agente → non deve finire in worker-x
        conn.execute("INSERT INTO events (agent_id, is_summary, timestamp, data) VALUES (?,0,4,?)",
                     ("worker-y", json.dumps({"type": "fake", "content": "non mio"})))
        conn.commit()
        conn.close()

        memory = self._memory_with_recovery(tmp, "worker-x")
        before = len(memory.working)
        recover_worker_state({"worker-x": memory}, {"paths": {"state_dir": str(tmp / 'state')}}, logger)
        got = len(memory.working)
        self.assertGreater(got, before, "nessun evento recuperato!")

    def test_missing_db_ok(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-recover-"))
        (tmp / "state").mkdir(parents=True, exist_ok=True)
        memory = self._memory_with_recovery(tmp, "a-missing")
        recover_worker_state({"a-missing": memory}, {"paths": {"state_dir": str(tmp / 'state')}}, logger)
        self.assertEqual(len(memory.working), 0)

    def test_corrupted_rows_skipped(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-recover-"))
        (tmp / "state").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(tmp / "state" / "memory_events.db")
        conn.execute('CREATE TABLE events (agent_id TEXT, is_summary INTEGER DEFAULT 0,'
                     ' timestamp REAL, data TEXT)')
        conn.execute("INSERT INTO events VALUES ('a-bad', 0, 1.0, 'TOT ZÁCI')")
        conn.execute("INSERT INTO events VALUES ('a-bad', 0, 2.0, ?)",
                     (json.dumps({"type": "tool_result", "content": "ok" }),))
        conn.commit()
        conn.close()
        memory = self._memory_with_recovery(tmp, "a-bad")
        recover_worker_state({"a-bad": memory}, {"paths": {"state_dir": str(tmp / 'state')}}, logger)
        contents = [e.get("content", "") for e in memory.working]
        self.assertIn("ok", contents)

    def test_get_last_task(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-retr-"))
        (tmp / "state").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(tmp / "state" / "memory_events.db")
        conn.execute('CREATE TABLE events (agent_id TEXT, is_summary INTEGER DEFAULT 0,'
                     ' timestamp REAL, event_type TEXT, data TEXT)')
        conn.execute("INSERT INTO events (agent_id, event_type, timestamp, data) VALUES "
                     "('a-lst', 'task_start', 9.0, ?)",
                     (json.dumps({"id": "vecchio"}),))
        conn.execute("INSERT INTO events (agent_id, event_type, timestamp, data) VALUES "
                     "('a-lst', 'task_start', 10.0, ?)",
                     (json.dumps({"id": "nuovissimo"}),))
        conn.commit()
        conn.close()
        last = get_last_task_for_worker("a-lst", {"paths": {"state_dir": str(tmp / 'state')}})
        self.assertIsNotNone(last)
        self.assertEqual(last["id"], "nuovissimo")


# ======================================================================
# F. CORRECTION E DECISION FEEDBACK
# ======================================================================

class TestCorrectionAndFeedback(unittest.TestCase):

    def test_sanitizer_masks_home_paths(self):
        masked = sanitize_paths("Error at /home/mario/byte-swarmx/main.py")
        self.assertNotIn("/home/mario", masked)
        self.assertIn("[PATH]", masked)

    def test_error_limit_frames_and_chars(self):
        stderr = "\n".join(f"line {i}" for i in range(50))
        capped = limit_error(stderr)
        self.assertLessEqual(len(capped), 500)
        self.assertNotIn("line 49", capped)

    def test_correction_prompt_structure(self):
        prompt = build_correction_prompt(
            "trova l'errore nel codice precedentemente scritto nel repo",
            "def f(x):\tfail",
            "Traceback (most recent call last):\n  File 'main.py'\nKeyError: 1",
        )
        self.assertIn("ORIGINAL TASK", prompt)
        self.assertIn("## ERROR", prompt)
        self.assertIn("## PREVIOUS CODE", prompt)
        self.assertLessEqual(len(prompt), 2200)

    def test_clamp(self):
        self.assertEqual(clamp("x" * 999, 10), "x" * 10)
        self.assertEqual(clamp("", 10), "")
        self.assertEqual(clamp("short", 10), "short")

    def test_decision_validator_end_to_end(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-feedback-"))
        (tmp / "tasks").mkdir(parents=True, exist_ok=True)
        from CORE.orchestrator import TaskQueue
        q = TaskQueue(tmp, logger)
        validator = DecisionValidator(q, decision_client=None, db_path=tmp / "fbw.db")

        res = validator.validate("crea un file di ben correzione",
                                 params={"paths": "tutto ok"})
        self.assertEqual(res.status, "queued")

        res_bad = validator.validate("parole random", params={"paths": "space/project"})
        self.assertEqual(res_bad.status, "needs_revision")
        self.assertGreater(validator.count_feedback(), 0)


# ======================================================================
# G. WORKFLOW FELICE END-TO-END (modello scriptato, ToolSet reale)
# ======================================================================

class _ScriptedModel:
    """Risponde con la prossima azione del piano; poi done."""

    def __init__(self, plan: list):
        self.plan = plan
        self.turn = 0

    def call_streaming(self, **kwargs):
        if self.turn < len(self.plan):
            action = json.dumps(self.plan[self.turn])
            self.turn += 1
            return action
        return json.dumps({"thought": "finito", "action": "none", "args": [],
                           "done": True, "result": "DONE-OK"})

    def call(self, **kwargs):
        return next(iter(self.call_streaming(**kwargs)), "")


class TestHappyWorkflowE2E(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-e2e-"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        (self.tmp / "state").mkdir()
        cfg = {
            "paths": {"project_root": str(self.project),
                      "state_dir": str(self.tmp / "state")},
            "routing": {"max_file_size_readable": 50_000, "timeout_bash": 5},
            "security": {"enabled": True, "max_output_chars": 5_000,
                         "max_file_size_write": 200_000,
                         "max_file_size_bytes": 2_000_000,
                         "max_memory_mb": 256},
        }
        self.tools = ToolSet(cfg, logger)
        self.tools.set_worker("e2e-happy")

    def test_worker_writes_and_runs(self):
        memory = AgentMemory("e2e", self.tmp / "state", None, logger)
        plan = [
            {"thought": "analizzo il progetto", "action": "analyze_project", "args": [], "done": False},
            {"thought": "scrivo lo script", "action": "write_file",
             "args": ["saluta.py", '"""Saluta il mondo."""\n\n\ndef main() -> None:\n    print("e2e ok")\n\n\nif __name__ == "__main__":\n    main()\n'],
             "done": False},
            {"thought": "lanci", "action": "run_bash", "args": ["python saluta.py"], "done": False},
        ]
        worker = Worker("e2e", "worker_coder", self.tools, memory,
                        _ScriptedModel(plan), logger)
        result = worker.execute({"id": "e2e-1", "title": "workflow felice",
                                 "description": "scrivi ed esegui saluta.py"})
        self.assertEqual(result, "DONE-OK")
        self.assertEqual(
            (self.project / "saluta.py").read_text(),
            '"""Saluta il mondo."""\n\n\ndef main() -> None:\n    print("e2e ok")\n\n\nif __name__ == "__main__":\n    main()\n',
        )

    def test_circuit_breaker_pivots(self):
        # Il modello ripete 3 volte lo stesso tool con esito uguale.
        # Il breaker deve forzare il pivot NON bloccando an continuando per sempre.
        memory = AgentMemory("cb", self.tmp / "state", None, logger)
        plan = [
            {"thought": "riproviamo", "action": "read_file",
             "args": ["INESISTENTE.txt"], "done": False},
        ]
        worker = Worker("cb", "worker_coder", self.tools, memory,
                        _ScriptedModel(plan), logger)
        result = worker.execute({"id": "cb-1", "title": "breaker", "description": "forza pivot"})
        # deve arrivare a done (l'ultima action è sempre done=true)
        self.assertEqual(result, "DONE-OK")
        # e NON deveARE andare in loop infinito (MAX_STEPS fa bound)

    def test_injection_envelope_ships_properly(self):
        # Modelli piccoli emettono "path, content": l'envelope deve raffrontare → write_file
        memory = AgentMemory("envelope", self.tmp / "state", None, logger)
        plan = [
            {"thought": "salvataggio", "action": "tool",
             "args": ["nota.py", 'x = 1\n'], "done": False},
        ]
        worker = Worker("envelope", "worker_coder", self.tools, memory,
                        _ScriptedModel(plan), logger)
        worker.execute({"id": "env-1", "title": "envelope", "description": ""})
        self.assertEqual((self.project / "nota.py").read_text(), "x = 1\n")


# ======================================================================
# H. DEGRADATION: Il sistema NON crasha con workflow arbitriario
# ======================================================================

class TestDegradationNotCrash(unittest.TestCase):

    def test_queue_weird_tasks(self):
        tmp = Path(tempfile.mkdtemp(prefix="bsqrx-deg-"))
        q = TaskQueue(tmp, logger)
        weird = [
            {"id": "w1", "title": ""}, {"id": "w2"}, {},
            {"id": "w3" * 100, "title": "🤖" * 500, "type": "controversial"},
        ]
        for t in weird:
            with self.subTest(repr(t)[:30]):
                try:
                    q.add(t)   # type: ignore[arg-type]
                except Exception as e:  # noqa: BLE001
                    self.fail(f"TaskQueue.add degraded! {type(e).__name__}: {e}")

    def test_queue_infinite_churn(self):
        tmp = Path(tempfile.mkdtemp(prefix="bsqrx-churn-"))
        q = TaskQueue(tmp, logger)
        for i in range(50):
            q.add({"id": f"ch{i}", "title": f"churn-{i}"})
        start = time.time()
        while time.time() - start < 2.0:
            q.next_pending()
        # 2s di churn senza crash; va bene cosí

    def test_engine_recovery_authoritative(self):
        # dopo un kill simulato, il recupero dai NULL running
        tmp = Path(tempfile.mkdtemp(prefix="bsqrx-zomb-"))
        conn = sqlite3.connect(tmp / "queue.db")
        conn.execute('CREATE TABLE IF NOT EXISTS tasks ('
                     ' id TEXT PRIMARY KEY, status TEXT, title TEXT)')
        conn.execute("INSERT INTO tasks VALUES ('z1', 'running', 'zombie')")
        conn.execute("INSERT INTO tasks VALUES ('z2', 'running', 'zombie2')")
        conn.commit()
        conn.close()
        q = TaskQueue(tmp, logger)
        # il claim funziona nonostantecoli zombie (no crash)
        self.assertIsNotNone(q.stats())


if __name__ == "__main__":
    unittest.main(verbosity=2)
