"""
test_self_improvement_report.py — C2: report deterministico del loop.
Nessun LLM, nessuna rete: crea uno state finto in tmp e verifica le metriche.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.self_improvement_report import collect, markdown  # noqa: E402


class TestSelfImprovementReport(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "feedback_corpus").mkdir()
        (self.tmp / "skill_proposals").mkdir()

    def _triple(self, task_id, verdict, attempt=1, title="task"):
        return {
            "task_id": task_id, "prompt": f"prompt {task_id}",
            "output": "output", "verdict": verdict, "attempt": attempt,
            "first_try": attempt == 1, "title": title, "description": "",
            "reason": "", "failure_triple": {},
        }

    def _write(self, task_id, triples):
        (self.tmp / "feedback_corpus" / f"{task_id}.jsonl").write_text(
            "".join(json.dumps(t) + "\n" for t in triples), encoding="utf-8")

    def test_corpus_e_verdetti(self):
        self._write("t1", [
            self._triple("t1", "done"),
            self._triple("t1", "corrected", attempt=2),
            self._triple("t1", "failed_definitively", attempt=3),
        ])
        m = collect(self.tmp)
        self.assertEqual(m["corpus"]["samples"], 3)
        self.assertEqual(m["verdicts"], {"done": 1, "corrected": 1,
                                          "failed_definitively": 1})
        self.assertAlmostEqual(m["corpus"]["first_try_rate"], 1 / 3, places=3)
        self.assertEqual(m["retrieval"]["tasks"], 1)
        self.assertEqual(m["retrieval"]["indexed"], 1)
        self.assertEqual(m["retrieval"]["coverage"], 1.0)

    def test_copertura_retrieval_parziale(self):
        self._write("t1", [self._triple("t1", "done", title="con titolo")])
        self._write("t2", [self._triple("t2", "done", title="   ")])
        m = collect(self.tmp)
        self.assertEqual(m["retrieval"]["tasks"], 2)
        self.assertEqual(m["retrieval"]["indexed"], 1)
        self.assertEqual(m["retrieval"]["coverage"], 0.5)

    def test_gate_e_proposte_da_failures(self):
        data = {
            "proposals": {
                "a": {"status": "pending"},
                "b": {"status": "approved"},
                "c": {"status": "rejected"},
                "d": {"status": "pending"},
            },
            "gate_reports": {
                "a": {"ok": False}, "b": {"ok": True}, "c": {"ok": False},
            },
        }
        (self.tmp / "skill_proposals" / "failures.json").write_text(
            json.dumps(data), encoding="utf-8")
        m = collect(self.tmp)
        self.assertEqual(m["skill_proposals"],
                         {"pending": 2, "approved": 1, "rejected": 1})
        self.assertEqual(m["gates"], {"green": 1, "red": 2})

    def test_override_issues_da_file_invalido(self):
        (self.tmp / "auto_skill_keywords.json").write_text(
            json.dumps({"skill_inesistente_xyz": ["x"]}), encoding="utf-8")
        m = collect(self.tmp)
        self.assertGreaterEqual(m["override_issues"], 1)

    def test_fail_open_su_state_vuoto_e_file_rotti(self):
        m = collect(self.tmp)
        self.assertEqual(m["corpus"]["samples"], 0)
        self.assertEqual(m["corpus"]["first_try_rate"], 0.0)
        self.assertEqual(m["retrieval"]["coverage"], 0.0)
        self.assertEqual(m["gates"], {"green": 0, "red": 0})
        (self.tmp / "skill_proposals" / "failures.json").write_text(
            "{rotto", encoding="utf-8")
        self.assertEqual(collect(self.tmp)["gates"], {"green": 0, "red": 0})

    def test_markdown_contiene_tutte_le_sezioni(self):
        self._write("t1", [self._triple("t1", "done")])
        md = markdown(collect(self.tmp))
        self.assertIn("Self-Improvement Report", md)
        for section in ("Corpus di feedback", "Gate e apprendimento",
                        "Copertura retrieval", "Tasso primo colpo",
                        "`done`", "Gate verdi (skill)"):
            with self.subTest(section=section):
                self.assertIn(section, md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
