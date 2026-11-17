"""Test preparati per Cycle 78 (NON eseguiti ora — da lanciare domani).

Regressione sul fix del sensore B0D4 (Cycle 74-77): il gate termico deve
usare la temperatura REALE della CPU (coretemp), non la zona DPTF B0D4
che satura a 100.0°C esatti sotto carico e resta bloccata (lezione UEFI).

Questi test fallirebbero se qualcuno ripristinasse la max() su tutte le
zone (il bug che ha causato il blocco UEFI).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.routing import _read_cpu_temp_now  # noqa: E402
from tools.swarm_refactor_session import read_max_temp  # noqa: E402


class TestSensorSourceRealCPU(unittest.TestCase):
    """Il gate termico usa la CPU vera, non il falso B0D4."""

    def test_read_max_temp_non_e_b0d4_saturato(self):
        """read_max_temp() (runner) non deve restituire 100.0 (B0D4
        saturo) quando la CPU vera è più bassa."""
        t = read_max_temp()
        self.assertLess(t, 95.0,
                        "probabile lettura di B0D4 saturo (100.0) invece "
                        "della CPU vera")

    def test_read_cpu_temp_now_non_e_b0d4_saturato(self):
        t = _read_cpu_temp_now()
        self.assertLess(t, 95.0,
                        "probabile lettura di B0D4 saturo (100.0)")

    def test_read_max_temp_coerente_con_coretemp(self):
        """La lettura del runner deve essere <= max coretemp + 5°C
        (tolleranza per differenze di campionamento)."""
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
        t = read_max_temp()
        self.assertLessEqual(t, max(coretemps) + 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
