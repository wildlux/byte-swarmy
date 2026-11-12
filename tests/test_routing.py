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
  E. M4 routing termico — _thermal_blocked cablato in _route_decide:
     in zona pausa (CPU ≥75 °C, GPU ≥80 °C) l'heavy NON parte
  F. M6 signature cache di code_map.rebuild — no-op se il progetto
     non è cambiato dall'ultima chiamata (TTL 5 s)
  G. M7 isteresi persistente su disco — il riavvio del processo
     non perde lo sticky (max 30 min di età)
  H. M9 routing anche in ReAct — Worker._route_model_key() decide
     il model_key del loop ReAct come run_direct, con fail-open e
     determinismo per client finti

Tutti i test sono SENZA LLM: progetti temporanei + client finti.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
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
import CORE.routing as _routing_mod  # noqa: E402
import CORE.code_map as _code_map_mod  # noqa: E402

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


# ── M4: routing termico ────────────────────────────────────────────────
class TestThermalRouting(unittest.TestCase):
    """E. _thermal_blocked cablato in _route_decide — in zona pausa
    l'heavy NON parte (lezione 4B della suite: modello grande muore
    di throttling, piccolo regge)."""

    def setUp(self):
        reset_hysteresis()
        # Salva l'originale per ripristinarlo in tearDown.
        self._orig_blocked = _routing_mod._thermal_blocked

    def tearDown(self):
        reset_hysteresis()
        _routing_mod._thermal_blocked = self._orig_blocked

    def _mock_thermal(self, reason: str) -> None:
        """Sostituisce _thermal_blocked con uno stub che ritorna `reason`."""
        _routing_mod._thermal_blocked = lambda: reason

    def test_alta_con_block_termico_resta_base(self):
        self._mock_thermal(
            "termico: cpu 80°C gpu 0°C ≥ soglia → heavy evitato")
        key, lv, why = route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(key, BASE)
        self.assertEqual(lv, "alta")  # il livello è alto, ma...
        self.assertIn("termico", why)
        self.assertIn("heavy evitato", why)

    def test_alta_senza_block_termico_va_heavy(self):
        self._mock_thermal("")
        key, lv, why = route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(key, "worker_granite")
        self.assertEqual(lv, "alta")
        self.assertNotIn("termico", why)

    def test_bassa_ignora_termico(self):
        # Task basso non fa decisione heavy: il gate termico non
        # appare nella motivazione (resta base a prescindere).
        self._mock_thermal("termico: cpu 90°C")
        key, lv, why = route_model_key(TASK_BANALE, "", CFG, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(key, BASE)
        self.assertEqual(lv, "bassa")
        self.assertNotIn("termico", why)

    def test_lettura_termica_fallisce_fail_open(self):
        # Se _thermal_blocked solleva, il routing NON crasha: il
        # try/except in _route_decide lo mangia → fail-open, l'heavy
        # parte comunque (la guardia termica resta affidata al
        # gatekeeper del loop, che ha la sua isteresi).
        def boom() -> str:
            raise RuntimeError("sensori morti")
        _routing_mod._thermal_blocked = boom
        key, lv, _why = route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                                          {GRANITE_NAME})
        self.assertEqual(key, "worker_granite")  # fail-open → heavy
        self.assertEqual(lv, "alta")

    def test_block_termico_dopo_heavy_non_installato(self):
        # Ordine: heavy NON installato ha la precedenza (fail-open
        # più restrittivo). Con heavy installato + blocco termico →
        # base per motivi termici (NON per "NON installato").
        self._mock_thermal("termico: heavy evitato")
        key, lv, why = route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(key, BASE)
        self.assertIn("termico", why)
        # Il "NON installato" appare SOLO quando heavy manca davvero;
        # qui heavy è installato, il fallback è termico → la frase
        # specifica "NON installato" non deve comparire nei bits.
        # (Il head neutra dice solo "heavy non usato".)
        # Cerchiamo la frase esatta del fallback NON-installato:
        self.assertNotIn("NON installato: fallback", why)


