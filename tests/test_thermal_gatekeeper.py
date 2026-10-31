"""Test Task 3 — Timestral Gatekeeper (throttling termico).

DoD: forzando una temperatura fittizia di 80C il task va in pausa e
riprende automaticamente quando la temperatura torna sotto 65C.
Tutto deterministico: nessun I/O, nessun sleep.
"""
import logging
import tempfile
import unittest
from pathlib import Path

from MONITORING.thermal_manager import TimestralGatekeeper, thermal_should_pause
from CORE.orchestrator import TaskQueue


class PureGateTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertFalse(thermal_should_pause(74.9, 0.0))
        self.assertTrue(thermal_should_pause(75.0, 0.0))
        self.assertFalse(thermal_should_pause(60.0, 79.9))
        self.assertTrue(thermal_should_pause(60.0, 80.0))


class GatekeeperHysteresisTests(unittest.TestCase):
    def test_pause_at_80_resume_at_60(self):
        g = TimestralGatekeeper()
        self.assertFalse(g.check(60.0, 0.0))
        self.assertTrue(g.check(80.0, 0.0))            # pausa CPU
        # resta in pausa finche' la temp non scende SOTTO 65
        self.assertTrue(g.check(70.0, 0.0))
        self.assertTrue(g.check(65.0, 0.0))            # 65 non e' < 65
        self.assertFalse(g.check(60.0, 0.0))           # ripresa
        self.assertFalse(g.check(60.0, 0.0))

    def test_gpu_threshold(self):
        g = TimestralGatekeeper()
        self.assertTrue(g.check(60.0, 81.0))           # pausa GPU
        self.assertFalse(g.check(64.9, 64.9))          # ripresa

    def test_latch_holds_between_thresholds(self):
        g = TimestralGatekeeper()
        self.assertTrue(g.check(76.0, 0.0))
        # tra le soglie: ripresa solo a < 65, non a 65-75
        self.assertTrue(g.check(65.0, 0.0))
        self.assertTrue(g.check(70.0, 0.0))


class QueuePauseResumeTests(unittest.TestCase):
    """Il gate sul loop: task caldo -> thermal_paused, freddo -> pending."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-t3-"))
        self.queue = TaskQueue(self.tmp, logging.getLogger("t"))
        self.pending_ids = []

    def _add(self) -> str:
        tid = self.queue.add({"title": "t", "description": "d",
                              "type": "code"})
        self.pending_ids.append(tid)
        return tid

    def test_pause_marks_and_resume_requeues(self):
        self._add()
        self._add()
        n = self.queue.pause_thermal()
        self.assertEqual(n, 2)
        # in pausa il loop non pesca nulla
        self.assertIsNone(self.queue.next_pending())
        # rientro dichiarato: resume
        n = self.queue.resume_thermal()
        self.assertEqual(n, 2)
        t = self.queue.next_pending()
        self.assertIsNotNone(t)

    def test_done_and_definitive_not_affected(self):
        tid = self._add()
        self.queue.mark_done(tid, "ok")
        self.assertEqual(self.queue.pause_thermal(), 0)
        self.queue.resume_thermal()     # niente da fare
        with self.queue._get_conn() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE id=?",
                               (tid,)).fetchone()
        self.assertEqual(row[0], "done")


if __name__ == "__main__":
    unittest.main()
