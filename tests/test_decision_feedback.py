"""Test Task 1 — Pre-flight check & persistenza (CORE/decision_feedback.py).

DoD: un parametro errato viene salvato su SQLite e NON consuma token LLM
(decision_client mai chiamato nel ramo deterministico).
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from CORE.decision_feedback import (
    DecisionValidator,
    validate_task_parameters,
)


class FakeQueue:
    """Coda minima che registra gli add (niente I/O)."""

    def __init__(self):
        self.added: list = []

    def add(self, task: dict) -> str:
        tid = f"task-{len(self.added) + 1}"
        self.added.append(task)
        return tid


class FakeDecisionClient:
    def __init__(self, verdict: dict = None):
        self.calls: list = []
        self.verdict = verdict if verdict is not None else {"valid": True}

    def __call__(self, prompt: str):
        import json
        self.calls.append(json.dumps({"prompt": prompt}))
        return self.verdict


class DecisionFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-decision-"))
        self.db_path = self.tmp / "decision_feedback.db"
        self.queue = FakeQueue()

    def make_validator(self, client=None) -> DecisionValidator:
        return DecisionValidator(self.queue, decision_client=client,
                                 db_path=self.db_path)

    def count_rows(self) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM decision_feedback").fetchone()[0]

    # --- ramo deterministico: zero LLM -------------------------------------
    def test_invalid_type_inserts_row_and_never_calls_llm(self):
        client = FakeDecisionClient()
        v = self.make_validator(client)
        result = validate_task_parameters(
            "deploy su produzione",
            {"type": "deploy-prod", "title": "deploy",
             "description": "fai il deploy"},
            v,
        )
        self.assertEqual(result["status"], "needs_revision")
        self.assertIn("type non valido", result["reason"])
        self.assertEqual(len(client.calls), 0)          # DoD: zero token LLM
        self.assertEqual(len(self.queue.added), 0)      # non accodato
        self.assertEqual(self.count_rows(), 1)          # salvato su SQLite

    def test_all_formal_gates(self):
        v = self.make_validator()
        cases = [
            ({"title": "", "description": "x"}, "title vuoto"),
            ({"title": "t" * 300, "description": "x"}, "title oltre"),
            ({"title": "t", "description": "  "}, "description vuota"),
            ({"title": "t", "description": "x",
              "context": "c" * 3000}, "context oltre"),
            ({"title": "t", "description": "x",
              "paths": ["/etc/passwd"]}, "path fuori"),
            ({"title": "t", "description": "x",
              "paths": ["../../etc"]}, "path fuori"),
        ]
        for params, expected in cases:
            with self.subTest(params=params.get("title", "")[:12]):
                r = v.validate("prompt", params).as_dict()
                self.assertEqual(r["status"], "needs_revision")
                self.assertIn(expected, r["reason"])
        self.assertEqual(self.count_rows(), len(cases))
        self.assertEqual(len(self.queue.added), 0)

    # --- ramo valido --------------------------------------------------------
    def test_valid_params_queued_without_rows(self):
        v = self.make_validator()
        result = validate_task_parameters(
            "implementa hello in C",
            {"type": "execute", "title": "hello",
             "description": "gcc project/hello.c -o project/hello"},
            v,
        )
        self.assertEqual(result["status"], "queued")
        self.assertTrue(result["task_id"])
        self.assertEqual(len(self.queue.added), 1)
        self.assertEqual(self.count_rows(), 0)          # nessuna reject

    def test_decision_model_disagreement_persists_reason(self):
        client = FakeDecisionClient(verdict={"valid": False,
                                             "reason": "troppo vago"})
        v = self.make_validator(client)
        result = validate_task_parameters("fai le cose", {"title": "Stuff",
                                                          "description": "..."},
                                          v)
        self.assertEqual(result["status"], "needs_revision")
        self.assertEqual(result["reason"], "troppo vago")
        self.assertEqual(len(client.calls), 1)          # qui il LLM e' lecito
        self.assertEqual(self.count_rows(), 1)

    def test_prompt_limit(self):
        client = FakeDecisionClient()
        v = self.make_validator(client)
        validate_task_parameters("x" * 10_000,
                                 {"title": "t", "description": "ok"}, v)
        import json
        sent = json.loads(client.calls[0])["prompt"]
        self.assertLessEqual(len(sent), 500)

    def test_default_without_decision_client(self):
        v = self.make_validator(client=None)
        r = validate_task_parameters("ciao",
                                     {"title": "t", "description": "d"}, v)
        self.assertEqual(r["status"], "queued")


if __name__ == "__main__":
    unittest.main()
