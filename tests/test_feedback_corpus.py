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

    # --- A2 (2026-11-22): reason / verdict / attempts su ogni esito --------
    def test_clamp_reason(self):
        self.assertEqual(fc.clamp_reason("  a   b\n c "), "a b c")
        self.assertEqual(len(fc.clamp_reason("x" * 5000)), fc.MAX_REASON_CHARS)
        self.assertEqual(fc.clamp_reason(None), "")

    def test_verdict_set_comprende_fallimenti(self):
        self.assertEqual(fc.VALID_VERDICTS,
                         {"done", "corrected", "failed_definitively"})

    def test_triple_con_reason_e_attempts_per_verdetto(self):
        for verdict, attempts in (("done", 1), ("corrected", 3),
                                  ("failed_definitively", 4)):
            with self.subTest(verdict=verdict):
                t = fc.Triple(task_id=f"t-{verdict}", kind="code", title="t",
                              description="d", refs=("ref.py",), output="out",
                              verdict=verdict, first_try=attempts == 1,
                              attempts=attempts, model="fake:1b",
                              reason=fc.clamp_reason("perché: " + "x" * 4100),
                              ts=123.0)
                fc.append_triple(t, state_dir=self.tmp)
                loaded = fc.load_task(f"t-{verdict}", state_dir=self.tmp)[0]
                self.assertEqual(loaded.verdict, verdict)
                self.assertEqual(loaded.attempts, attempts)
                self.assertEqual(len(loaded.reason), fc.MAX_REASON_CHARS)
                self.assertIn("verdict", loaded.to_dict())
                self.assertIn("reason", loaded.to_dict())

    def test_failure_triple_scrive_failed_definitively(self):
        task = {"id": "boom", "type": "code", "title": "task",
                "description": "d", "context": {"refs": ["a.py"]}}
        p = fc.failure_triple(task, reason="errore", attempts=4,
                              model="fake:1b", correction="CORREZIONE " * 500,
                              state_dir=self.tmp)
        self.assertTrue(p.exists())
        t = fc.load_task("boom", state_dir=self.tmp)[0]
        self.assertEqual(t.verdict, "failed_definitively")
        self.assertEqual(t.attempts, 4)
        self.assertEqual(t.model, "fake:1b")
        self.assertEqual(len(t.reason), fc.MAX_REASON_CHARS)
        self.assertTrue(t.reason.startswith("CORREZIONE"))
        self.assertEqual(t.refs, ("a.py",))

    def test_dedup_invariato_con_verdetti_diversi(self):
        a = _triple("t", output="same", verdict="done")
        b = _triple("t", output="same", verdict="done")
        c = _triple("t", output="same", verdict="corrected")
        self.assertEqual(len(fc.dedupe([a, b])), 1)
        self.assertEqual(len(fc.dedupe([a, c])), 2)  # verdict diverso = chiave diversa

    def test_stats_conta_failed(self):
        s = fc.stats([
            _triple("a", verdict="done"),
            _triple("b", verdict="corrected"),
            _triple("c", verdict="failed_definitively"),
        ])
        self.assertEqual(s["done"], 1)
        self.assertEqual(s["corrected"], 1)
        self.assertEqual(s["correction_rate"], 0.333)


if __name__ == "__main__":
    unittest.main()
