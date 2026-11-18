"""Test Robustezza #1 — watchdog backoff escalato + guardia crash-loop."""

import io
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import SAFETY.watchdog as wd  # noqa: E402


class TestBackoffPure(unittest.TestCase):
    def test_sequenza_backoff(self):
        self.assertEqual([wd.backoff_for(i) for i in range(1, 9)],
                         [1, 2, 4, 8, 16, 32, 60, 60])

    def test_cap_custom(self):
        self.assertEqual(wd.backoff_for(10, cap=10), 10)

    def test_zero_o_negativo(self):
        self.assertEqual(wd.backoff_for(0), 1)
        self.assertEqual(wd.backoff_for(-3), 1)

    def test_healthy_reset(self):
        self.assertTrue(wd.healthy_reset(60.0))
        self.assertTrue(wd.healthy_reset(99.0))
        self.assertFalse(wd.healthy_reset(30.0))
        self.assertFalse(wd.healthy_reset(0.0))

    def test_costanti(self):
        self.assertEqual(wd.ALERT_AFTER_RESTARTS, 5)
        self.assertEqual(wd.BACKOFF_CAP_SEC, 60)


class TestCrashSimulato(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        self._orig_max = wd._MAX_RESTARTS
        wd._MAX_RESTARTS = 3

    def tearDown(self):
        wd._MAX_RESTARTS = self._orig_max

    def test_backoff_su_crash_consecutivi(self):
        class FakeProc:
            def __init__(self):
                self.stdout = io.StringIO("")
                self.returncode = 1

            def poll(self):
                return None

            def wait(self):
                return 1

            def terminate(self):
                pass

            def kill(self):
                pass

        with mock.patch("SAFETY.watchdog.subprocess.Popen",
                        return_value=FakeProc()), \
                mock.patch("SAFETY.watchdog.time.sleep",
                           side_effect=lambda d: self.sleeps.append(d)), \
                mock.patch("SAFETY.watchdog.sys.exit",
                           side_effect=SystemExit):
            with self.assertRaises(SystemExit):
                wd.run_orchestrator()

        # 3 riavvii → backoff 1, 2, 4 (il 3° esce prima del sleep)
        self.assertEqual(self.sleeps, [1, 2])


if __name__ == "__main__":
    unittest.main()
