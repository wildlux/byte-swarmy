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

    def test_rigenera_da_feedback(self):
        """Il pulsante riporta byte, esito e se il contenuto è cambiato."""
        import subprocess
        import tempfile
        from unittest import mock

        svg = ('<svg xmlns="http://www.w3.org/2000/svg" '
               'width="100" height="100"><rect width="10" height="10"/>'
               '</svg>')
        with tempfile.TemporaryDirectory() as tmp:
            p = ImprovementsPanel()
            p._svg_path = Path(tmp) / "miglioramenti.svg"
            p._svg_path.write_text(svg, encoding="utf-8")
            done = subprocess.CompletedProcess(args=[], returncode=0,
                                               stdout="scritto", stderr="")
            with mock.patch.object(subprocess, "run", return_value=done):
                p.btn_regen.click()
            self.assertIn("SVG identico", p._status.text())
            self.assertIn("byte", p._status.text())
            self.assertIsNotNone(p._svg)

    def test_rigenera_errore_visibile(self):
        """Un fallimento dello script non resta silenzioso."""
        import subprocess
        from unittest import mock

        p = ImprovementsPanel()
        bad = subprocess.CompletedProcess(args=[], returncode=1,
                                          stdout="", stderr="boom")
        with mock.patch.object(subprocess, "run", return_value=bad):
            p.btn_regen.click()
        self.assertIn("errore", p._status.text())
        self.assertIn("boom", p._status.text())


if __name__ == "__main__":
    unittest.main()
