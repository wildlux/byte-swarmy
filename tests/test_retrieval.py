"""Test Fase F — retrieval TF-IDF (CORE/retrieval.py). Zero LLM."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE import retrieval as R  # noqa: E402
from CORE import feedback_corpus as fc  # noqa: E402


class TestRetrieval(unittest.TestCase):
    def test_tokenize(self):
        self.assertEqual(R.tokenize("Hello, World! foo_bar"),
                         ["hello", "world", "foo_bar"])

    def test_retrieve_rileva_simile(self):
        pairs = [
            ("t1", "fix bug in PyQt6 button click handler",
             "def on_click(self): self.hide()"),
            ("t2", "aggiungi logging al modulo auth",
             "import logging\nlogging.info('ok')"),
            ("t3", "PyQt6 window close event handler",
             "def closeEvent(self, e): self.hide()"),
        ]
        r = R.build_from_pairs(pairs)
        res = r.retrieve("PyQt6 button handler", k=2)
        self.assertTrue(res)
        ids = [x[0] for x in res]
        self.assertIn("t1", ids)

    def test_nessun_risultato_per_query_senza_overlap(self):
        pairs = [("t1", "PyQt6 button", "x = 1")]
        r = R.build_from_pairs(pairs)
        res = r.retrieve("database postgres migration", k=3)
        self.assertEqual(res, [])

    def test_empty_index(self):
        r = R.TaskRetriever([])
        r.build()
        self.assertEqual(r.retrieve("anything"), [])

    def test_format_results(self):
        out = R.TaskRetriever([]).format_results(
            [("t1", 0.5, "def f():\n    return 1")])
        self.assertIn("t1", out)
        self.assertIn("def f()", out)

    def test_build_from_queue_db_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = R.build_from_queue_db(db_path=Path(tmp) / "nope.db")
            self.assertEqual(r.tasks, [])

    def test_build_from_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = fc.task_path("task-x", state_dir=tmp)
            p.parent.mkdir(parents=True, exist_ok=True)
            fc.append_triple(fc.Triple(
                task_id="task-x", kind="code", title="fix PyQt6 button",
                description="handler click", refs=("PyQt6",), output="def on_click(): pass",
                verdict="done", first_try=True, attempts=1,
                model="m", reason="", ts=1.0), state_dir=tmp)
            r = R.build_from_corpus(tmp)
            self.assertEqual(len(r.tasks), 1)
            res = r.retrieve("PyQt6 button click", k=1)
            self.assertTrue(res)
            self.assertEqual(res[0][0], "task-x")


if __name__ == "__main__":
    unittest.main()
