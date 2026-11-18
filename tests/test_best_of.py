"""Test Fase D-15 — best-of-N con il gate come giudice (CORE/best_of.py)."""

import sys
import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.best_of import (  # noqa: E402
    Candidate,
    evaluate_candidates,
    select_passing,
    select_rejected,
)


class TestBestOf(unittest.TestCase):
    def test_candidato_valido_vince(self):
        cands = evaluate_candidates(
            ["def a():\n    return 1\n", "def b(:\n    pass\n"],
            refs_by_index={0: [], 1: []},
            kinds=["function", "function"],
        )
        best = select_passing(cands)
        self.assertIsInstance(best, Candidate)
        self.assertEqual(best.index, 0)
        self.assertTrue(best.verdict.ok)

    def test_nessun_candidato_passa(self):
        cands = evaluate_candidates(
            ["def b(:\n    pass\n"],
            refs_by_index={0: []},
            kinds=["function"],
        )
        self.assertIsNone(select_passing(cands))
        self.assertEqual(len(select_rejected(cands)), 1)
        self.assertFalse(cands[0].verdict.ok)

    def test_kinds_mismatch_rifiuta(self):
        with self.assertRaises(ValueError):
            evaluate_candidates(["x = 1\n"], refs_by_index={}, kinds=[])


if __name__ == "__main__":
    unittest.main()
