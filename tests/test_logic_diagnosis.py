"""
test_logic_diagnosis.py — Test unit di D2 (diagnosi errori di logica).

Verifica che diagnose_logic_error suggerisca la causa probabile.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.skill_executor import diagnose_logic_error  # noqa: E402


class TestLogicDiagnosis(unittest.TestCase):
    def test_off_by_one(self):
        fix = diagnose_logic_error("[1,2,3]", "6", "5")
        self.assertIn("off-by-one", fix)

    def test_valore_doppio(self):
        fix = diagnose_logic_error("[5,3,2]", "10", "20")
        self.assertIn("doppio", fix)

    def test_output_vuoto(self):
        fix = diagnose_logic_error("[1,2,3]", "6", "")
        self.assertIn("vuoto", fix)

    def test_generico(self):
        fix = diagnose_logic_error("x", "y", "z")
        self.assertIn("verifica la logica", fix)

    def test_fail_open(self):
        # Non deve sollevare mai
        try:
            diagnose_logic_error(None, None, None)  # type: ignore
        except Exception as e:
            self.fail(f"diagnose_logic_error ha sollevato: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
