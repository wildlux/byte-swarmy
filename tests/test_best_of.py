"""Test Fase D-15 — best-of-N con il gate come giudice (CORE/best_of.py)."""

import sys
import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tempfile
from types import SimpleNamespace

from CORE.best_of import (  # noqa: E402
    Candidate,
    evaluate_candidates,
    judge_candidates,
    select_passing,
    select_rejected,
)
from CORE.config_model import load_typed_config  # noqa: E402
from CORE.worker import Worker  # noqa: E402

_OK = "def ok():\n    return 1\n"
_BAD = "def bad(:\n    pass\n"


def _self():
    return SimpleNamespace(MAX_BEST_OF=Worker.MAX_BEST_OF)


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

    # --- B1 (2026-11-22): gate-giudice con N candidati finti --------------
    def test_giudice_sceglie_primo_che_passa(self):
        r = judge_candidates(
            [_BAD, _OK, "def terzo():\n    return 3\n"],
            refs_by_index={}, kinds=["function"] * 3, best_of=3)
        self.assertTrue(r.ok)
        self.assertEqual(r.selected_index, 1)
        self.assertEqual(r.selected_code, _OK)
        self.assertEqual(r.reason, "first_passing")
        self.assertEqual(r.evaluated, 3)

    def test_giudice_deterministico_e_limitato_da_best_of(self):
        codes = [_OK, _BAD, _OK]
        kinds = ["function"] * 3
        a = judge_candidates(codes, {}, kinds, best_of=1)
        b = judge_candidates(codes, {}, kinds, best_of=1)
        self.assertEqual(a, b)  # funzione pura
        self.assertEqual(a.evaluated, 1)
        self.assertEqual(a.limit, 1)
        self.assertEqual(a.selected_index, 0)
        c = judge_candidates([_BAD, _BAD, _OK], {}, kinds, best_of=3)
        self.assertEqual(c.selected_index, 2)

    def test_giudice_rifiuta_tutti(self):
        r = judge_candidates([_BAD, _BAD, _BAD], {}, ["function"] * 3,
                             best_of=3)
        self.assertIsNone(r.selected_index)
        self.assertEqual(r.reason, "all_rejected")
        self.assertFalse(r.ok)
        self.assertEqual(len(r.verdicts), 3)

    def test_flag_best_of_n_letto_da_config_tipizzata(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.toml"
            p.write_text('[orchestrator]\nbest_of_n = 5\n', encoding="utf-8")
            self.assertEqual(load_typed_config(p).orchestrator.best_of_n, 5)
            p.write_text('[orchestrator]\nbest_of_n = 99\n', encoding="utf-8")
            self.assertEqual(load_typed_config(p).orchestrator.best_of_n, 8)
            p.write_text('[orchestrator]\nbest_of_n = 0\n', encoding="utf-8")
            self.assertEqual(load_typed_config(p).orchestrator.best_of_n, 1)

    def test_best_of_n_precedenza_e_clamp(self):
        fake = _self()
        self.assertEqual(Worker._best_of_n(fake, {"best_of": 3}), 3)
        self.assertEqual(Worker._best_of_n(fake, {"best_of": 99}), 8)
        self.assertEqual(Worker._best_of_n(fake, {"best_of": 0}), 1)
        self.assertEqual(Worker._best_of_n(fake, {"best_of": True}), 1)
        self.assertEqual(Worker._best_of_n(fake, {}), 1)  # config repo = 1


if __name__ == "__main__":
    unittest.main()
