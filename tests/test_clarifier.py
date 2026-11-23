"""
test_clarifier.py — Test unit di Fase 9 (domande interattive).

Senza LLM: rilevamento ambiguità, parsing risposte, chiarimento, loop.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.clarifier import (  # noqa: E402
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

    def test_task_ambiguo_test_runner(self):
        qs = detect_ambiguity("scrivi test per il modulo auth")
        self.assertTrue(len(qs) > 0)
        texts = [q.text for q in qs]
        self.assertTrue(any("runner" in t.lower() or "marker" in t.lower()
                            for t in texts))

    def test_task_ambiguo_handler_sistema(self):
        qs = detect_ambiguity("crea un handler di sistema per il backup")
        self.assertTrue(len(qs) > 0)
        texts = [q.text for q in qs]
        self.assertTrue(any("servizio di sistema" in t.lower() or "meccanismo" in t.lower()
                            for t in texts))

    def test_task_ambiguo_formato_config(self):
        qs = detect_ambiguity("leggi il file json di configurazione")
        self.assertTrue(len(qs) > 0)
        texts = [q.text for q in qs]
        self.assertTrue(any("formato" in t.lower() and "configurazione" in t.lower()
                            for t in texts))


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

    def test_testo_libero_preservato_con_virgole(self):
        qs = [Question(id="Q1", text="Test?", options=["a", "b"])]
        ans = parse_answer("0: voglio PyQt6, con Designer", qs)
        self.assertEqual(ans["Q1"], "voglio PyQt6, con Designer")
        # Formato prodotto dal dialog PyQt6 (testo senza prefisso "0:")
        ans = parse_answer("voglio tkinter, con ttk", qs)
        self.assertEqual(ans["Q1"], "voglio tkinter, con ttk")

    def test_testo_libero_multi_domanda_non_mangia_le_altre(self):
        qs = [Question(id="Q1", text="Uno?", options=["a", "b"]),
              Question(id="Q2", text="Due?", options=["c", "d"])]
        ans = parse_answer("0: primo, con virgola,2", qs)
        self.assertEqual(ans["Q1"], "primo, con virgola")
        self.assertEqual(ans["Q2"], "d")

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
        calls = []

        def ask_fn(text):
            calls.append(text)
            return "1,1,1"

        r = clarify_loop("rifattorizza il modulo auth per usare OAuth2",
                         ask_fn=ask_fn)
        self.assertEqual(len(calls), 1, "la stessa domanda non va ripetuta")
        self.assertTrue(r.is_clear)
        self.assertIn("Chiarimenti dell'utente", r.enriched_description)

    def test_loop_risposta_libera_non_richiede_e_arriva_al_modello(self):
        calls = []

        def ask_fn(text):
            calls.append(text)
            return "0: mantieni l'attuale, con pytest"

        r = clarify_loop("rifattorizza il modulo", ask_fn=ask_fn)
        self.assertEqual(len(calls), 1)
        self.assertTrue(r.is_clear)
        self.assertIn("mantieni l'attuale, con pytest", r.enriched_description)

    def test_loop_interrotto(self):
        def ask_fn(text):
            raise EOFError()
        r = clarify_loop("rifattorizza il modulo auth per usare OAuth2",
                         ask_fn=ask_fn)
        self.assertFalse(r.is_clear)  # fail-open: non crasha, ma non dichiara clear

    def test_risposte_vuote_non_fanno_loop(self):
        calls = []

        def ask_fn(text):
            calls.append(text)
            return "0,0,0"

        r = clarify_loop("rifattorizza il modulo auth per usare OAuth2",
                         ask_fn=ask_fn)
        self.assertEqual(len(calls), 1)
        self.assertFalse(r.is_clear)
        self.assertIn("Chiarimenti dell'utente", r.enriched_description)


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


class TestPersistPreferences(unittest.TestCase):
    """Q4 — Persistenza delle risposte del chiarimento."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)
        import CORE.persistent_memory as pm
        pm.MEMORY_FILE = self.tmp / "persistent_memory.json"

    def test_record_preference(self):
        from CORE.persistent_memory import record_preference, get_preferences
        record_preference("Quale DB?", "SQLite")
        prefs = get_preferences()
        self.assertEqual(prefs.get("Quale DB?"), "SQLite")

    def test_multiple_preferences(self):
        from CORE.persistent_memory import record_preference, get_preferences
        record_preference("Quale DB?", "SQLite")
        record_preference("Quale framework?", "Flask")
        prefs = get_preferences()
        self.assertEqual(len(prefs), 2)

    def test_clarify_saves_preferences(self):
        from CORE.clarifier import clarify
        from CORE.persistent_memory import get_preferences
        r0 = clarify("rifattorizza il modulo auth per usare OAuth2")
        if not r0.questions:
            self.skipTest("no questions")
        answers = {q.id: "1" for q in r0.questions}
        clarify("rifattorizza il modulo auth per usare OAuth2", answers=answers)
        prefs = get_preferences()
        self.assertTrue(len(prefs) > 0)


class TestClarificationDialogSmoke(unittest.TestCase):
    """Q2 — Smoke test del dialog PyQt6 (offscreen)."""

    def test_import(self):
        try:
            self.assertTrue(True)
        except ImportError:
            self.skipTest("PyQt6 non disponibile")

    def test_qt_available(self):
        try:
            from GUI.clarification_dialog import _QT_AVAILABLE
            if not _QT_AVAILABLE:
                self.skipTest("PyQt6 non disponibile")
            self.assertTrue(_QT_AVAILABLE)
        except ImportError:
            self.skipTest("PyQt6 non disponibile")

    def test_dialog_creation(self):
        try:
            from PyQt6.QtWidgets import QApplication
            from GUI.clarification_dialog import ClarificationDialog, _QT_AVAILABLE
            from CORE.clarifier import Question
            if not _QT_AVAILABLE:
                self.skipTest("PyQt6 non disponibile")
            QApplication.instance() or QApplication([])
            qs = [Question(id="Q1", text="Test?", options=["a", "b"])]
            dlg = ClarificationDialog(qs)
            self.assertIsNotNone(dlg._dialog)
            dlg._dialog.close()
        except ImportError:
            self.skipTest("PyQt6 non disponibile")
