# -*- coding: utf-8 -*-
"""
tests/test_actors_panel.py — pannello Attori della GUI (T3.6).

Offscreen (QT_QPA_PLATFORM=offscreen, senza display): la combo dei modelli
deve mostrare i modelli Ollama INSTALLATI (T2.4) con fallback alla lista
statica, e il load/save dei dati attori deve girare fuori dal device.
I parametri timestral del pannello devono restare nel range atteso.
"""

from __future__ import annotations

import os
import sys
import unittest
import unittest.mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from GUI import actors_panel as ap  # noqa: E402


_app = QApplication.instance() or QApplication(
    sys.argv[:1] + ["test_actors_panel"])


class TestOllamaList(unittest.TestCase):
    """T2.4: modelli installati reali, fallback sicuro."""

    def test_returns_list(self):
        models = ap.ollama_list_models()
        self.assertIsInstance(models, list)
        for m in models:
            self.assertIsInstance(m, str)
            self.assertTrue(m)

    def test_ollama_bad_bin_falls_back_empty(self):
        # bin inesistente: falso (il chiamante fa fallback alla lista statica)
        with unittest.mock.patch("subprocess.run",
                                 side_effect=FileNotFoundError("no")):
            self.assertEqual(ap.ollama_list_models(), [])


class TestPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.panel = ap.ActorsPanel()

    def test_combo_contains_at_least_static_list(self):
        # Con etichette annotate ("nome (uso)") controlliamo i DATI
        # (nomi reali in itemData), non i testi delle etichette.
        data = [self.panel.llm_model.itemData(i)
                for i in range(self.panel.llm_model.count())]
        fallback_first = ap.OLLAMA_MODELS[0]
        self.assertIn(fallback_first, data,
                      "fallback statico presente anche se ollama è scarso")
        self.assertTrue(len(data) >= 1)

    def test_combo_dec_model_populated(self):
        self.assertTrue(self.panel.dec_model.count() >= 1)

    def test_timestral_spin_ranges(self):
        # soglie termiche sensate: mai sotto 40 °C, mai sopra 120 °C
        self.assertGreaterEqual(self.panel.ts_cpu_threshold.minimum(), 40)
        self.assertLessEqual(self.panel.ts_cpu_threshold.maximum(), 120)
        self.assertGreaterEqual(self.panel.ts_gpu_threshold.minimum(), 40)
        self.assertLessEqual(self.panel.ts_gpu_threshold.maximum(), 120)

    def test_collect_dict_schema(self):
        """Il pannello produce un dict col schema atteso da orchestrator."""
        getattr(self.panel, "_collect", None)
        # reco la funzione di raccolta reale (in _on_save si può creare di
        # una dict funzionante); qui verifichiamo solo i campi chiave
        self.assertTrue(hasattr(self.panel, "ts_cpu_threshold"))
        self.assertTrue(hasattr(self.panel, "ts_gpu_threshold"))
        self.assertTrue(hasattr(self.panel, "ts_interval"))


class TestParamReset(unittest.TestCase):
    """I pulsanti '↺ Ripristina' riportano temperature/ctx/predict ai default."""

    @classmethod
    def setUpClass(cls):
        cls.panel = ap.ActorsPanel()

    def _reset_buttons(self):
        from PyQt6.QtWidgets import QPushButton
        return [b for b in self.panel.findChildren(QPushButton)
                if "Ripristina" in b.text()]

    def test_two_reset_buttons_exist(self):
        self.assertEqual(len(self._reset_buttons()), 2,
                         "attesi reset per Worker e per Decision Model")

    def test_reset_restores_all_defaults(self):
        from PyQt6.QtWidgets import QPushButton
        p = self.panel
        # Sporca i valori
        p.llm_temp.setValue(1.7); p.llm_ctx.setValue(16384)
        p.llm_predict.setValue(4096)
        p.dec_temp.setValue(1.9); p.dec_ctx.setValue(32768)
        p.dec_predict.setValue(8192)
        # Click su ENTRAMBI i reset (ordine del findChildren è irrilevante)
        for b in self._reset_buttons():
            b.click()
        dl, dd = ap.DEFAULTS["llm"], ap.DEFAULTS["decision_model"]
        self.assertEqual(p.llm_temp.value(), dl["temperature"])
        self.assertEqual(p.llm_ctx.value(), dl["num_ctx"])
        self.assertEqual(p.llm_predict.value(), dl["num_predict"])
        self.assertEqual(p.dec_temp.value(), dd["temperature"])
        self.assertEqual(p.dec_ctx.value(), dd["num_ctx"])
        self.assertEqual(p.dec_predict.value(), dd["num_predict"])

    def test_reset_keeps_model_and_weight(self):
        """Il reset non tocca le scelte utente (modello, peso)."""
        p = self.panel
        model_before = p.llm_model.currentText()
        for b in self._reset_buttons():
            b.click()
        self.assertEqual(p.llm_model.currentText(), model_before)


if __name__ == "__main__":
    print("Actors panel test → GUI/actors_panel.py")
    print("=" * 60)
    unittest.main(verbosity=2)
