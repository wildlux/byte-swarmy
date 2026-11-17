"""Test preparati per Cycle 78 (NON eseguiti ora — da lanciare domani).

Regressione sul display di VENTOLA/ventola.py: il numero primario è la
CPU vera (coretemp), la zona più calda (incluso B0D4 saturo) è solo
riga secondaria con avviso. Evita che l'utente veda un "100.0°C
bloccato" pensando sia la CPU.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from VENTOLA.ventola import (  # noqa: E402
    FanControl, cpu_core_temp, hottest_zone,
)


class TestVentolaDisplay(unittest.TestCase):
    def test_cpu_core_temp_e_coretemp(self):
        """cpu_core_temp() deve tornare il max per-core di coretemp,
        non la max su tutte le zone (che include B0D4 saturo)."""
        import glob
        coretemps = []
        for d in glob.glob("/sys/class/hwmon/hwmon*"):
            try:
                if Path(d, "name").read_text().strip() != "coretemp":
                    continue
                for p in glob.glob(f"{d}/temp*_input"):
                    coretemps.append(float(Path(p).read_text().strip())
                                     / 1000.0)
            except (OSError, ValueError):
                continue
        if not coretemps:
            self.skipTest("coretemp non disponibile")
        self.assertAlmostEqual(cpu_core_temp(), max(coretemps), delta=0.1)

    def test_hottest_zone_restituisce_tuple(self):
        t, name = hottest_zone()
        self.assertIsInstance(t, float)
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)

    def test_tick_mostra_cpu_primario(self):
        """Il label primario deve contenere 'CPU' (non solo il numero)."""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        w = FanControl()
        w._tick()
        self.assertIn("CPU", w.temp.text())
        w.close()

    def test_tick_state_mostra_zona_calda(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        w = FanControl()
        w._tick()
        self.assertIn("zona più calda", w.state.text())
        w.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
