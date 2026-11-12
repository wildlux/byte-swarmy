"""
test_refactoring_live.py — Test unit per M3 (refactoring live su progetto).

Copre:
  A. Routing per impatto del task di refactoring: il task cita
     simboli su 2+ file → estimate_impact = "alta" → routing sceglie
     worker_granite (se installato + non in zona pausa)
  B. Worker.execute con FakeClient: il loop ReAct usa tool multipli
     (find_references + patch_code × 3) per rifattorizzare il progetto
     end-to-end. Verifica:
     - 'Statistiche' sparisce da tutti i file
     - 'Calcolatore' appare in tutti i file rilevanti
     - il risultato NON inizia con 'ERROR'
     - i test in test_app.py passano ancora (subprocess pytest)
  C. Fail-open: se il FakeClient produce una sequenza sbagliata (es.
     solo find_references, poi done senza patch), il refactoring FALLISCE
     onestamente (Statistiche ancora presente, test falliscono)

Tutti i test sono SENZA Ollama: usano il FakeClient di demo_m3.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.routing import reset_hysteresis, estimate_impact  # noqa: E402


# Stesso progetto di test di scripts/demo_m3_refactoring_live.py
FILES = {
    "utils.py": (
        "class Statistiche:\n"
        "    def media(self, numeri):\n"
        "        return sum(numeri) / len(numeri)\n"
        "\n"
        "    def mediana(self, numeri):\n"
        "        nums = sorted(numeri)\n"
        "        n = len(nums)\n"
        "        mid = n // 2\n"
        "        if n % 2:\n"
        "            return nums[mid]\n"
        "        return (nums[mid - 1] + nums[mid]) / 2\n"),
    "app.py": (
        "from utils import Statistiche\n"
        "\n"
        "\n"
        "def report(numeri):\n"
        "    s = Statistiche()\n"
        "    return s.media(numeri), s.mediana(numeri)\n"),
    "test_app.py": (
        "from app import report\n"
        "\n"
        "\n"
        "def test_report():\n"
        "    assert report([1, 2, 3]) == (2.0, 2)\n"),
}

TASK = ("Refactoring: rinomina la classe Statistiche in Calcolatore in "
        "tutto il progetto. Aggiorna tutti i file che la referenziano "
        "(utils.py, app.py) e verifica che i test in test_app.py "
        "continuano a passare.")


def _setup_proj(tmp: Path) -> Path:
    proj = tmp / "PR_TEST_refactoring"
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir(parents=True)
    for name, content in FILES.items():
        (proj / name).write_text(content, encoding="utf-8")
    return proj


class _FakeModelClientRefactoring:
    """Mock ModelClient: simula granite4 con sequenza di tool calls
    di refactoring predefinita (stessa di demo_m3)."""

    def __init__(self, sequence=None):
        self.models_cfg = {}
        self.config = {}
        self._step = 0
        if sequence is None:
            # Sequenza buona: find_references + 3 patch + done
            self._sequence = [
                ('{"thought":"cerco riferimenti","action":'
                 '"find_references","args":["Statistiche"],"done":false}'),
                ('{"thought":"patch utils.py","action":'
                 '"patch_code","args":["utils.py","class Statistiche",'
                 '"class Calcolatore"],"done":false}'),
                ('{"thought":"patch app.py import","action":'
                 '"patch_code","args":["app.py","from utils import '
                 'Statistiche","from utils import Calcolatore"],'
                 '"done":false}'),
                ('{"thought":"patch app.py uso","action":'
                 '"patch_code","args":["app.py","s = Statistiche()",'
                 '"s = Calcolatore()"],"done":false}'),
                ('{"thought":"fatto","action":"none","args":[],'
                 '"done":true,"result":"refactoring ok"}'),
            ]
        else:
            self._sequence = sequence

    def call_streaming(self, model_key=None, prompt=None, system=None,
                       max_tokens=1024, options_override=None):
        if self._step >= len(self._sequence):
            yield ('{"thought":"done","action":"none","args":[],'
                   '"done":true,"result":"mock: sequenza terminata"}')
            return
        action = self._sequence[self._step]
        self._step += 1
        yield action

    def call(self, model_key=None, prompt=None, system=None,
             max_tokens=1024):
        return self._sequence[min(self._step, len(self._sequence) - 1)]

    def _get_tuned_options(self, *a, **kw):
        return {}


def _run_worker(proj: Path, fake_client) -> tuple[str, dict]:
    """Istanzia Worker con fake_client e lancia execute(TASK).
    Ritorna (result, files_after)."""
    import logging
    log = logging.getLogger("test_m3")
    logging.basicConfig(level=logging.WARNING)  # silenzioso

    config = {
        "paths": {"project_root": str(proj)},
        "security": {"enabled": True, "max_output_chars": 10000,
                     "max_file_size_write": 2_000_000,
                     "max_file_size_bytes": 50_000_000,
                     "max_memory_mb": 1536,
                     "project_disk_limit_mb": 2048},
    }
    from CORE.tools import ToolSet
    tools = ToolSet(config, log)
    from CORE.memory import AgentMemory
    state_dir = proj.parent / "state_m3_test"
    state_dir.mkdir(parents=True, exist_ok=True)
    memory = AgentMemory(agent_id="worker-m3-test",
                         state_dir=state_dir,
                         model_client=None,
                         logger=log)
    from CORE.worker import Worker
    worker = Worker(
        agent_id="worker-m3-test",
        model_key="worker_granite",
        tools=tools,
        memory=memory,
        model_client=fake_client,
        logger=log,
    )
    reset_hysteresis()
    result = worker.execute({"title": TASK, "id": "m3-test"})
    files_after = {f: (proj / f).read_text() for f in FILES
                   if (proj / f).exists()}
    return result, files_after


def _tests_pass(proj: Path) -> bool:
    """True se test_app.py passa con pytest."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(proj / "test_app.py"),
             "-q", "--no-header", "--tb=line"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False


