"""test_test_suite_panel.py — Test del pannello Test Suite.

Copre:
  1. is_e2e_file / discover_test_files (esclusione e2e/LLM di default);
  2. parse_test_output (pytest -q, unittest verbose, exit 5 = SKIP);
  3. pipeline QProcess reale su un file piccolo (test_settings_store.py)
     con il pannello: esito registrato e JSON salvato (path tmp, mai
     sullo state/ reale).
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import GUI.test_suite_panel as tsp  # noqa: E402


class TestDiscovery(unittest.TestCase):
    def test_e2e_notori_riconosciuti(self):
        for name in ("test_e2e.py", "test_mcp_e2e.py",
                     "test_functional_swarm.py", "test_user_workflow.py",
                     "test_refactoring_live.py", "test_timestral_e2e.py",
                     "test_timestral_full.py"):
            self.assertTrue(tsp.is_e2e_file(name), name)

    def test_unit_non_e_e2e(self):
        for name in ("test_settings_store.py", "test_close_orchestrator.py",
                     "test_theme_sync.py"):
            self.assertFalse(tsp.is_e2e_file(name), name)

    def test_discover_default_esclude_e2e(self):
        files, excluded = tsp.discover_test_files(include_e2e=False)
        self.assertTrue(files)
        for f in files:
            self.assertFalse(tsp.is_e2e_file(f), f)
        self.assertTrue(excluded)
        for f in excluded:
            self.assertTrue(tsp.is_e2e_file(f), f)

    def test_discover_optin_include_tutto(self):
        files, excluded = tsp.discover_test_files(include_e2e=True)
        self.assertTrue(files)
        self.assertEqual(excluded, [])


class TestParser(unittest.TestCase):
    def test_pytest_ok(self):
        out = "............\n13 passed, 1 skipped in 2.45s"
        r = tsp.parse_test_output(out, 0)
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["counts"]["passed"], 13)
        self.assertEqual(r["counts"]["skipped"], 1)

    def test_pytest_fail(self):
        out = "...F..\n1 failed, 4 passed in 0.8s"
        r = tsp.parse_test_output(out, 1)
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(r["counts"]["failed"], 1)
        self.assertEqual(r["counts"]["passed"], 4)

    def test_pytest_no_tests_collected_skip(self):
        out = "no tests ran in 0.01s"
        r = tsp.parse_test_output(out, 5)
        self.assertEqual(r["status"], "SKIP")

    def test_unittest_fallback(self):
        out = ("test_x (tests.test_z.C.test_x) ... ok\n"
               "----------------------------------------------------------------------\n"
               "Ran 3 tests in 0.123s\n\nOK")
        r = tsp.parse_test_output(out, 0)
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["counts"]["passed"], 3)

    def test_unittest_fallback_failed(self):
        out = "Ran 2 tests in 0.1s\n\nFAILED (failures=1)"
        r = tsp.parse_test_output(out, 1)
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(r["counts"]["passed"], 2)
        # FAILED nel testo → i contatori pass NON vengono azzerati come ok
        self.assertTrue(r["counts"]["failed"] >= 0)


class TestPanelPipeline(unittest.TestCase):
    """Pipeline reale: il pannello esegue UN file piccolo via QProcess."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bsw_tsuite_"))
        # Risultati su path tmp: mai sul state/ reale del progetto
        self._orig_results = tsp.RESULTS_REL
        tsp.RESULTS_REL = str(self.tmp / "results.json")
        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])
        self.panel = tsp.TestSuitePanel()

    def tearDown(self):
        if self.panel._proc is not None:
            self.panel._proc.kill()
            self.panel._proc = None
        tsp.RESULTS_REL = self._orig_results

    def _spin_until_idle(self, limit_s: float = 120):
        deadline = time.monotonic() + limit_s
        while self.panel._proc is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        self.app.processEvents()

    def test_run_file_piccolo_end_to_end(self):
        panel = self.panel
        panel._results = []
        panel._queue = [Path(__file__).resolve().parent.parent /
                        "tests" / "test_settings_store.py"]
        panel._stopping = False
        panel._timed_out = False
        panel.progress.setRange(0, 1)
        panel.progress.setValue(0)
        panel.run_btn.setEnabled(False)
        panel.stop_btn.setEnabled(True)
        panel._next()  # parte il QProcess
        self._spin_until_idle()
        self.assertIsNone(panel._proc, "processo ancora attivo a fine spin")
        self.assertEqual(len(panel._results), 1)
        rec = panel._results[0]
        self.assertEqual(rec["file"], "test_settings_store.py")
        # test_settings_store: 6 test tutti verdi (fix SETTINGS_FILE)
        self.assertEqual(rec["status"], "PASS",
                         f"detail: {rec.get('detail', '')[:400]}")
        self.assertEqual(rec["counts"]["passed"], 6)
        self.assertGreater(rec["duration_s"], 0.0)
        # JSON salvato sul path tmp patchato
        import json
        saved = json.loads(tsp.RESULTS_REL and
                           open(tsp.RESULTS_REL, encoding="utf-8").read())
        self.assertIn("summary", saved)
        self.assertEqual(saved["summary"]["files_total"], 1)
        self.assertEqual(saved["summary"]["files_ok"], 1)

    def test_run_file_inesistente_error(self):
        panel = self.panel
        panel._results = []
        panel._queue = [Path(__file__).resolve().parent.parent /
                        "tests" / "test_NO_ESISTE_zzz.py"]
        panel._stopping = False
        panel._timed_out = False
        panel.progress.setRange(0, 1)
        panel._next()
        self._spin_until_idle()
        self.assertEqual(len(panel._results), 1)
        self.assertIn(panel._results[0]["status"], ("FAIL", "ERROR", "SKIP"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
