"""Test Fase B (corpus di feedback): Triple + append/load + dedup + stats."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE import feedback_corpus as fc  # noqa: E402


def _triple(task_id="task-1", output="def f():\n    return 1\n",
            verdict="done", first_try=True, attempts=1, refs=(), kind="code"):
    return fc.Triple(
        task_id=task_id, kind=kind, title=task_id, description="d",
        refs=tuple(refs), output=output, verdict=verdict, first_try=first_try,
        attempts=attempts, model="qwen2.5-coder:3b", reason="", ts=1234567890.0)


class TestFeedbackCorpus(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-corpus-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_task_id_sanitize(self):
        self.assertEqual(fc.task_id_safe("task/../../evil"), "task_.._.._evil")
        self.assertTrue(fc.task_id_safe("") .startswith("task"))

    def test_append_load_roundtrip(self):
        p = fc.append_triple(_triple("task-1", output="x = 1\n"), state_dir=self.tmp)
        self.assertTrue(p.exists())
        samples = fc.load_task("task-1", state_dir=self.tmp)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].task_id, "task-1")
        self.assertEqual(samples[0].output, "x = 1\n")
        self.assertEqual(fc.load_task("task-404", state_dir=self.tmp), [])

    def test_load_linea_corrotta_non_crasa(self):
        p = fc.task_path("task-2", state_dir=self.tmp)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json\n", encoding="utf-8")
        self.assertEqual(fc.load_task("task-2", state_dir=self.tmp), [])

    def test_dedup(self):
        a = _triple("task-1", output="same\n")
        b = _triple("task-1", output="same\n")   # ri-esecuzione + stessa risposta
        c = _triple("task-3", output="other\n")
        unique = fc.dedupe([a, b, c])
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0].task_id, "task-1")
        self.assertEqual(unique[1].task_id, "task-3")

    def test_stats(self):
        s = fc.stats([
            _triple("t1", output="a\n"),
            _triple("t1", output="a\n"),   # duplicato: dedup -> 1
            _triple("t3", output="b\n"),
        ])
        self.assertEqual(s["samples"], 3)
        self.assertEqual(s["unique"], 2)
        self.assertEqual(s["done"] + s["corrected"], s["samples"])
        self.assertEqual(s["correction_rate"], 0.0)

    def test_empty_stats(self):
        self.assertEqual(fc.stats([])["unique"], 0)


if __name__ == "__main__":
    unittest.main()
