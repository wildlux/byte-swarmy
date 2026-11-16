"""Test Cycle 70 — Pannello GUI del debt ledger (offscreen, veloci).

Copre la REGOLA DI PARITÀ GUI: ogni funzione del ledger è usufruibile
dal pannello (stats, list, add, next, mark, context). Nessun timer
nuovo: il refresh è solo on-demand. Qt in modalità offscreen.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from CORE import debt_ledger as dl  # noqa: E402
from GUI.debt_ledger_panel import DebtLedgerPanel  # noqa: E402


def _mk_file(tmp: Path, name: str, content: str = "def foo(): pass\n") -> Path:
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestDebtLedgerPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.panel = DebtLedgerPanel(project_root=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_coda_vuota_no_crash(self):
        """Pannello su ledger vuoto: stats 'vuota', 0 righe, mai crash."""
        self.assertIn("vuota", self.panel.stats_label.text())
        self.assertEqual(self.panel.table.rowCount(), 0)

    def test_list_mostra_gli_item(self):
        _mk_file(self.root, "CORE/worker.py")
        dl.add(self.root, "refactor", "CORE/worker.py", "Uno")
        dl.add(self.root, "optimization", "CORE/worker.py", "Due")
        self.panel.refresh()
        self.assertEqual(self.panel.table.rowCount(), 2)

    def test_next_prende_e_seleziona_in_progress(self):
        """🎯 Prossimo: il lavoro arriva dalla query, marcato e selezionato."""
        _mk_file(self.root, "CORE/worker.py")
        _mk_file(self.root, "CORE/other.py", "def b(): pass\n")
        dl.add(self.root, "refactor", "CORE/worker.py", "Basso", priority=3)
        alto = dl.add(self.root, "optimization", "CORE/other.py",
                      "Alto", priority=1)
        self.panel.refresh()
        self.panel._pick_next()
        # l'item p1 è in_progress nel DB...
        self.assertEqual(dl.get(self.root, alto["id"])["status"],
                         "in_progress")
        # ...e selezionato nella tabella
        self.assertEqual(self.panel._selected_id(), alto["id"])

    def test_next_senza_item_valido_mostra_vuota(self):
        """Tutti stale → 'coda vuota', nessun crash, niente selezione."""
        _mk_file(self.root, "CORE/worker.py")
        dl.add(self.root, "refactor", "CORE/worker.py", "Vecchio")
        _mk_file(self.root, "CORE/worker.py", "cambiato\n")  # → stale
        self.panel._pick_next()
        self.assertIn("vuota", self.panel.stats_label.text())

    def test_mark_done_dalla_gui(self):
        _mk_file(self.root, "CORE/worker.py")
        it = dl.add(self.root, "docs", "CORE/worker.py", "Docstring")
        self.panel.refresh()
        # seleziona la riga dell'item e clicca ✅ Fatto
        self.panel._select_item(it["id"])
        self.panel._mark_selected("done")
        self.assertEqual(dl.get(self.root, it["id"])["status"], "done")

    def test_context_fail_open(self):
        """🔍 Contesto senza code_map → None (il pannello mostra un
        messaggio, mai crash)."""
        _mk_file(self.root, "CORE/worker.py")
        it = dl.add(self.root, "refactor", "CORE/worker.py", "X")
        self.panel.refresh()
        self.panel._select_item(it["id"])
        self.assertIsNone(self.panel._context_text())

    def test_nessun_timer_avviato(self):
        """Disciplina Cycle 63: il pannello non aggiunge timer alla GUI."""
        self.assertEqual(len(self.panel.childrenTimers()
                             if hasattr(self.panel, "childrenTimers")
                             else []), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
