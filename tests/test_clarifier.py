"""
test_clarifier.py — Test unit di Fase 9 (domande interattive).

Senza LLM: rilevamento ambiguità, parsing risposte, chiarimento, loop.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.clarifier import (  # noqa: E402
    ClarificationResult,
    Question,
    clarify,
    clarify_loop,
    detect_ambiguity,
    format_questions,
    is_clear,
    parse_answer,
)


class TestDetectAmbiguity(unittest.TestCase):
    def test_task_chiaro(self):
        qs = detect_ambiguity("stampa ciao mondo")
        self.assertEqual(qs, [])

    def test_task_ambiguo_architettura(self):
        qs = detect_ambiguity("rifattorizza il modulo auth per usare OAuth2")
        self.assertTrue(len(qs) > 0)
        # Deve avere una domanda su architettura/framework
        texts = [q.text for q in qs]
        self.assertTrue(any("architettura" in t.lower() or "framework" in t.lower()
                            for t in texts))

    def test_task_ambiguo_database(self):
        qs = detect_ambiguity("crea un sistema con persistenza su database")
        self.assertTrue(len(qs) > 0)
        texts = [q.text for q in qs]
        self.assertTrue(any("database" in t.lower() or "storage" in t.lower()
                            for t in texts))

    def test_task_ambiguo_docker(self):
        qs = detect_ambiguity("deploya il servizio su kubernetes")
        self.assertTrue(len(qs) > 0)

    def test_task_ambiguo_auth(self):
        qs = detect_ambiguity("implementa login con oauth2")
        self.assertTrue(len(qs) > 0)

    def test_is_clear(self):
        self.assertTrue(is_clear("stampa ciao mondo"))
        self.assertFalse(is_clear("rifattorizza il modulo auth per usare OAuth2"))

    def test_fail_open(self):
        # Non deve sollevare mai
        qs = detect_ambiguity("")
        self.assertEqual(qs, [])


class TestParseAnswer(unittest.TestCase):
    def test_numeri_semplici(self):
        qs = detect_ambiguity("rifattorizza il modulo auth per usare OAuth2")
        if not qs:
            self.skipTest("no questions")
        ans = parse_answer("1,1", qs)
        self.assertEqual(len(ans), len(qs))
        for v in ans.values():
            self.assertIn(v, [o for q in qs for o in q.options] + ["free", "non specificato"])

    def test_risposta_libera(self):
        qs = [Question(id="Q1", text="Test?", options=["a", "b"])]
        ans = parse_answer("0", qs)
        self.assertEqual(ans["Q1"], "free")

    def test_parsing_vuoto(self):
        qs = [Question(id="Q1", text="Test?", options=["a", "b"])]
        ans = parse_answer("", qs)
        self.assertEqual(ans["Q1"], "non specificato")


class TestClarify(unittest.TestCase):
    def test_chiaro(self):
        r = clarify("stampa ciao mondo")
        self.assertTrue(r.is_clear)
        self.assertEqual(r.questions, [])
        self.assertEqual(r.enriched_title, "stampa ciao mondo")

    def test_ambiguo_senza_risposte(self):
        r = clarify("rifattorizza il modulo auth per usare OAuth2")
        self.assertFalse(r.is_clear)
        self.assertTrue(len(r.questions) > 0)

    def test_ambiguo_con_risposte(self):
        r0 = clarify("rifattorizza il modulo auth per usare OAuth2")
        if not r0.questions:
            self.skipTest("no questions")
        answers = {q.id: "1" for q in r0.questions}
        r = clarify("rifattorizza il modulo auth per usare OAuth2", answers=answers)
        self.assertTrue(r.is_clear)
        self.assertIn("Chiarimenti dell'utente", r.enriched_description)


class TestClarifyLoop(unittest.TestCase):
    def test_loop_chiaro(self):
        r = clarify_loop("stampa ciao mondo")
        self.assertTrue(r.is_clear)

    def test_loop_con_risposte(self):
        # Simula un utente che risponde "1" a tutte le domande
        def ask_fn(text):
            return "1,1,1,1,1,1,1,1"
        r = clarify_loop("rifattorizza il modulo auth per usare OAuth2",
                         ask_fn=ask_fn)
        self.assertTrue(r.is_clear)
        self.assertIn("Chiarimenti dell'utente", r.enriched_description)

    def test_loop_interrotto(self):
        def ask_fn(text):
            raise EOFError()
        r = clarify_loop("rifattorizza il modulo auth per usare OAuth2",
                         ask_fn=ask_fn)
        # Procede senza chiarimento
        self.assertFalse(r.is_clear) or True  # fail-open: non crasha

    def test_loop_max_rounds(self):
        # L'utente risponde sempre "0" (libero) → mai chiarito → max_rounds
        def ask_fn(text):
            return "0,0,0,0,0,0,0,0"
        r = clarify_loop("rifattorizza il modulo auth per usare OAuth2",
                         ask_fn=ask_fn)
        # Dopo max_rounds, procede comunque
        self.assertTrue(r.is_clear or r.enriched_description != "")


class TestFormatQuestions(unittest.TestCase):
    def test_format_empty(self):
        self.assertEqual(format_questions([]), "")

    def test_format_with_questions(self):
        qs = [Question(id="Q1", text="Test?", options=["a", "b"])]
        text = format_questions(qs)
        self.assertIn("Q1", text)
        self.assertIn("1) a", text)
        self.assertIn("2) b", text)
        self.assertIn("0) Altro", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
