"""
test_model_selector.py — Test unit del selettore modelli (M10).

Copre:
  A. load_suite_evidence: lettura results.json + mapping tramite config
     - caso reale (risultati per worker_coder, worker_granite)
     - file assente → {}
     - file corrotto → {}
     - modello in results ma non in config → non mappato (saltato)
     - mean_secs/mean_attempts calcolati correttamente
  B. _evidence_boost_for_model: soglie di boost
     - 10/10 → +30 (+ bonus secondari)
     - 7-9/10 → +20
     - 5-6/10 → +10
     - 1-4/10 → -10
     - 0/10 → -20
     - assente → (0, "")
     - mean_attempts <= 1.2 → +5
     - mean_secs <= 15 → +5
  C. score_model_for_role con evidence
     - boost applicato al punteggio totale
     - reason include "evidence"
     - evidence=None (default pre-M10) → nessun boost, comportamento
       invariato (regressione)
  D. get_recommendations end-to-end
     - la chiave _evidence è presente nel dict ritornato
     - se il file results.json manca, _evidence è {} e non crasha

Tutti i test sono SENZA LLM: file temporanei + mock hardware.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.model_selector import (  # noqa: E402
    load_suite_evidence,
    _evidence_boost_for_model,
    score_model_for_role,
    ROLE_DEFINITIONS,
)


def _make_results_file(tmp: Path, content: dict) -> Path:
    """Scrive un results.json con content in state/suite_compare/."""
    out_dir = tmp / "state" / "suite_compare"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "results.json"
    p.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return p


def _make_config_file(tmp: Path, models: dict) -> Path:
    """Scrive un config.toml con [models.<key>].name = value."""
    p = tmp / "config.toml"
    lines = []
    for key, name in models.items():
        lines.append(f"[models.{key}]")
        lines.append(f'name = "{name}"')
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _fake_model(name: str, size_gb: float = 1.5,
                family: str = "qwen2", families=None,
                capabilities=None, quantization: str = "Q4_K_M") -> dict:
    """Crea un dict model come quello restituito da get_ollama_models."""
    return {
        "name": name,
        "size_bytes": int(size_gb * 1e9),
        "size_gb": size_gb,
        "family": family,
        "families": families or [family],
        "capabilities": capabilities or ["completion"],
        "parameter_size": "",
        "quantization": quantization,
        "context_length": 4096,
    }


HARDWARE_NO_GPU = {"vram_gb": 0, "ram_gb": 16, "temp_c": 0}


class TestLoadSuiteEvidence(unittest.TestCase):
    """A. Lettura results.json + mapping tramite config."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lettura_normale_mappa_chiavi_a_nomi(self):
        results = {
            "worker_coder": {
                "T1": {"ok": True, "attempts": 1, "secs": 10, "done": True},
                "T2": {"ok": True, "attempts": 1, "secs": 5, "done": True},
            },
            "worker_granite": {
                "T1": {"ok": True, "attempts": 1, "secs": 12, "done": True},
                "T2": {"ok": False, "attempts": 3, "secs": 300, "done": True},
            },
        }
        rp = _make_results_file(self.tmp, results)
        cp = _make_config_file(self.tmp, {
            "worker_coder": "qwen2.5-coder:3b",
            "worker_granite": "granite4:7b-a1b-h",
        })
        ev = load_suite_evidence(rp, cp)
        # Verifica mappatura chiavi → nomi
        self.assertIn("qwen2.5-coder:3b", ev)
        self.assertIn("granite4:7b-a1b-h", ev)
        # Verifica conteggi
        self.assertEqual(ev["qwen2.5-coder:3b"]["pass"], 2)
        self.assertEqual(ev["qwen2.5-coder:3b"]["total"], 2)
        self.assertEqual(ev["granite4:7b-a1b-h"]["pass"], 1)
        self.assertEqual(ev["granite4:7b-a1b-h"]["total"], 2)
        # mean_secs e mean_attempts
        self.assertEqual(ev["qwen2.5-coder:3b"]["mean_secs"], 7.5)
        self.assertEqual(ev["qwen2.5-coder:3b"]["mean_attempts"], 1.0)
        # score = pass_rate * 100
        self.assertEqual(ev["qwen2.5-coder:3b"]["score"], 100.0)
        self.assertEqual(ev["granite4:7b-a1b-h"]["score"], 50.0)

    def test_file_assente_fail_open(self):
        ev = load_suite_evidence(
            self.tmp / "non_esiste.json",
            self.tmp / "non_esiste.toml",
        )
        self.assertEqual(ev, {})

    def test_file_corrotto_fail_open(self):
        rp = self.tmp / "results.json"
        rp.write_text("NOT-JSON-AT-ALL", encoding="utf-8")
        cp = _make_config_file(self.tmp, {"worker_coder": "qwen2.5-coder:3b"})
        ev = load_suite_evidence(rp, cp)
        self.assertEqual(ev, {})

    def test_modello_in_results_non_in_config_saltato(self):
        results = {
            "worker_coder": {"T1": {"ok": True, "attempts": 1, "secs": 10}},
            "modello_orfano": {"T1": {"ok": True, "attempts": 1, "secs": 10}},
        }
        rp = _make_results_file(self.tmp, results)
        # config.toml ha solo worker_coder, non modello_orfano
        cp = _make_config_file(self.tmp, {"worker_coder": "qwen2.5-coder:3b"})
        ev = load_suite_evidence(rp, cp)
        # Solo worker_coder → mappato
        self.assertIn("qwen2.5-coder:3b", ev)
        # modello_orfano non è in config → non mappato
        self.assertNotIn("modello_orfano", ev)
        self.assertEqual(len(ev), 1)

    def test_risultato_vuoto_fail_open(self):
        results = {"worker_coder": {}}
        rp = _make_results_file(self.tmp, results)
        cp = _make_config_file(self.tmp, {"worker_coder": "qwen2.5-coder:3b"})
        ev = load_suite_evidence(rp, cp)
        # 0 task → non incluso nel dict evidence
        self.assertEqual(ev, {})

    def test_config_assente_fail_open(self):
        results = {
            "worker_coder": {"T1": {"ok": True, "attempts": 1, "secs": 10}}
        }
        rp = _make_results_file(self.tmp, results)
        # config.toml NON esiste → niente mappatura → {}
        ev = load_suite_evidence(rp, self.tmp / "non_esiste.toml")
        self.assertEqual(ev, {})