# ── M6: signature cache di code_map.rebuild ───────────────────────────
class TestCodeMapSignatureCache(unittest.TestCase):
    """F. Cache di signature (file_count, max_mtime) con TTL 5 s:
    se il progetto non è cambiato, rebuild è no-op."""

    def setUp(self):
        _code_map_mod.reset_rebuild_cache()
        self.proj = Path(tempfile.mkdtemp())
        (self.proj / "a.py").write_text(
            "def f():\n    return 1\n", encoding="utf-8")

    def tearDown(self):
        _code_map_mod.reset_rebuild_cache()
        shutil.rmtree(self.proj, ignore_errors=True)

    def test_seconda_chiamata_ritorna_stats_in_cache(self):
        s1 = _code_map_mod.rebuild(self.proj)
        cache_key = str(self.proj.resolve())
        self.assertIn(cache_key, _code_map_mod._BUILD_CACHE)
        s2 = _code_map_mod.rebuild(self.proj)
        self.assertEqual(s1, s2)  # identiche (cache hit)

    def test_nuovo_file_invalida_signature(self):
        _code_map_mod.rebuild(self.proj)
        # Aggiunge un file: signature cambia (count +1)
        (self.proj / "b.py").write_text(
            "def g():\n    return 2\n", encoding="utf-8")
        # Importante: usa force=False — la cache deve accorgersi
        # del cambio signature e rebuildare per davvero.
        # Per evitare il TTL fresh, azzeriamo il ts della cache:
        cache_key = str(self.proj.resolve())
        if cache_key in _code_map_mod._BUILD_CACHE:
            sig, stats, _ts = _code_map_mod._BUILD_CACHE[cache_key]
            _code_map_mod._BUILD_CACHE[cache_key] = (sig, stats, 0.0)
        s = _code_map_mod.rebuild(self.proj)
        self.assertEqual(s["files"], 2)
        # symbol count deve essere cresciuto (g in più di f)
        self.assertGreater(s["symbols"], 1)

    def test_force_salta_la_cache(self):
        _code_map_mod.rebuild(self.proj)
        cache_key = str(self.proj.resolve())
        orig_ts = _code_map_mod._BUILD_CACHE[cache_key][2]
        time.sleep(0.02)
        # force=True: anche con signature uguale, deve ripassare
        # dal branch SQL e aggiornare il ts della cache.
        _code_map_mod.rebuild(self.proj, force=True)
        new_ts = _code_map_mod._BUILD_CACHE[cache_key][2]
        self.assertGreater(new_ts, orig_ts)

    def test_ttl_scaduto_ricalcola(self):
        _code_map_mod.rebuild(self.proj)
        cache_key = str(self.proj.resolve())
        # Forza il ts della cache a 100 s fa (oltre TTL di 5 s)
        sig, stats, _ts = _code_map_mod._BUILD_CACHE[cache_key]
        _code_map_mod._BUILD_CACHE[cache_key] = (sig, stats, time.time() - 100)
        # Anche con signature uguale, il TTL scaduto deve far ripassare
        # dal rebuild reale (verifico che il ts si aggiorni).
        _code_map_mod.rebuild(self.proj)
        new_ts = _code_map_mod._BUILD_CACHE[cache_key][2]
        self.assertGreater(new_ts, time.time() - 10)

    def test_reset_cache_pulisce(self):
        _code_map_mod.rebuild(self.proj)
        self.assertTrue(len(_code_map_mod._BUILD_CACHE) >= 1)
        _code_map_mod.reset_rebuild_cache()
        self.assertEqual(len(_code_map_mod._BUILD_CACHE), 0)


