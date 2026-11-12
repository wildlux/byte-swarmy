"""
test_memory_compaction.py — Test unit di F1 (compaction intelligente).

Senza LLM: merge, compaction, persistenza.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import CORE.persistent_memory as pm  # noqa: E402


class TestMemoryCompaction(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)
        pm.MEMORY_FILE = self.tmp / "persistent_memory.json"

    def test_record_error_exact_match(self):
        pm.record_error("SyntaxError", "expected 'except' or 'finally'")
        pm.record_error("SyntaxError", "expected 'except' or 'finally'")
        mem = pm.load_memory()
        self.assertEqual(len(mem["common_errors"]), 1)
        self.assertEqual(mem["common_errors"][0]["count"], 2)

    def test_record_error_fuzzy_match(self):
        pm.record_error("NameError", "name 'foo' is not defined in module scope")
        pm.record_error("NameError", "name 'bar' is not defined in module scope")
        mem = pm.load_memory()
        self.assertEqual(len(mem["common_errors"]), 1)
        self.assertEqual(mem["common_errors"][0]["count"], 2)

    def test_record_error_different_types(self):
        pm.record_error("SyntaxError", "expected 'except'")
        pm.record_error("NameError", "name 'x' not defined")
        mem = pm.load_memory()
        self.assertEqual(len(mem["common_errors"]), 2)

    def test_compaction_merges_same_type(self):
        # Crea 25 errori diversi dello stesso tipo
        for i in range(25):
            pm.record_error("TypeError", f"unsupported operand type {i}")
        mem = pm.load_memory()
        # Dopo compaction, dovrebbero essere fusi
        self.assertLessEqual(len(mem["common_errors"]), 20)

    def test_build_context_recurring(self):
        pm.record_error("SyntaxError", "expected 'except'")
        pm.record_error("SyntaxError", "expected 'except'")
        ctx = pm.build_context_for_prompt()
        self.assertIn("ERRORI COMUNI", ctx)


if __name__ == "__main__":
    unittest.main(verbosity=2)
