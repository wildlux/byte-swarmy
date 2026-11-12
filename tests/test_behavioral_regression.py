"""
test_behavioral_regression.py — Test unit di A3 (gate di regressione).

Verifica che check_refactor_regression rilevi cambiamenti di comportamento.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.behavioral_diff import check_refactor_regression  # noqa: E402


class TestBehavioralRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, code: str) -> Path:
        p = self.tmp / "main.py"
        p.write_text(code, encoding="utf-8")
        return p

    def test_primo_run_crea_snapshot(self):
        p = self._write('print("hello")\n')
        ok, diff = check_refactor_regression(p, inputs=[""])
        self.assertTrue(ok)
        self.assertEqual(diff, "")

    def test_comportamento_preservato(self):
        p = self._write('print("hello")\n')
        # Crea snapshot
        check_refactor_regression(p, inputs=[""])
        # Riscrivi lo stesso codice → ok
        p.write_text('print("hello")\n', encoding="utf-8")
        ok, diff = check_refactor_regression(p, inputs=[""])
        self.assertTrue(ok)

    def test_comportamento_cambiato(self):
        p = self._write('print("hello")\n')
        check_refactor_regression(p, inputs=[""])
        # Modifica il codice → divergenza
        p.write_text('print("goodbye")\n', encoding="utf-8")
        ok, diff = check_refactor_regression(p, inputs=[""])
        self.assertFalse(ok)
        self.assertIn("COMPORTAMENTO CAMBIATO", diff)

    def test_file_inesistente(self):
        p = self.tmp / "nope.py"
        ok, diff = check_refactor_regression(p, inputs=[""])
        self.assertTrue(ok)

    def test_fail_open(self):
        p = self._write('print("x")\n')
        # Non deve sollevare mai
        try:
            check_refactor_regression(p, inputs=[""])
        except Exception as e:
            self.fail(f"ha sollevato: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
