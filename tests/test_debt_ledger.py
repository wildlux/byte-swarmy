"""Test Cycle 68 — Registro del debito tecnico (CORE/debt_ledger.py).

Le 3 regole di design sotto test:
1. API/CLI deterministiche (niente SQL libero dall'LLM)
2. file_hash anti-stantio: file cambiato → item 'stale', mai proposto
3. next() dalla coda: priority ASC + created ASC, un item per sessione
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE import debt_ledger as dl  # noqa: E402


def _mk(tmp: Path, name: str = "CORE/worker.py", content: str = "def foo(): pass\n") -> Path:
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestDebtLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_restituisce_item_con_hash(self):
        _mk(self.root)
        it = dl.add(self.root, "refactor", "CORE/worker.py", "Estrarre helper",
                    rationale="troppo lungo", priority=1, effort="m")
        self.assertEqual(it["status"], "open")
        self.assertEqual(it["priority"], 1)
        self.assertTrue(it["file_hash"])  # sha1 del file ESISTENTE
        self.assertEqual(it["kind"], "refactor")

    def test_validazioni_kind_priority_effort(self):
        with self.assertRaises(ValueError):
            dl.add(self.root, "zzz", "x.py", "t")
        with self.assertRaises(ValueError):
            dl.add(self.root, "refactor", "x.py", "t", priority=9)
        with self.assertRaises(ValueError):
            dl.add(self.root, "refactor", "x.py", "t", effort="xxl")

    def test_next_ordina_per_priorita_poi_created(self):
        _mk(self.root)
        dl.add(self.root, "refactor", "CORE/worker.py", "Basso", priority=3)
        dl.add(self.root, "refactor", "CORE/worker.py", "Alto", priority=1)
        it = dl.next(self.root)
        self.assertEqual(it["title"], "Alto")

    def test_file_cambiato_diventa_stale(self):
        _mk(self.root, content="v1\n")
        dl.add(self.root, "refactor", "CORE/worker.py", "Vecchio")
        _mk(self.root, content="v2 modificato\n")  # cambia il file
        self.assertIsNone(dl.next(self.root))      # non propone alla cieca
        stale = dl.list_items(self.root, status="stale")
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["status"], "stale")

    def test_file_assente_alla_registrazione_ancora_proposto(self):
        # file che NON esiste (es. nuovo file da creare): hash None
        dl.add(self.root, "test", "CORE/nuovo.py", "Scrivere test")
        it = dl.next(self.root)
        self.assertIsNotNone(it)
        self.assertIsNone(it["file_hash"])

    def test_done_non_piu_proposto(self):
        _mk(self.root)
        it = dl.add(self.root, "docs", "CORE/worker.py", "Docstring")
        dl.mark(self.root, it["id"], "in_progress")
        dl.mark(self.root, it["id"], "done")
        self.assertIsNone(dl.next(self.root))
        self.assertEqual(dl.stats(self.root), {"done": 1})

    def test_prefer_kind_ripriorizza_senza_violare_stale(self):
        _mk(self.root, name="CORE/a.py")
        _mk(self.root, name="CORE/b.py", content="def b(): pass\n")
        hi = dl.add(self.root, "refactor", "CORE/a.py", "Refactor p1", priority=1)
        dl.add(self.root, "test", "CORE/b.py", "Test p2", priority=2)
        # prefer test: il p2 test viene PRIMA del p1 refactor
        it = dl.next(self.root, prefer_kind="test")
        self.assertEqual(it["title"], "Test p2")
        # senza prefer: torna il p1
        self.assertEqual(dl.next(self.root)["id"], hi["id"])

    def test_next_scelta_fifo_a_parita_priorita(self):
        _mk(self.root, name="CORE/a.py")
        _mk(self.root, name="CORE/b.py", content="x\n")
        first = dl.add(self.root, "refactor", "CORE/a.py", "Primo", priority=2)
        dl.add(self.root, "refactor", "CORE/b.py", "Secondo", priority=2)
        self.assertEqual(dl.next(self.root)["id"], first["id"])

    def test_context_fail_open_senza_codemap(self):
        # progetto tmp senza .byteswarm/codemap.db → [] e mai crash
        _mk(self.root)
        self.assertEqual(dl.context_for_file(self.root, "CORE/worker.py"), [])

    def test_mark_status_non_valido(self):
        _mk(self.root)
        it = dl.add(self.root, "refactor", "CORE/worker.py", "X")
        with self.assertRaises(ValueError):
            dl.mark(self.root, it["id"], "zzz")

    def test_cli_end_to_end(self):
        """Smoke CLI: add → next → done con --root tmp (per la skill)."""
        _mk(self.root)
        r = dl.main(["add", "--root", str(self.root), "--kind", "refactor",
                     "--file", "CORE/worker.py", "--title", "Via CLI"])
        self.assertEqual(r, 0)
        r = dl.main(["next", "--root", str(self.root)])
        self.assertEqual(r, 0)
        r = dl.main(["done", "--root", str(self.root), "1"])
        self.assertEqual(r, 0)
        self.assertEqual(dl.stats(self.root), {"done": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
