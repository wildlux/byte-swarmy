"""Test metrica "primo colpo %" (P1-1) — TaskQueue.first_try + report.

Copre:
  - default NULL per task mai valutati (deterministici swarm/execute)
  - mark_done(first_try=True/False) scrive 1/0
  - mark_failed / fail_with_correction / mark_pending → first_try=0
  - mark_done senza flag non tocca un valore già impostato
  - build_report conta SOLO i task valutati (done + first_try NOT NULL)
  - format_line e fail-open su DB assente

Zero LLM, DB temporaneo.
"""

import logging
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.task_queue import TaskQueue  # noqa: E402
from tools.first_try_report import build_report, format_line  # noqa: E402

log = logging.getLogger("test.first_try")


class TestQueueFirstTry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue = TaskQueue(Path(self.tmp.name), log)
        self.db = Path(self.tmp.name) / "queue.db"

    def tearDown(self):
        self.tmp.cleanup()

    def _add(self, tid):
        self.queue.add({"id": tid, "title": tid, "description": "",
                        "context": "", "status": "pending"})

    def _first_try(self, tid):
        with sqlite3.connect(str(self.db)) as conn:
            row = conn.execute(
                "SELECT first_try FROM tasks WHERE id = ?", (tid,)).fetchone()
        return row[0] if row else "missing"

    def test_default_null(self):
        self._add("t1")
        self.assertIsNone(self._first_try("t1"))

    def test_mark_done_primo_colpo(self):
        self._add("t1")
        self.queue.mark_done("t1", "ok", first_try=True)
        self.assertEqual(self._first_try("t1"), 1)

    def test_mark_failed_poi_done_non_primo_colpo(self):
        self._add("t1")
        self.queue.mark_failed("t1", "errore")
        self.queue.mark_done("t1", "ok", first_try=False)
        self.assertEqual(self._first_try("t1"), 0)

    def test_fail_with_correction_segna_zero(self):
        self._add("t1")
        self.queue.fail_with_correction("t1", "e", "correggi",
                                        retry_limit=3)
        self.assertEqual(self._first_try("t1"), 0)

    def test_mark_pending_segna_zero(self):
        self._add("t1")
        self.queue.mark_done("t1", "ok", first_try=True)
        self.queue.mark_pending("t1")
        self.assertEqual(self._first_try("t1"), 0)

    def test_mark_done_senza_flag_non_tocca(self):
        self._add("t1")
        self.queue.mark_done("t1", "primo", first_try=True)
        self.assertEqual(self._first_try("t1"), 1)
        # Un secondo mark_done senza flag (es. chiusura parent) non azzera.
        self.queue.mark_done("t1", "secondo")
        self.assertEqual(self._first_try("t1"), 1)


class TestFirstTryReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.queue = TaskQueue(self.root, log)
        self.db = self.root / "queue.db"
        # t1: primo colpo · t2: dopo correction · t3: deterministico (NULL)
        self.queue.add({"id": "t1", "status": "pending"})
        self.queue.mark_done("t1", "ok", first_try=True)
        self.queue.add({"id": "t2", "status": "pending"})
        self.queue.mark_failed("t2", "errore")
        self.queue.mark_done("t2", "ok", first_try=False)
        self.queue.add({"id": "t3", "status": "pending"})
        self.queue.mark_done("t3", "ok")

    def tearDown(self):
        self.tmp.cleanup()

    def test_conta_solo_i_valutati(self):
        report = build_report(self.db)
        self.assertEqual((report["done"], report["first_try"],
                          report["pct"], report["legacy"]),
                         (2, 1, 50.0, False))

    def test_schema_vecchio_legacy(self):
        # DB senza colonna first_try: file leggibile ma schema pre-P1-1.
        legacy = self.root / "legacy.db"
        with sqlite3.connect(str(legacy)) as conn:
            conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, "
                         "status TEXT)")
        report = build_report(legacy)
        self.assertTrue(report["legacy"])
        self.assertIn("non ancora migrato", format_line(report))

    def test_format_line(self):
        line = format_line(build_report(self.db))
        self.assertEqual(line, "primo_colpo: 1/2 (50.0%)")

    def test_db_assente_fail_open(self):
        self.assertIsNone(build_report(self.root / "nope.db"))
        self.assertIn("n/d", format_line(None))


if __name__ == "__main__":
    unittest.main()