class TestEvidenceBoost(unittest.TestCase):
    """B. Soglie di boost/penalty in base all'evidence."""

    def test_10_su_10_boost_30(self):
        ev = {"m": {"pass": 10, "total": 10, "mean_attempts": 1.0,
                    "mean_secs": 10.0, "score": 100.0}}
        boost, reason = _evidence_boost_for_model("m", ev)
        # +30 base +5 (attempts ≤ 1.2) +5 (secs ≤ 15) = +40
        self.assertEqual(boost, 40.0)
        self.assertIn("evidence 10/10", reason)

    def test_8_su_10_boost_20(self):
        ev = {"m": {"pass": 8, "total": 10, "mean_attempts": 2.0,
                    "mean_secs": 50.0, "score": 80.0}}
        boost, reason = _evidence_boost_for_model("m", ev)
        # +20 base, no bonus (attempts > 1.2, secs > 15)
        self.assertEqual(boost, 20.0)
        self.assertIn("evidence 8/10", reason)

    def test_6_su_10_boost_10(self):
        ev = {"m": {"pass": 6, "total": 10, "mean_attempts": 2.0,
                    "mean_secs": 50.0, "score": 60.0}}
        boost, _ = _evidence_boost_for_model("m", ev)
        self.assertEqual(boost, 10.0)

    def test_4_su_10_penalty_10(self):
        ev = {"m": {"pass": 4, "total": 10, "mean_attempts": 3.0,
                    "mean_secs": 100.0, "score": 40.0}}
        boost, reason = _evidence_boost_for_model("m", ev)
        self.assertEqual(boost, -10.0)
        self.assertIn("weak", reason)

    def test_0_su_10_penalty_20(self):
        ev = {"m": {"pass": 0, "total": 10, "mean_attempts": 3.0,
                    "mean_secs": 100.0, "score": 0.0}}
        boost, reason = _evidence_boost_for_model("m", ev)
        self.assertEqual(boost, -20.0)
        self.assertIn("rejected", reason)

    def test_modello_assente_nessun_boost(self):
        ev = {"altro_modello": {"pass": 10, "total": 10}}
        boost, reason = _evidence_boost_for_model("m", ev)
        self.assertEqual(boost, 0.0)
        self.assertEqual(reason, "")

    def test_evidence_vuota_nessun_boost(self):
        boost, reason = _evidence_boost_for_model("m", {})
        self.assertEqual(boost, 0.0)
        self.assertEqual(reason, "")

    def test_bonus_attempts_e_secs_solo_se_pass_maggiore_di_0(self):
        # 0/10 non deve ricevere bonus secondari
        ev = {"m": {"pass": 0, "total": 10, "mean_attempts": 1.0,
                    "mean_secs": 5.0, "score": 0.0}}
        boost, _ = _evidence_boost_for_model("m", ev)
        # Solo -20 (penalty), no bonus
        self.assertEqual(boost, -20.0)

    def test_pass_rate_70_percento_esatto_soglia_20(self):
        # 7/10 = 0.7 esatto, deve entrare nel tier 7-9/10 (+20)
        ev = {"m": {"pass": 7, "total": 10, "mean_attempts": 2.0,
                    "mean_secs": 50.0, "score": 70.0}}
        boost, _ = _evidence_boost_for_model("m", ev)
        self.assertEqual(boost, 20.0)

    def test_pass_rate_50_percento_esatto_soglia_10(self):
        ev = {"m": {"pass": 5, "total": 10, "mean_attempts": 2.0,
                    "mean_secs": 50.0, "score": 50.0}}
        boost, _ = _evidence_boost_for_model("m", ev)
        self.assertEqual(boost, 10.0)


