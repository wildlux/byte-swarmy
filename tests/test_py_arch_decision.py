"""Test P3-7 — skill py-arch-decision: regole decision tree v2."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestPyArchDecision(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "SKILLS" / "py-arch-decision.md"
        self.text = self.path.read_text(encoding="utf-8")

    def test_skill_esiste(self):
        self.assertTrue(self.path.exists())

    def test_regole_nuove_presenti(self):
        for name in ("CACHE", "RETRY", "VALIDATION"):
            self.assertIn(name, self.text, f"pattern {name} mancante")

    def test_decision_tree_ha_9_regole(self):
        rows = re.findall(r"^\|\s*\d+\s*\|", self.text, re.M)
        self.assertGreaterEqual(len(rows), 9)

    def test_template_presente(self):
        self.assertIn("PATTERN_SCELTO", self.text)
        self.assertIn("TRADEOFF", self.text)
        self.assertIn("def main():", self.text)

    def test_fallback_class(self):
        self.assertIn("fallback", self.text.lower())
        self.assertIn("CLASS", self.text)


if __name__ == "__main__":
    unittest.main()
