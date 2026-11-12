"""
test_diagnosis.py — Test unit di D1 (diagnosi intelligente del gate).

Verifica che suggest_fix_for_marker produca suggerimenti mirati.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.skill_executor import (  # noqa: E402
    suggest_fix_for_marker,
    verify_runtime,
)


class TestDiagnosis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)

    def _write(self, code: str) -> Path:
        p = self.tmp / "main.py"
        p.write_text(code, encoding="utf-8")
        return p

    def test_suggest_len(self):
        fix = suggest_fix_for_marker("LEN=3")
        self.assertIn("LEN=", fix)
        self.assertIn("len(coll)", fix)

    def test_suggest_somma(self):
        fix = suggest_fix_for_marker("SOMMA=15")
        self.assertIn("SOMMA=", fix)

    def test_suggest_overflow(self):
        fix = suggest_fix_for_marker("OVERFLOW=ok")
        self.assertIn("OVERFLOW=ok", fix)

    def test_suggest_generico(self):
        fix = suggest_fix_for_marker("FOO=bar")
        self.assertIn("FOO=", fix)
        self.assertIn("Aggiungi", fix)

    def test_verify_runtime_include_suggerimento(self):
        p = self._write('print("hello")\n')
        err, _ = verify_runtime("print('hello')", p,
                                oracle_checks=["SOMMA=15"])
        self.assertIsNotNone(err)
        self.assertIn("Suggerimento", err)
        self.assertIn("SOMMA=", err)

    def test_verify_runtime_no_suggerimento_se_ok(self):
        p = self._write('print("SOMMA=15")\n')
        err, _ = verify_runtime("print('SOMMA=15')", p,
                                oracle_checks=["SOMMA=15"])
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