class TestScoreWithEvidence(unittest.TestCase):
    """C. score_model_for_role integra l'evidence boost."""

    def test_evidence_none_comportamento_pre_m10(self):
        """Con evidence=None, il punteggio deve essere uguale a pre-M10
        (regressione: niente boost)."""
        m = _fake_model("qwen2.5-coder:3b", size_gb=1.5, family="qwen2")
        hw = HARDWARE_NO_GPU
        score_no_ev, _ = score_model_for_role(m, "worker_coder", hw,
                                                evidence=None)
        # Stesso calcolo senza evidence
        score_default, _ = score_model_for_role(m, "worker_coder", hw)
        self.assertEqual(score_no_ev, score_default)

    def test_evidence_10_su_10_aumenta_punteggio(self):
        # Modello NON in preferred_names e con size > ideal: score base
        # più basso → il boost ha margine per aumentarlo senza clamping.
        m = _fake_model("llama3.2:3b", size_gb=2.5, family="llama",
                        quantization="Q4_K_M")
        hw = HARDWARE_NO_GPU
        score_base, _ = score_model_for_role(m, "worker_coder", hw,
                                              evidence=None)
        # Il modello "llama3.2:3b" non è in preferred_names, famiglia
        # llama è preferred → 50 base + 20 size + 15 family + 0 name
        # + 5 quant = 90. Se per caso è già > 90 abbasso l'hardware per
        # dargli un thermal penalty.
        self.assertLess(score_base, 95,
                        "Score base deve avere margine per il boost")
        ev = {"llama3.2:3b": {"pass": 10, "total": 10,
                              "mean_attempts": 1.0,
                              "mean_secs": 10.0, "score": 100.0}}
        score_ev, reason = score_model_for_role(m, "worker_coder", hw,
                                                 evidence=ev)
        # Boost deve essere applicato (+40 = +30 +5 +5)
        self.assertGreater(score_ev, score_base)
        self.assertIn("evidence 10/10", reason)

    def test_evidence_0_su_10_diminuisce_punteggio(self):
        m = _fake_model("qwen2.5-coder:3b", size_gb=1.5, family="qwen2")
        hw = HARDWARE_NO_GPU
        score_base, _ = score_model_for_role(m, "worker_coder", hw,
                                              evidence=None)
        ev = {"qwen2.5-coder:3b": {"pass": 0, "total": 10,
                                   "mean_attempts": 3.0,
                                   "mean_secs": 200.0, "score": 0.0}}
        score_ev, reason = score_model_for_role(m, "worker_coder", hw,
                                                 evidence=ev)
        self.assertLess(score_ev, score_base)
        self.assertIn("rejected", reason)

    def test_evidence_modello_non_presente_nessun_effetto(self):
        m = _fake_model("qwen2.5-coder:3b", size_gb=1.5, family="qwen2")
        hw = HARDWARE_NO_GPU
        score_base, _ = score_model_for_role(m, "worker_coder", hw,
                                              evidence=None)
        # Evidence ha un ALTRO modello, non questo
        ev = {"granite4:7b-a1b-h": {"pass": 10, "total": 10,
                                     "mean_attempts": 1.0,
                                     "mean_secs": 10.0, "score": 100.0}}
        score_ev, _ = score_model_for_role(m, "worker_coder", hw,
                                            evidence=ev)
        self.assertEqual(score_ev, score_base)

    def test_evidence_non_cambia_hard_gates(self):
        """Un modello che viola l'hard gate (VRAM troppo piccola) deve
        restituire 0 anche con evidence 10/10."""
        m = _fake_model("qwen2.5-coder:3b", size_gb=5.0)  # 5 GB
        hw = {"vram_gb": 4.0, "ram_gb": 16, "temp_c": 0}  # max 3 GB
        ev = {"qwen2.5-coder:3b": {"pass": 10, "total": 10,
                                   "mean_attempts": 1.0,
                                   "mean_secs": 10.0, "score": 100.0}}
        score, _ = score_model_for_role(m, "worker_coder", hw, evidence=ev)
        self.assertEqual(score, 0)  # hard gate vince su evidence

    def test_score_clampato_a_100(self):
        """Un modello con score base 95 + evidence +40 → 135 → clamp 100."""
        m = _fake_model("qwen2.5-coder:1.5b", size_gb=1.5, family="qwen2",
                        quantization="Q4_K_M")
        m["name"] = "qwen2.5-coder:1.5b"  # in preferred_names → +20
        hw = HARDWARE_NO_GPU
        ev = {"qwen2.5-coder:1.5b": {"pass": 10, "total": 10,
                                     "mean_attempts": 1.0,
                                     "mean_secs": 5.0, "score": 100.0}}
        score, _ = score_model_for_role(m, "worker_coder", hw, evidence=ev)
        # Anche con boost forte, lo score non sfora 100
        self.assertLessEqual(score, 100)
        self.assertGreater(score, 90)  # comunque alto


