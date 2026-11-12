"""
test_oracle_gate.py — Test unit di A1 (oracle test in verify_runtime).

Verifica che il gate rifiuti codice che produce output sbagliato,
anche quando compila e non ha traceback.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.skill_executor import verify_runtime  # noqa: E402


class TestOracleGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)

    def _write(self, code: str) -> Path:
        p = self.tmp / "main.py"
        p.write_text(code, encoding="utf-8")
        return p

    def test_oracle_ok(self):
        p = self._write('print("SOMMA=15")\n')
        err, out = verify_runtime("print('SOMMA=15')", p,
                                  oracle_checks=["SOMMA=15"])
        self.assertIsNone(err)
        self.assertIn("SOMMA=15", out)

    def test_oracle_wrong_value(self):
        p = self._write('print("SOMMA=99")\n')
        err, out = verify_runtime("print('SOMMA=99')", p,
                                  oracle_checks=["SOMMA=15"])
        self.assertIsNotNone(err)
        self.assertIn("SOMMA=15", err)
        self.assertIn("SOMMA=99", err)

    def test_oracle_missing(self):
        p = self._write('print("hello")\n')
        err, out = verify_runtime("print('hello')", p,
                                  oracle_checks=["SOMMA=15"])
        self.assertIsNotNone(err)
        self.assertIn("SOMMA=15", err)

    def test_oracle_multiple(self):
        code = 'print("SOMMA=15")\nprint("LEN=3")\n'
        p = self._write(code)
        err, out = verify_runtime(code, p,
                                  oracle_checks=["SOMMA=15", "LEN=3"])
        self.assertIsNone(err)

    def test_oracle_multiple_one_missing(self):
        code = 'print("SOMMA=15")\n'
        p = self._write(code)
        err, out = verify_runtime(code, p,
                                  oracle_checks=["SOMMA=15", "LEN=3"])
        self.assertIsNotNone(err)
        self.assertIn("LEN=3", err)

    def test_no_oracle_checks(self):
        p = self._write('print("hello")\n')
        err, out = verify_runtime("print('hello')", p)
        self.assertIsNone(err)

    def test_oracle_with_markers(self):
        code = 'print("SOMMA=15")\n'
        p = self._write(code)
        err, out = verify_runtime(code, p,
                                  expected_markers=[("SOMMA", "15")],
                                  oracle_checks=["15"])
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
