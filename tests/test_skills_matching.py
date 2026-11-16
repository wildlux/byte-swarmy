"""Test Cycle 72 — Regressione matching skill → prompt del Worker.

Run 2 su prismalux (root cause provato in modo deterministico): la
descrizione del task conteneva parole generiche ("file", "store") →
find_skill matchava py-json-store → la ricetta con "Create
project/main.py" e "STORE_FILE = store.json" finiva nel prompt → il
worker 3b seguiva la ricetta sbagliata invece del task.

Fix (dati): keywords generiche rimosse dalle skill pericolose.
Questo test blocca la regressione su casi reali della campagna.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.skills import find_skill  # noqa: E402


class TestNoHijack(unittest.TestCase):
    """Le descrizioni dei task della campagna NON devono matchare skill."""

    def test_task_bare_except_non_matcha_py_json_store(self):
        """Il caso reale run 2: bare except su docker_mcp/server.py."""
        desc = ("Nel file MCPs/docker_mcp/server.py ci sono 2 istruzioni "
                "except: bare. Convertile in except Exception: mantenendo "
                "identico il corpo. DISCIPLINA: PRIMA leggi il file target "
                "con lo strumento di lettura; VIETATO creare file nuovi; "
                "modifica SOLO il file indicato, con i cambi minimi.")
        self.assertIsNone(
            find_skill("Convertire i 2 bare except: in except Exception",
                       desc))

    def test_parola_test_non_hijacka_py_unittest(self):
        """'test' nudo in una descrizione qualunque non deve iniettare
        la ricetta unittest nel prompt."""
        desc = ("Convertire i bare except nel server MCP; dopo la "
                "modifica rileggi per verifica e controlli i test esistenti.")
        sk = find_skill("Refactor server MCP", desc)
        self.assertNotEqual(sk["id"] if sk else None, "py-unittest")

    def test_parola_with_non_hijacka_py_context_manager(self):
        """'with' appare in ogni descrizione inglese: mai match."""
        desc = ("Refactor del file target with minimal changes, "
                "read first then write.")
        sk = find_skill("Refactor MCP server", desc)
        self.assertNotEqual(sk["id"] if sk else None, "py-context-manager")


class TestMatchLegittimi(unittest.TestCase):
    """I match LEGITTIMI devono continuare a funzionare (no regression)."""

    def test_task_json_store_matcha_py_json_store(self):
        sk = find_skill("Salvare i dati in un json",
                        "persistenza su file json, load e save del database "
                        "piccolo in un unico store locale")
        self.assertIsNotNone(sk)
        self.assertEqual(sk["id"], "py-json-store")

    def test_task_unittest_matcha_py_unittest(self):
        sk = find_skill("Scrivere unittest per il modulo",
                        "test unitari con testcase e asserzioni")
        self.assertIsNotNone(sk)
        self.assertEqual(sk["id"], "py-unittest")

    def test_task_cli_script_matcha_py_cli_script(self):
        sk = find_skill("Nuovo script cli",
                        "tool a riga di comando per il terminale, "
                        "console con argparse")
        self.assertIsNotNone(sk)
        self.assertEqual(sk["id"], "py-cli-script")


if __name__ == "__main__":
    unittest.main(verbosity=2)