class TestGetRecommendationsWithEvidence(unittest.TestCase):
    """D. get_recommendations espone _evidence nel dict ritornato."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Patch SUITE_RESULTS_PATH e CONFIG_PATH_DEFAULT per puntare
        # ai file temporanei.
        import CORE.model_selector as ms
        self._orig_results_path = ms.SUITE_RESULTS_PATH
        self._orig_config_default = ms.CONFIG_PATH_DEFAULT

    def tearDown(self):
        import CORE.model_selector as ms
        ms.SUITE_RESULTS_PATH = self._orig_results_path
        ms.CONFIG_PATH_DEFAULT = self._orig_config_default
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_evidence_presente_nel_dict_recs(self):
        # Crea results.json + config.toml in self.tmp
        results = {
            "worker_coder": {
                "T1": {"ok": True, "attempts": 1, "secs": 10, "done": True},
                "T2": {"ok": True, "attempts": 1, "secs": 5, "done": True},
            }
        }
        rp = _make_results_file(self.tmp, results)
        cp = _make_config_file(self.tmp, {"worker_coder": "qwen2.5-coder:3b"})
        # Patch dei path
        import CORE.model_selector as ms
        ms.SUITE_RESULTS_PATH = rp
        ms.CONFIG_PATH_DEFAULT = str(cp)
        # Patch get_ollama_models per restituire il nostro modello finto
        orig_get_models = ms.get_ollama_models
        ms.get_ollama_models = lambda host: [
            _fake_model("qwen2.5-coder:3b", size_gb=1.5, family="qwen2")
        ]
        # Patch get_gpu_info e get_ram_info per hardware deterministico
        orig_gpu = ms.get_gpu_info
        orig_ram = ms.get_ram_info
        ms.get_gpu_info = lambda: {"vram_mb": 0, "vram_gb": 0, "temp_c": 0}
        ms.get_ram_info = lambda: {"ram_mb": 16384, "ram_gb": 16}
        try:
            # Chiama la funzione con i path patchati
            from CORE.model_selector import load_suite_evidence, get_recommendations
            evidence = load_suite_evidence(rp, str(cp))
            self.assertIn("qwen2.5-coder:3b", evidence)
            # get_recommendations chiama load_suite_evidence internamente
            # usando i path di default, ma quelli sono patchati sopra
            recs = get_recommendations(config_path=str(cp))
            self.assertIn("_evidence", recs)
            self.assertIsInstance(recs["_evidence"], dict)
        finally:
            ms.get_ollama_models = orig_get_models
            ms.get_gpu_info = orig_gpu
            ms.get_ram_info = orig_ram

    def test_evidence_assente_dict_vuoto(self):
        # File results.json mancante → _evidence = {} (fail-open)
        import CORE.model_selector as ms
        ms.SUITE_RESULTS_PATH = self.tmp / "non_esiste.json"
        ms.CONFIG_PATH_DEFAULT = str(self.tmp / "non_esiste.toml")
        orig_get_models = ms.get_ollama_models
        ms.get_ollama_models = lambda host: []
        try:
            recs = ms.get_recommendations()
            self.assertEqual(recs["_evidence"], {})
        finally:
            ms.get_ollama_models = orig_get_models


if __name__ == "__main__":
    unittest.main(verbosity=2)