class TestRoutingImpactForRefactoring(unittest.TestCase):
    """A. Il routing per impatto vede il task come 'alta'."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = _setup_proj(self.tmp)
        # Reset code_map cache
        import CORE.code_map as cm
        cm.reset_rebuild_cache()
        reset_hysteresis()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_impact_alta_per_rinomina_classe(self):
        imp = estimate_impact(TASK, str(self.proj),
                              exclude_files={"main.py"})
        self.assertIn("Statistiche", imp["cited"])
        self.assertEqual(imp["level"], "alta")
        self.assertGreaterEqual(len(imp["files"]), 2)

    def test_impact_files_inclusi(self):
        """Il task cita Statistiche, definita in utils.py e chiamata
        in app.py → entrambi i file devono essere in 'files'."""
        imp = estimate_impact(TASK, str(self.proj),
                              exclude_files={"main.py"})
        files = set(imp["files"])
        self.assertIn("utils.py", files)
        self.assertIn("app.py", files)

    def test_impact_tests_coperto(self):
        """Il test_app.py chiama report() che chiama Statistiche →
        la copertura test TRANSITIVA deve essere True."""
        imp = estimate_impact(TASK, str(self.proj),
                              exclude_files={"main.py"})
        self.assertTrue(imp["tests"],
                        "Il test_app.py copre la catena chiamante")


class TestWorkerRefactoringLiveMock(unittest.TestCase):
    """B. Worker.execute con FakeClient fa refactoring multi-file."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = _setup_proj(self.tmp)
        import CORE.code_map as cm
        cm.reset_rebuild_cache()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_refactoring_rinomina_statistiche_in_calcolatore(self):
        """Sequenza buona: find_references + 3 patch + done.
        Aspettato: 0 'Statistiche', 3 'Calcolatore', test passano."""
        fake = _FakeModelClientRefactoring()
        result, files_after = _run_worker(self.proj, fake)
        # Verifica refactoring
        statistiche = sum(v.count("Statistiche") for v in files_after.values())
        calcolatore = sum(v.count("Calcolatore") for v in files_after.values())
        self.assertEqual(statistiche, 0,
                         f"Statistiche deve sparire, trovato {statistiche}")
        self.assertGreater(calcolatore, 0,
                           "Calcolatore deve apparire")
        # Verifica result
        self.assertFalse(result.startswith("ERROR"),
                         f"result non deve essere ERROR: {result[:100]}")
        # Verifica test passano ancora
        self.assertTrue(_tests_pass(self.proj),
                        "test_app.py deve passare dopo il refactoring")

    def test_files_specifici_aggiornati(self):
        """Ogni file deve avere il refactoring corretto."""
        fake = _FakeModelClientRefactoring()
        _, files_after = _run_worker(self.proj, fake)
        # utils.py: class Calcolatore (NON più Statistiche)
        self.assertIn("class Calcolatore", files_after["utils.py"])
        self.assertNotIn("Statistiche", files_after["utils.py"])
        # app.py: import + uso Calcolatore
        self.assertIn("from utils import Calcolatore", files_after["app.py"])
        self.assertIn("Calcolatore()", files_after["app.py"])
        self.assertNotIn("Statistiche", files_after["app.py"])

    def test_result_include_message_di_successo(self):
        fake = _FakeModelClientRefactoring()
        result, _ = _run_worker(self.proj, fake)
        self.assertIn("refactoring", result.lower())


