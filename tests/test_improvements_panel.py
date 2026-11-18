"""Test ImprovementsPanel — grafico miglioramenti dentro la GUI.

Offscreen, zero LLM. Copre:
  - costruzione + SVG caricato (renderer valido, dimensione reale)
  - back_btn presente (regola di parità GUI)
  - fallback onesto se l'SVG manca (messaggio, niente crash)
  - path resolution indipendente dal cwd
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

from GUI.improvements_panel import ImprovementsPanel  # noqa: E402


class TestImprovementsPanel(unittest.TestCase):
    def test_svg_caricato_e_valido(self):
        p = ImprovementsPanel()
        self.assertIsNotNone(p._svg, "l'SVG reale deve essere caricato")
        self.assertTrue(p._svg.renderer().isValid())
        size = p._svg.renderer().defaultSize()
        self.assertGreater(size.width(), 400)
        self.assertGreater(size.height(), 400)

    def test_back_btn_presente(self):
        """Regola di parità GUI: back_btn per tornare alla Plancia."""
        from PyQt6.QtWidgets import QPushButton
        p = ImprovementsPanel()
        backs = [b for b in p.findChildren(QPushButton)
                 if b.objectName() == "back_btn"]
        self.assertTrue(backs, "nessun back_btn nel pannello miglioramenti")

    def test_fallback_svg_mancante(self):
        """Se l'SVG non esiste: messaggio onesto, niente crash."""
        p = ImprovementsPanel()
        old = p._svg_path
        try:
            p._svg_path = old.parent / "innesistente.svg"
            p._load_svg()
            self.assertIsNone(p._svg)
            self.assertIn("mancante", p._status.text().lower())
        finally:
            p._svg_path = old

    def test_path_indipendente_dal_cwd(self):
        """La risoluzione non dipende dalla cwd del processo."""
        p = ImprovementsPanel()
        self.assertTrue(p._svg_path.is_absolute())
        self.assertTrue(p._svg_path.exists())


if __name__ == "__main__":
    unittest.main()
