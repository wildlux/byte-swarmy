"""Test Cycle 64 — Corsia veloce (single-shot) nel Worker.

La corsia veloce riusa il prompt del benchmark "naked" (RAG/DOCS/BENCH.md:
50% primo colpo in ~14s contro 12.5% in ~192s del loop ReAct) per i task
con UN solo file target. La scrittura passa da ToolSet.write_file, quindi
AST scanner, safe path e runtime verifier restano attivi.

Nessun Ollama: ModelClient sostituito da un FakeClient.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.worker import Worker          # noqa: E402
from CORE.tools import ToolSet          # noqa: E402
from CORE.memory import AgentMemory     # noqa: E402


class _L:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass


def _make_worker(tmp_path, responses):
    """Worker con ToolSet reale su tmp e client finto con risposte a coda."""
    tmp_path = Path(tmp_path)

    class FakeClient:
        """Client LLM finto: ritorna le risposte in coda (poi l'ultima)."""

        def __init__(self, resp):
            self.resp = list(resp)
            self.calls = []

        def call(self, model_key, prompt, system=None, max_tokens=None,
                 **kw):
            self.calls.append({"prompt": prompt, "max_tokens": max_tokens})
            if len(self.resp) > 1:
                return self.resp.pop(0)
            return self.resp[0]

    cfg = {
        "paths": {
            "project_root": str(tmp_path / "project"),
            "state_dir": str(tmp_path / "state"),
        },
        "security": {
            "enabled": True,
            "max_output_chars": 10_000,
            "max_file_size_write": 2_000_000,
            "max_file_size_bytes": 50_000_000,
            "max_memory_mb": 1536,
            "project_disk_limit_mb": 2048,
        },
        "routing": {"max_file_size_readable": 50_000},
    }
    tools = ToolSet(cfg, _L())
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    mem = AgentMemory("w1", state_dir, None, _L())
    client = FakeClient(responses)
    w = Worker("w1", "worker_coder", tools, mem, client, _L())
    return w, client


def _flcfg(**kw):
    """Config corsia veloce per i test (indipendente da config.toml reale)."""
    base = {"enabled": True, "max_task_chars": 600,
            "max_tokens": 1500, "max_attempts": 2}
    base.update(kw)
    return SimpleNamespace(**base)


TASK = {"title": "aggiorna main.py", "description": "aggiungi funzione somma"}


class TestFastLaneTarget(unittest.TestCase):
    """Euristica di elegibilità: UN solo file target, testo breve."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w, _ = _make_worker(self.tmp.name, ["x"])
        self.cfg = _flcfg()

    def tearDown(self):
        self.tmp.cleanup()

    def test_un_solo_file(self):
        t = {"title": "crea utils.py", "description": "aggiungi funzione somma"}
        self.assertEqual(self.w._fast_lane_target(t, self.cfg), "utils.py")

    def test_path_con_cartella(self):
        t = {"title": "aggiorna core/processor.py",
             "description": "gestisci edge case"}
        self.assertEqual(self.w._fast_lane_target(t, self.cfg),
                         "core/processor.py")

    def test_chiave_file_esplicita(self):
        t = {"title": "applica il refactoring", "description": "",
             "file": "validator.py"}
        self.assertEqual(self.w._fast_lane_target(t, self.cfg), "validator.py")

    def test_chiave_file_autorevole_su_varianti_nel_testo(self):
        """🆕 Cycle 66: 'file' esplicito + varianti nel testo (es. il task
        del benchmark con 'utils.py' nel titolo e 'bench_target/utils.py'
        nella descrizione) → NON è multi-file: la chiave vince."""
        t = {"title": "Aggiungi type hints a utils.py",
             "description": "In bench_target/utils.py, aggiungi type hints.",
             "file": "utils.py"}
        self.assertEqual(self.w._fast_lane_target(t, self.cfg), "utils.py")

    def test_chiave_file_traversal_no(self):
        t = {"title": "crea", "description": "", "file": "../evil.py"}
        self.assertIsNone(self.w._fast_lane_target(t, self.cfg))

    def test_chiave_file_vuota_fallback_testo(self):
        t = {"title": "crea utils.py", "description": "", "file": "  "}
        self.assertEqual(self.w._fast_lane_target(t, self.cfg), "utils.py")

    def test_due_file_no(self):
        t = {"title": "collega main.py e utils.py", "description": ""}
        self.assertIsNone(self.w._fast_lane_target(t, self.cfg))

    def test_nessun_file_no(self):
        t = {"title": "migliora l'architettura del progetto",
             "description": "riorganizza i moduli"}
        self.assertIsNone(self.w._fast_lane_target(t, self.cfg))

    def test_testo_troppo_lungo_no(self):
        t = {"title": "main.py", "description": "x" * 700}
        self.assertIsNone(self.w._fast_lane_target(t, self.cfg))

    def test_path_traversal_no(self):
        # "../evil.py" → il match della regex è "/evil.py" (assoluto),
        # scartato dal filtro → None → corsia classica (comportamento
        # conservativo; safe_project_path resterebbe comunque la difesa).
        t = {"title": "crea file", "description": "../evil.py scrivilo"}
        self.assertIsNone(self.w._fast_lane_target(t, self.cfg))


class TestFastLaneExecute(unittest.TestCase):
    """Esecuzione single-shot con ToolSet reale (difese deterministiche)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = _flcfg()

    def tearDown(self):
        self.tmp.cleanup()

    def test_successo_primo_colpo(self):
        code = "def somma(a, b):\n    return a + b\n"
        w, client = _make_worker(self.tmp.name, [code])
        res = w._execute_fast_lane(TASK, "main.py", self.cfg)
        self.assertTrue(res.startswith("File scritto in corsia veloce"))
        self.assertIn("tentativi: 1", res)
        written = (Path(self.tmp.name) / "project" / "main.py").read_text()
        self.assertEqual(written, code)
        # Il prompt è la variante naked: struttura FILE/TASK/DESCRIZIONE
        p = client.calls[0]["prompt"]
        self.assertIn("FILE: main.py", p)
        self.assertIn("NUOVO CONTENUTO:", p)
        # Le difese non si disattivano: niente retry inutili
        self.assertEqual(len(client.calls), 1)

    def test_retry_su_errore_sintassi(self):
        bad = "def somma(a, b\n    return a + b\n"   # SyntaxError
        good = "def somma(a, b):\n    return a + b\n"
        w, client = _make_worker(self.tmp.name, [bad, good])
        res = w._execute_fast_lane(TASK, "main.py", self.cfg)
        self.assertTrue(res.startswith("File scritto in corsia veloce"))
        self.assertIn("tentativi: 2", res)
        written = (Path(self.tmp.name) / "project" / "main.py").read_text()
        self.assertEqual(written, good)
        # Il secondo prompt contiene l'errore specifico (non generico)
        self.assertIn("ERRORE", client.calls[1]["prompt"])

    def test_fallimento_dopo_tutti_i_tentativi(self):
        bad = "def rotta(a, b\n    return a + b\n"
        w, client = _make_worker(self.tmp.name, [bad, bad])
        res = w._execute_fast_lane(TASK, "main.py", self.cfg)
        self.assertTrue(res.startswith("ERROR: corsia veloce fallita"))
        # last_code popolato per l'eventuale correction loop
        self.assertEqual(w.last_code, bad)
        # 2 tentativi (non 3, non 10: nessun loop)
        self.assertEqual(len(client.calls), 2)

    def test_errore_llm_poi_successo(self):
        good = "def somma(a, b):\n    return a + b\n"

        class FlakyClient:
            def __init__(self):
                self.calls = []
                self.n = 0

            def call(self, model_key, prompt, system=None, max_tokens=None, **kw):
                self.calls.append(prompt)
                self.n += 1
                if self.n == 1:
                    raise RuntimeError("ollama giù")
                return good

        cfg = {
            "paths": {"project_root": str(Path(self.tmp.name) / "project"),
                      "state_dir": str(Path(self.tmp.name) / "state")},
            "security": {"enabled": True, "max_output_chars": 10_000,
                         "max_file_size_write": 2_000_000,
                         "max_file_size_bytes": 50_000_000,
                         "max_memory_mb": 1536, "project_disk_limit_mb": 2048},
            "routing": {"max_file_size_readable": 50_000},
        }
        tools = ToolSet(cfg, _L())
        state_dir = Path(self.tmp.name) / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        mem = AgentMemory("w1", state_dir, None, _L())
        flaky = FlakyClient()
        w = Worker("w1", "worker_coder", tools, mem, flaky, _L())
        res = w._execute_fast_lane(TASK, "main.py", self.cfg)
        self.assertTrue(res.startswith("File scritto in corsia veloce"))
        self.assertIn("tentativi: 2", res)

    def test_codice_vietato_bloccato_da_ast_scanner(self):
        """Le difese restano attive: contenuto pericoloso → rifiuto → retry
        → se anche il retry è pericoloso, fallimento pulito (niente write)."""
        evil = "import os\nos.system('rm -rf /')\n"
        w, client = _make_worker(self.tmp.name, [evil, evil])
        res = w._execute_fast_lane(TASK, "main.py", self.cfg)
        self.assertTrue(res.startswith("ERROR"))
        target = Path(self.tmp.name) / "project" / "main.py"
        self.assertFalse(target.exists())  # mai scritto

    def test_ultimo_colpo_restituito_se_una_sola_risposta(self):
        """FakeClient con una sola risposta: entrambi i tentativi la usano."""
        good = "def somma(a, b):\n    return a + b\n"
        w, client = _make_worker(self.tmp.name, [good])
        res = w._execute_fast_lane(TASK, "main.py", self.cfg)
        self.assertTrue(res.startswith("File scritto in corsia veloce"))
        self.assertEqual(len(client.calls), 1)


class TestFastLaneConfig(unittest.TestCase):
    """Config: fail-open e default."""

    def test_cfg_fail_open(self):
        # _fast_lane_cfg non deve mai esplodere (anche con CWD strano)
        w, _ = _make_worker(tempfile.mkdtemp(), ["x"])
        cfg = w._fast_lane_cfg()
        self.assertTrue(hasattr(cfg, "enabled"))

    def test_max_attempts_minimo_1(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            w, client = _make_worker(tmp.name, ["def x()\n"])
            cfg = _flcfg(max_attempts=0)
            res = w._execute_fast_lane(TASK, "main.py", cfg)
            self.assertTrue(res.startswith("ERROR"))
            self.assertEqual(len(client.calls), 1)  # max(1, 0) → 1 tentativo
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