class TestWorkerRefactoringFailOpen(unittest.TestCase):
    """C. Se il Worker produce una sequenza sbagliata, il refactoring
    FALLISCE onestamente (niente falsi positivi)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = _setup_proj(self.tmp)
        import CORE.code_map as cm
        cm.reset_rebuild_cache()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sequenza_troncata_lascia_statistiche(self):
        """Se il FakeClient fa SOLO find_references e poi done (senza
        patch_code), il refactoring non avviene: Statistiche ancora
        presente, test passano ancora (perché niente è cambiato)."""
        # Sequenza sbagliata: solo find_references + done
        bad_sequence = [
            ('{"thought":"cerco","action":'
             '"find_references","args":["Statistiche"],"done":false}'),
            ('{"thought":"fatto","action":"none","args":[],'
             '"done":true,"result":"fatto (ma non ho patchato)"}'),
        ]
        fake = _FakeModelClientRefactoring(sequence=bad_sequence)
        result, files_after = _run_worker(self.proj, fake)
        # Statistiche ancora presente: 0 patch applicate
        statistiche = sum(v.count("Statistiche") for v in files_after.values())
        self.assertGreater(statistiche, 0,
                           "Statistiche deve essere ancora presente")
        # I test passano perché il progetto è invariato
        self.assertTrue(_tests_pass(self.proj),
                        "I test devono passare se niente è cambiato")

    def test_sequenza_con_done_immediato_lavoro_zero(self):
        """Se il Worker dichiara done subito senza chiamare tool,
        il result è 'ok' ma nessun file è stato toccato: il refactoring
        non è avvenuto e l'utente lo vede dal risultato."""
        immediate_done = [
            ('{"thought":"fatto","action":"none","args":[],'
             '"done":true,"result":"refactoring dichiarato senza fare"}'),
        ]
        fake = _FakeModelClientRefactoring(sequence=immediate_done)
        result, files_after = _run_worker(self.proj, fake)
        # I file sono invariati
        for name, content in FILES.items():
            self.assertEqual(files_after[name], content,
                             f"{name} non deve essere modificato")
        # Statistiche ancora presente
        statistiche = sum(v.count("Statistiche") for v in files_after.values())
        self.assertGreater(statistiche, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