# ── M7: isteresi persistente su disco ────────────────────────────────
class TestPersistentHysteresis(unittest.TestCase):
    """G. Lo sticky heavy sopravvive al riavvio del processo (entro
    STICKY_MAX_AGE_S). File corrotto/assente → fail-open da False."""

    def setUp(self):
        # Reindirizza _HYST_FILE a un tempdir: i test non dipendono
        # dal cwd e non inquinano la state/ reale del progetto.
        self._orig_file = _routing_mod._HYST_FILE
        self.tmpdir = Path(tempfile.mkdtemp())
        _routing_mod._HYST_FILE = self.tmpdir / "routing_hysteresis.json"
        # Simula processo fresco: memoria azzerata, non ancora caricata
        _routing_mod._HYST = {"heavy": False, "loaded": False}

    def tearDown(self):
        _routing_mod._HYST_FILE = self._orig_file
        _routing_mod._HYST = {"heavy": False, "loaded": False}
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_sticky_salvato_e_letto_da_processo_fresco(self):
        # Processo A: un task ALTA imposta sticky heavy
        _k, lv, _why = route_model_key(TASK_ALTA_KW, "", CFG, BASE,
                                         {GRANITE_NAME})
        self.assertEqual(lv, "alta")
        self.assertTrue((self.tmpdir / "routing_hysteresis.json").exists())
        # Processo B (riavvio): memoria azzerata → _hyst_load legge il file
        _routing_mod._HYST = {"heavy": False, "loaded": False}
        _k, lv, why = route_model_key(TASK_MEDIA, "", CFG, BASE,
                                        {GRANITE_NAME})
        self.assertEqual(lv, "alta")  # isteresi dal disco
        self.assertIn("isteresi", why)

    def test_sticky_scaduto_ignorato(self):
        # Scrive un file vecchio più di STICKY_MAX_AGE_S
        sticky_file = self.tmpdir / "routing_hysteresis.json"
        old_ts = time.time() - _routing_mod.STICKY_MAX_AGE_S - 100
        sticky_file.write_text(json.dumps({"heavy": True, "ts": old_ts}),
                                encoding="utf-8")
        # Processo fresco: il file è troppo vecchio → fail-open da False
        _routing_mod._HYST = {"heavy": False, "loaded": False}
        _k, lv, _why = route_model_key(TASK_MEDIA, "", CFG, BASE,
                                         {GRANITE_NAME})
        self.assertNotEqual(lv, "alta")  # scaduto: non incollato

    def test_file_corrotto_fail_open(self):
        # File con JSON invalido: si parte da False (no crash).
        (self.tmpdir / "routing_hysteresis.json").write_text(
            "NOT-JSON-AT-ALL", encoding="utf-8")
        _routing_mod._HYST = {"heavy": False, "loaded": False}
        _k, lv, _why = route_model_key(TASK_MEDIA, "", CFG, BASE,
                                         {GRANITE_NAME})
        self.assertNotEqual(lv, "alta")

    def test_file_assente_parte_da_false(self):
        # Nessun file: prima chiamata con task MEDIA non diventa heavy
        _k, lv, _why = route_model_key(TASK_MEDIA, "", CFG, BASE,
                                         {GRANITE_NAME})
        self.assertNotEqual(lv, "alta")

    def test_bassa_dopo_alta_resetta_il_file(self):
        # ALTA → BASSA: il file viene aggiornato (heavy=False)
        route_model_key(TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        self.assertTrue((self.tmpdir / "routing_hysteresis.json").exists())
        # Processo B (riavvio): la BASSA deve "resettare" sticky
        _routing_mod._HYST = {"heavy": False, "loaded": False}
        # il file sul disco ha heavy=True; lo leggiamo.
        # Ora processiamo una BASSA: deve scrivere heavy=False sul disco.
        route_model_key(TASK_BANALE, "", CFG, BASE, {GRANITE_NAME})
        data = json.loads(
            (self.tmpdir / "routing_hysteresis.json").read_text())
        self.assertFalse(data["heavy"])


# ── M9: routing anche in ReAct (Worker._route_model_key) ──────────────
class TestWorkerRoutingReAct(unittest.TestCase):
    """H. Worker._route_model_key decide il model_key del loop ReAct
    con lo stesso contratto di run_direct: fail-open per client finti
    (determinismo dei test) e routing attivo per ModelClient reale."""

    def setUp(self):
        reset_hysteresis()
        # Patch temporaneo: solleviamo _route_model_key come metodo
        # statico, e sostituiamo ModelClient con uno stub che fa finta
        # di essere "reale" per il test. Evitiamo di costruire un
        # Worker completo (che servirebbe tools/memory/logger pesanti).
        self._orig_real_check = None

    def tearDown(self):
        reset_hysteresis()

    def _make_route_method(self, is_real: bool, project_root: str = "."):
        """Crea un callable che simula Worker._route_model_key con
        attributi controllati: is_real decide se il routing è attivo,
        project_root serve al code_map. Restituisce (callable, models)."""
        # Simuliamo un ModelClient: ha models_cfg come dict vuoto (per
        # _direct_mode_enabled che non entriamo); is_real controlla il
        # check `isinstance(self.models, ModelClient)`.
        # Per il test usiamo un trucco: monkey-patchiamo
        # CORE.ollama_client.ModelClient con uno stub marker class.
        import CORE.ollama_client as oc

        class FakeModelClient:
            """Stub marker:._route_model_key vede isinstance(ModelClient)
            True perché sostituiamo temporaneamente la classe."""
            pass

        if is_real:
            self._orig_ModelClient = oc.ModelClient
            oc.ModelClient = FakeModelClient
            models = FakeModelClient()
        else:
            self._orig_ModelClient = getattr(oc, "ModelClient", None)
            models = object()  # NON è un ModelClient → routing off

        # Simuliamo un Worker con gli attributi minimi che
        # _route_model_key legge: self.models, self.tools, self.model_key
        # Niente classi inner (Python name scope non vede il param):
        # usiamo una semplice namespace object via SimpleNamespace.
        from types import SimpleNamespace

        class _StubLogger:
            def warning(self, msg): pass
            def info(self, msg): pass

        # Reusiamo il metodo reale di Worker
        from CORE.worker import Worker
        stub_tools = SimpleNamespace(project_root=project_root)
        stub_logger = _StubLogger()

        def make_stub(model_key):
            w = SimpleNamespace(
                model_key=model_key,
                models=models,
                tools=stub_tools,
                log=stub_logger,
                agent_id="test-worker",
            )
            # Binda il metodo reale con l'istanza finta (unbound method
            # di Worker = funzione che riceve self come primo arg)
            w._route_model_key = lambda task: Worker._route_model_key(w, task)
            return w

        return make_stub, models, oc

    def tearDown_oc(self, oc):
        if hasattr(self, "_orig_ModelClient") and self._orig_ModelClient is not None:
            oc.ModelClient = self._orig_ModelClient

    def test_client_finto_routing_off_determinismo(self):
        """Un Worker con client NON-ModelClient (test) deve restituire
        il model_key invariato e route vuota — come run_direct."""
        make_stub, _models, oc = self._make_route_method(is_real=False)
        try:
            w = make_stub(BASE)
            key, level, route = w._route_model_key(
                {"title": TASK_ALTA_KW, "description": ""})
            self.assertEqual(key, BASE)
            self.assertEqual(route, "")  # nessuna decisione registrata
            self.assertEqual(level, "")  # routing off
        finally:
            self.tearDown_oc(oc)

    def test_client_reale_alta_va_heavy(self):
        """Un Worker con ModelClient reale + task ALTA + heavy installato
        deve routare verso l'heavy (worker_granite)."""
        # Patch mk.installed_names per simulare heavy installato
        import CORE.model_knowledge as mk
        orig_installed = getattr(mk, "installed_names", None)
        mk.installed_names = lambda: {GRANITE_NAME}
        # Patch load_config per restituire il nostro CFG
        import CORE.orchestrator as orch
        orig_load = getattr(orch, "load_config", None)
        orch.load_config = lambda: CFG
        try:
            make_stub, _models, oc = self._make_route_method(is_real=True)
            w = make_stub(BASE)
            key, level, route = w._route_model_key(
                {"title": TASK_ALTA_KW, "description": ""})
            self.assertEqual(key, "worker_granite")
            self.assertEqual(level, "alta")
            self.assertIn("complessità alta", route)
            self.assertIn("worker_granite", route)
        finally:
            self.tearDown_oc(oc)
            if orig_installed is not None:
                mk.installed_names = orig_installed
            if orig_load is not None:
                orch.load_config = orig_load

    def test_client_reale_bassa_resta_base(self):
        """Un Worker con ModelClient reale + task BASSA resta sul base."""
        import CORE.model_knowledge as mk
        orig_installed = getattr(mk, "installed_names", None)
        mk.installed_names = lambda: {GRANITE_NAME}
        import CORE.orchestrator as orch
        orig_load = getattr(orch, "load_config", None)
        orch.load_config = lambda: CFG
        try:
            make_stub, _models, oc = self._make_route_method(is_real=True)
            w = make_stub(BASE)
            key, level, route = w._route_model_key(
                {"title": TASK_BANALE, "description": ""})
            self.assertEqual(key, BASE)
            self.assertEqual(level, "bassa")
            self.assertIn("complessità bassa", route)
        finally:
            self.tearDown_oc(oc)
            if orig_installed is not None:
                mk.installed_names = orig_installed
            if orig_load is not None:
                orch.load_config = orig_load

    def test_fail_open_se_routing_solleva(self):
        """Se route_model_key solleva, _route_model_key deve restituire
        il model_key base + level/route vuoti (fail-open, mai crash)."""
        orig_route = _routing_mod.route_model_key
        def boom(*a, **kw):
            raise RuntimeError("simulato")
        _routing_mod.route_model_key = boom
        try:
            make_stub, _models, oc = self._make_route_method(is_real=True)
            w = make_stub(BASE)
            key, level, route = w._route_model_key(
                {"title": TASK_ALTA_KW, "description": ""})
            self.assertEqual(key, BASE)
            self.assertEqual(level, "")
            self.assertEqual(route, "")
        finally:
            _routing_mod.route_model_key = orig_route
            self.tearDown_oc(oc)

    def test_routing_decisione_registrata_in_memoria(self):
        """Verifica indiretta: il routing è attivo quando il Worker
        chiama _route_model_key con ModelClient reale. L'evento viene
        aggiunto in memoria SOLO se route_reason non è vuoto."""
        import CORE.model_knowledge as mk
        orig_installed = getattr(mk, "installed_names", None)
        mk.installed_names = lambda: {GRANITE_NAME}
        import CORE.orchestrator as orch
        orig_load = getattr(orch, "load_config", None)
        orch.load_config = lambda: CFG
        try:
            make_stub, _models, oc = self._make_route_method(is_real=True)
            w = make_stub(BASE)
            # Verifichiamo che con ALTA, route_reason è popolato
            # (l'evento in memoria lo fa il caller, non il metodo,
            # ma il metodo ritorna la stringa per il caller).
            key, level, route = w._route_model_key(
                {"title": TASK_ALTA_KW, "description": ""})
            self.assertTrue(route)  # non vuoto = caller registra l'evento
        finally:
            self.tearDown_oc(oc)
            if orig_installed is not None:
                mk.installed_names = orig_installed
            if orig_load is not None:
                orch.load_config = orig_load


if __name__ == "__main__":
    unittest.main(verbosity=2)
