"""Test Cycle 72 — Runner sessioni di refactoring tramite worker reale.

Copre i pezzi deterministici di tools/swarm_refactor_session.py:
disciplina dentro il task (learning ledger #4), lettura temperatura,
wait_cold senza attesa se già freddo. Nessun LLM: test veloci.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.swarm_refactor_session import (  # noqa: E402
    COLD_THRESHOLD_C, build_task, read_max_temp, wait_cold,
)


class TestBuildTask(unittest.TestCase):
    def test_disciplina_nella_descrizione(self):
        """Learning #4: la descrizione DEVE forzare lettura→scrittura."""
        t = build_task("prx-05", "Titolo", "Converti i bare except.",
                       "MCPs/docker_mcp/server.py")
        self.assertIn("PRIMA leggi il file target", t["description"])
        self.assertIn("VIETATO creare file nuovi", t["description"])
        self.assertEqual(t["file"], "MCPs/docker_mcp/server.py")
        self.assertEqual(t["source"], "debt_ledger")

    def test_disciplina_non_inquina_routing_e_skill(self):
        """Learning run 2: niente nomi di tool/file nella disciplina —
        'read_file' e 'main.py' hanno inquinato routing (heavy model)
        e matching skill (py-json-store)."""
        t = build_task("prx-05", "Titolo", "X", "f.py")
        self.assertNotIn("read_file", t["description"])
        self.assertNotIn("main.py", t["description"])
        self.assertNotIn("store", t["description"])


class TestTemp(unittest.TestCase):
    def test_read_max_temp_restituisce_numero(self):
        t = read_max_temp()
        self.assertIsInstance(t, float)
        self.assertGreaterEqual(t, 0.0)
        self.assertLess(t, 150.0)

    def test_wait_cold_se_gia_freddo_non_attende(self):
        # Soglia irrealisticamente alta: sempre "freddo", zero attesa.
        ok, temp = wait_cold(threshold=150.0, max_wait=1)
        self.assertTrue(ok)
        self.assertGreater(temp, 0.0)

    def test_wait_cold_mai_sopra_soglia_di_default(self):
        """La soglia di default resta sotto il limite 60°C."""
        self.assertLess(COLD_THRESHOLD_C, 60.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
