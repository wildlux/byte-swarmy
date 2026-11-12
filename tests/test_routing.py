"""
test_routing.py — Test unit del routing per complessità (Fasi 6-7).

Copre:
  A. estimate_impact: simboli citati nel task → file toccati, profondità
     BFS a valle, copertura test TRANSITIVA, livello ''/media/alta
  B. Isteresi: media dopo alta resta heavy; bassa resetta; reset manuale
  C. route_model_key: combinazione MAX(keyword, impatto), fallback con
     heavy assente, routing disabilitato, fail-open senza config,
     formato leggibile della decisione (3-tuple)
  D. explain (delega) + run_direct: client finto = routing OFF
     (determinismo dei test), enable_routing=True = decisione nel dict,
     classificazione client reale vs finto

Tutti i test sono SENZA LLM: progetti temporanei + client finti.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.routing import (  # noqa: E402
    estimate_impact,
    explain,
    reset_hysteresis,
    route_model_key,
)
from CORE.skill_executor import _is_real_client, run_direct  # noqa: E402

# Config di prova: stesso schema di CONFIG/config.toml (chiavi reali).
CFG = {
    "complexity_routing": {
        "enabled": True,
        "heavy_model": "worker_granite",
    },
    "models": {
        "worker_coder": {"name": "qwen2.5-coder:3b"},
        "worker_coder_big": {"name": "kirito1/qwen3-coder:4b"},
        "worker_granite": {"name": "granite4:7b-a1b-h"},
    },
}
BASE = "worker_coder"
GRANITE_NAME = "granite4:7b-a1b-h"

TASK_IMPATTO = "usa la classe Statistiche per calcolare la media"
TASK_ISOLATO = "riusa formatta nel nuovo codice"
TASK_BANALE = "stampa ciao mondo"
TASK_ALTA_KW = "task thread con lock e join"
TASK_MEDIA = "crea una classe semplice con json"


def _make_proj() -> Path:
    """Progetto temporaneo con catena di chiamate su 3 file + test.

    utils.Statistiche.media/mediana ← app.report ← test_app.test_report
    formatta (utils) resta un simbolo isolato (nessuno lo chiama).
    """
    proj = Path(tempfile.mkdtemp())
    (proj / "utils.py").write_text(
        "class Statistiche:\n"
        "    def media(self, numeri):\n        return 0\n"
        "    def mediana(self, numeri):\n        return 0\n"
        "def formatta(x):\n    return str(x)\n", encoding="utf-8")
    (proj / "app.py").write_text(
        "from utils import Statistiche\n"
        "def report(numeri):\n"
        "    s = Statistiche()\n"
        "    return s.media(numeri) + s.mediana(numeri)\n",
        encoding="utf-8")
    (proj / "biz.py").write_text(
        "from app import report\n"
        "def pipeline(dati):\n"
        "    return report(dati)\n", encoding="utf-8")
    (proj / "test_app.py").write_text(
        "def test_report():\n    assert report([1]) == 0\n",
        encoding="utf-8")
    return proj


class TestEstimateImpact(unittest.TestCase):
    """A. Impatto dal grafo del code_map."""

    @classmethod
    def setUpClass(cls):
        cls.proj = _make_proj()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.proj, ignore_errors=True)

    def test_simboli_citati_file_toccati_alta(self):
        imp = estimate_impact(TASK_IMPATTO, str(self.proj),
                              exclude_files={"main.py"})
        self.assertIn("Statistiche", imp["cited"])
        self.assertIn("media", imp["cited"])
        self.assertEqual(set(imp["files"]), {"utils.py", "app.py"})
        # BFS: Statistiche → report (app.py) → test_report (test_app.py)
        self.assertEqual(imp["depth"], 2)
        self.assertTrue(imp["tests"])  # copertura test TRANSITIVA
        self.assertEqual(imp["level"], "alta")  # ≥2 file toccati

    def test_simbolo_isolato_media(self):
        imp = estimate_impact(TASK_ISOLATO, str(self.proj),
                              exclude_files={"main.py"})
        self.assertEqual(imp["cited"], ["formatta"])
        self.assertEqual(imp["files"], ["utils.py"])
        self.assertEqual(imp["level"], "media")

    def test_nessuna_citazione_livello_vuoto(self):
        imp = estimate_impact(TASK_BANALE, str(self.proj))
        self.assertEqual(imp["cited"], [])
        self.assertEqual(imp["files"], [])
        self.assertEqual(imp["level"], "")

    def test_exclude_files_esclude_i_simboli(self):
        # Il file target sta per essere riscritto: i SUOI simboli sono
        # rumore → se tutto ciò che è citato vive lì, il livello è ''.
        imp = estimate_impact(TASK_IMPATTO, str(self.proj),
                              exclude_files={"utils.py", "main.py"})
        self.assertEqual(imp["cited"], [])
        self.assertEqual(imp["level"], "")

    def test_progetto_vuoto_fail_open(self):
        vuoto = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, vuoto, ignore_errors=True)
        imp = estimate_impact(TASK_IMPATTO, str(vuoto))
        self.assertEqual(imp["level"], "")
        # Anche un percorso inesistente non deve sollevare.
        imp2 = estimate_impact(TASK_IMPATTO, str(vuoto / "no_esiste"))
        self.assertEqual(imp2["level"], "")


class TestHysteresis(unittest.TestCase):
    """B. Isteresi sticky tra task consecutivi."""

    def setUp(self):
        reset_hysteresis()

    def tearDown(self):
        reset_hysteresis()

    def test_media_dopo_alta_resta_heavy(self):
        _k, lv, _why = route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                                       {GRANITE_NAME})
        self.assertEqual(lv, "alta")
        _k, lv, why = route_model_key(TASK_MEDIA, "", CFG, BASE,
                                      {GRANITE_NAME})
        self.assertEqual(lv, "alta")
        self.assertIn("isteresi", why)

    def test_bassa_resetta(self):
        route_model_key(TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        _k, lv, why = route_model_key(TASK_BANALE, "", CFG, BASE,
                                      {GRANITE_NAME})
        self.assertEqual(lv, "bassa")
        self.assertNotIn("isteresi", why)

    def test_reset_hysteresis(self):
        route_model_key(TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        reset_hysteresis()
        _k, lv, _why = route_model_key(TASK_MEDIA, "", CFG, BASE,
                                       {GRANITE_NAME})
        self.assertNotEqual(lv, "alta")


class TestRouteModelKey(unittest.TestCase):
    """C. Decisione (key, level, motivo leggibile)."""

    @classmethod
    def setUpClass(cls):
        cls.proj = _make_proj()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.proj, ignore_errors=True)

    def setUp(self):
        reset_hysteresis()

    def tearDown(self):
        reset_hysteresis()

    def test_banale_al_base(self):
        key, lv, _why = route_model_key(TASK_BANALE, "", CFG, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(key, BASE)
        self.assertEqual(lv, "bassa")

    def test_keyword_alta_verso_heavy(self):
        key, lv, why = route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                                       {GRANITE_NAME})
        self.assertEqual(key, "worker_granite")
        self.assertEqual(lv, "alta")
        self.assertIn("complessità alta → worker_granite", why)

    def test_impatto_alza_il_livello(self):
        key, lv, why = route_model_key(
            TASK_IMPATTO, "", CFG, BASE, {GRANITE_NAME},
            project_root=str(self.proj), exclude_files={"main.py"})
        self.assertEqual(key, "worker_granite")
        self.assertIn("impatto alta", why)
        self.assertIn("simboli citati", why)

    def test_heavy_non_installato_fallback(self):
        key, lv, why = route_model_key(TASK_ALTA_KW, "", CFG, BASE, set())
        self.assertEqual(key, BASE)
        self.assertEqual(lv, "alta")
        self.assertIn("NON installato", why)
        self.assertIn("fallback", why)

    def test_routing_disabilitato(self):
        cfg_off = {"complexity_routing": {"enabled": False,
                                          "heavy_model": "worker_granite"},
                   "models": CFG["models"]}
        key, _lv, why = route_model_key(TASK_ALTA_KW, "", cfg_off, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(key, BASE)
        self.assertIn("routing off", why)

    def test_senza_config_fail_open(self):
        key, lv, _why = route_model_key(TASK_ALTA_KW, "", None, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(key, BASE)
        self.assertEqual(lv, "alta")

    def test_senza_sezione_routing_fail_open(self):
        key, _lv, _why = route_model_key(TASK_ALTA_KW, "", {"models": {}},
                                         BASE, {GRANITE_NAME})
        self.assertEqual(key, BASE)


class TestExplainAndRunDirect(unittest.TestCase):
    """D. explain (delega) + integrazione run_direct."""

    def setUp(self):
        reset_hysteresis()
        self.proj = Path(tempfile.mkdtemp())
        (self.proj / "utils.py").write_text(
            "class Helper:\n    def aiuto(self):\n        pass\n",
            encoding="utf-8")

    def tearDown(self):
        reset_hysteresis()
        shutil.rmtree(self.proj, ignore_errors=True)

    def test_explain_delega_alla_decisione(self):
        self.assertEqual(
            explain(TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME}),
            route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                            {GRANITE_NAME})[2])

    def test_client_finto_routing_off(self):
        calls = []

        class FakeClient:
            def call(self, model_key, prompt, system=None):
                calls.append(model_key)
                return "```python\nprint('SOMMA=42')\n```"

        res = run_direct({"title": "stampa ciao e poi SOMMA=42"},
                         str(self.proj), model_key=BASE,
                         client=FakeClient(), max_retries=1)
        self.assertTrue(res["ok"])
        self.assertEqual(res["model"], BASE)
        self.assertEqual(res["route"], "")  # nessuna decisione registrata
        self.assertEqual(calls, [BASE])

    def test_enable_routing_forzato_decisione_nel_dict(self):
        class OneShotClient:
            def call(self, model_key, prompt, system=None):
                return "```python\nprint('SOMMA=42')\n```"

        res = run_direct({"title": "stampa ciao e poi SOMMA=42"},
                         str(self.proj), model_key=BASE,
                         client=OneShotClient(), max_retries=1,
                         enable_routing=True)
        self.assertTrue(res["ok"])
        self.assertEqual(res["model"], BASE)  # task banale → base
        self.assertIn("complessità bassa → worker_coder", res["route"])

    def test_classificazione_client_reale_vs_finto(self):
        self.assertTrue(_is_real_client(None))  # CLI → routing attivo

        class FakeClient:
            pass

        self.assertFalse(_is_real_client(FakeClient()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
