"""Test Cycle 66 — Pausa termica adattiva nel benchmark esterno.

Regola utente: mai sopra 60°C. Un singolo task porta 49→78°C in ~107s
su questo portatile, quindi tra le fasi il benchmark deve aspettare
ATTIVAMENTE che la temperatura scenda (limit - 8°C), non un cooldown
fisso di 30s.

Test senza Ollama e senza sleep reali (time.sleep patchato).
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.external_benchmark import ExternalBenchmark  # noqa: E402


def _mk_zones(tmp: Path, temps_c: list[float]) -> list[str]:
    """Crea file thermal_zone finti (contenuto in milligradi reali)."""
    paths = []
    for i, t in enumerate(temps_c):
        d = tmp / f"zone{i}"
        d.mkdir(exist_ok=True)
        p = d / "temp"
        p.write_text(str(int(t * 1000)), encoding="utf-8")
        paths.append(str(p))
    return paths


class _L:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _bench(tmp: Path) -> ExternalBenchmark:
    return ExternalBenchmark(tmp, bench_target_dir=tmp,
                             models=None, log=_L(), model_key="worker_coder")


class TestThermalPause(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sleeps = []

    def tearDown(self):
        self.tmp.cleanup()

    def _patch_sleep(self):
        return patch("time.sleep", side_effect=lambda s: self.sleeps.append(s))

    def test_gia_fredda_ritorna_subito(self):
        """Temp sotto la soglia di ripresa → True, zero sleep."""
        b = _bench(Path(self.tmp.name))
        zones = _mk_zones(Path(self.tmp.name), [45.0, 40.0])
        with patch("glob.glob", return_value=zones), self._patch_sleep():
            ok = b._thermal_pause(60.0, fase="test")
        self.assertTrue(ok)
        self.assertEqual(self.sleeps, [])

    def test_calda_attende_poi_raffredda(self):
        """Sequenza di letture: 78 → 78 → 52 → True con sleep 10s. La
        soglia di ripresa per limite 60 è limit-8 = 52°C."""
        b = _bench(Path(self.tmp.name))
        # Ogni chiamata ricrea le zone: 2 letture calde, poi fredda
        seq = [[78.0], [78.0], [52.0], [52.0]]

        def fake_glob(pattern):
            temps = seq[min(len(seq) - 1, self.sleeps.__len__())]
            return _mk_zones(Path(self.tmp.name), temps)

        with patch("glob.glob", side_effect=fake_glob), self._patch_sleep():
            ok = b._thermal_pause(60.0, fase="test")
        self.assertTrue(ok)
        # 2 sleep da 10s (2 letture calde) prima della ripresa
        self.assertEqual(self.sleeps, [10.0, 10.0])

    def test_max_wait_scaduto_ritorna_false(self):
        """Temp sempre a 78°C → dopo max_wait_s (accelerato) ritorna False."""
        b = _bench(Path(self.tmp.name))
        zones = _mk_zones(Path(self.tmp.name), [78.0])
        with patch("glob.glob", return_value=zones), self._patch_sleep():
            ok = b._thermal_pause(60.0, fase="test", max_wait_s=30.0)
        self.assertFalse(ok)
        # max_wait 30s / tick 10s → 3 sleep
        self.assertEqual(self.sleeps, [10.0, 10.0, 10.0])

    def test_lettura_impossibile_fail_open(self):
        """Nessun file leggibile → fail-open True senza sleep."""
        b = _bench(Path(self.tmp.name))
        with patch("glob.glob", return_value=[]), self._patch_sleep():
            ok = b._thermal_pause(60.0, fase="test")
        self.assertTrue(ok)
        self.assertEqual(self.sleeps, [])

    def test_soglia_ripresa_mai_sotto_40(self):
        """Con limite basso (45), la ripresa resta ≥ 40°C (offset 8 → 37
        sarebbe troppo freddo: clamp a 40). A 41°C costante → max wait
        scaduto → False."""
        b = _bench(Path(self.tmp.name))
        zones = _mk_zones(Path(self.tmp.name), [41.0])
        with patch("glob.glob", return_value=zones), self._patch_sleep():
            ok = b._thermal_pause(45.0, fase="test", max_wait_s=20.0)
        self.assertFalse(ok)
        self.assertEqual(self.sleeps, [10.0, 10.0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
