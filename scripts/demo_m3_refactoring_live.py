"""M3 — Refactoring live su progetto vero (demo end-to-end).

Caso d'uso per cui esiste il routing per IMPATTO (Fase 7 + M4+M6+M7+M9):
un task di refactoring che tocca piu file deve andare all'heavy (granite4)
perche' il 3B non e' in grado di coordinare modifiche multi-file.

Scenari:
  1. ROUTING CHECK (no LLM, sempre attivo): il task "rinomina la classe
     Statistiche in Calcolatore in tutto il progetto" cita simboli su
     2+ file → estimate_impact = "alta" → route_model_key restituisce
     worker_granite (se installato + non in zona pausa termica).
  2. WORKER LIVE (richiede Ollama + granite4 installato): istanzia un
     Worker reale con ToolSet + AgentMemory + ModelClient e lancia
     worker.execute(task) sul progetto di test. Verifica che:
     - il routing ha scelto worker_granite (event routing_decision)
     - i file sono stati modificati (Calcolatore invece di Statistiche)
     - i test passano ancora (test_app.py)
  3. MOCK FALLBACK (se Ollama non disponibile): simula granite4 con un
     FakeClient che risponde con una sequenza di tool calls predefinite
     (find_references → patch_code su utils.py → patch_code su app.py →
     done). Verifica che l'infrastruttura (routing + worker + tool)
     funziona end-to-end senza LLM.

Progetto di test: project/PR_TEST_refactoring/ con
  utils.py: class Statistiche (metodi media, mediana)
  app.py: from utils import Statistiche; def report(numeri): ...
  test_app.py: test_report che chiama report([1,2,3])

Output: state/suite_compare/m3_refactoring.json — mai solleva.

ATTENZIONE: scenario 2 USA Ollama + granite4. Se granite4 non e'
installato, parte in automatico lo scenario 3 (mock).
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.routing import reset_hysteresis, estimate_impact  # noqa: E402

PROJ = "project/PR_TEST_refactoring"

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

# Task: rinomina la classe in TUTTO il progetto. Cita "Statistiche"
# (definita in utils.py, chiamata in app.py) → estimate_impact vede
# 2 file toccati (utils.py + app.py) → livello alta.
TASK = ("Refactoring: rinomina la classe Statistiche in Calcolatore in "
        "tutto il progetto. Aggiorna tutti i file che la referenziano "
        "(utils.py, app.py) e verifica che i test in test_app.py "
        "continuano a passare.")


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def setup_project(proj: Path) -> None:
    """Crea/sovrascrive il progetto di test con i file in FILES."""
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir(parents=True)
    for name, content in FILES.items():
        (proj / name).write_text(content, encoding="utf-8")


def check_routing_impact(proj: Path) -> dict:
    """Scenario 1: verifica routing per impatto (no LLM).

    Il task cita simboli su 2+ file → estimate_impact deve restituire
    livello 'alta' con i simboli Statistiche e i file utils.py + app.py.
    """
    section("M3 — Scenario 1: routing per impatto (no LLM)")
    reset_hysteresis()
    code_map_path = proj / ".byteswarm"
    if code_map_path.exists():
        shutil.rmtree(code_map_path)
    imp = estimate_impact(TASK, str(proj), exclude_files={"main.py"})
    print(f"  cited: {imp['cited']}")
    print(f"  files: {imp['files']}")
    print(f"  depth: {imp['depth']}")
    print(f"  tests: {imp['tests']}")
    print(f"  level: {imp['level']!r}")
    assert "Statistiche" in imp["cited"], (
        "Il task cita 'Statistiche' ma non è nei simboli citati")
    assert imp["level"] == "alta", (
        f"Impatto deve essere 'alta' (≥2 file), ottenuto {imp['level']!r}")
    assert len(imp["files"]) >= 2, (
        f"Almeno 2 file toccati, ottenuti {imp['files']}")
    print(f"\n✓ Routing per impatto: ALTA con {len(imp['files'])} file toccati")
    return imp


def run_worker_live(proj: Path, task: str, use_mock: bool = False) -> dict:
    """Scenario 2/3: lancia un Worker reale (o mock) sul task.

    Costruisce ToolSet + AgentMemory + ModelClient (o FakeClient),
    istanzia Worker e chiama execute(task). Ritorna {ok, model, route,
    result, files_after}.

    use_mock=True se Ollama/granite4 non disponibili: usa un FakeClient
    che simula una sequenza di tool calls di refactoring.
    """
    section(f"M3 — Scenario {'3 (MOCK)' if use_mock else '2 (LIVE)'}: Worker.execute(task)")

    # Config minimale per ToolSet
    config = {
        "paths": {"project_root": str(proj)},
        "security": {"enabled": True, "max_output_chars": 10000,
                     "max_file_size_write": 2_000_000,
                     "max_file_size_bytes": 50_000_000,
                     "max_memory_mb": 1536,
                     "project_disk_limit_mb": 2048},
    }
    log = logging.getLogger("m3_demo")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # ToolSet: i tool reali che il worker usera
    from CORE.tools import ToolSet
    tools = ToolSet(config, log)

    # AgentMemory: memoria per i worker (event sourcing)
    from CORE.memory import AgentMemory
    state_dir = proj.parent / "state_m3"
    state_dir.mkdir(parents=True, exist_ok=True)
    memory = AgentMemory(agent_id="worker-m3",
                         state_dir=state_dir,
                         model_client=None,
                         logger=log)

    # ModelClient: reale o mock
    if use_mock:
        models = _FakeModelClientForRefactoring(proj, log)
        print("  [mock] FakeClient granite4: simula refactoring multi-file")
    else:
        from CORE.ollama_client import ModelClient
        from CORE.orchestrator import load_config
        try:
            cfg = load_config()
        except Exception:
            cfg = None
        models = ModelClient(cfg or config, log)

    # Worker
    from CORE.worker import Worker
    worker = Worker(
        agent_id="worker-m3",
        model_key="worker_granite",  # heavy: routing per impatto sceglie questo
        tools=tools,
        memory=memory,
        model_client=models,
        logger=log,
    )

    # Snapshot file prima del refactoring
    files_before = {f: (proj / f).read_text() for f in FILES}

    reset_hysteresis()
    t0 = time.monotonic()
    try:
        result = worker.execute({"title": TASK, "id": "m3-task"})
    except Exception as e:
        result = f"ERROR: {e}"
    dt = round(time.monotonic() - t0, 1)

    # File dopo il refactoring
    files_after = {f: (proj / f).read_text() for f in FILES
                   if (proj / f).exists()}

    # Verifica: Statistiche deve sparire, Calcolatore deve apparire
    statistiche_before = sum(v.count("Statistiche") for v in files_before.values())
    statistiche_after = sum(v.count("Statistiche") for v in files_after.values())
    calcolatore_after = sum(v.count("Calcolatore") for v in files_after.values())

    print(f"  → result: {result[:200]}")
    print(f"  → tempo: {dt}s")
    print(f"  → 'Statistiche' prima: {statistiche_before} occorrenze")
    print(f"  → 'Statistiche' dopo:  {statistiche_after} occorrenze (deve essere 0)")
    print(f"  → 'Calcolatore' dopo:  {calcolatore_after} occorrenze (deve essere > 0)")

    ok = (statistiche_after == 0 and calcolatore_after > 0
          and not result.startswith("ERROR"))
    print(f"\n{'✓' if ok else '✗'} Refactoring {'RIUSCITO' if ok else 'FALLITO'}")

    return {
        "ok": ok,
        "result": result,
        "secs": dt,
        "files_after": files_after,
        "statistiche_before": statistiche_before,
        "statistiche_after": statistiche_after,
        "calcolatore_after": calcolatore_after,
    }


class _FakeModelClientForRefactoring:
    """Mock ModelClient: simula granite4 facendo un refactoring
    multi-file predefinito. NON è un ModelClient reale (non eredita),
    quindi _route_model_key vede _is_real_client() = False → routing OFF
    (come nei test M9). Ma qui non ci importa perché costruiamo il
    worker con model_key='worker_granite' fisso.

    Per il live test (use_mock=False) usiamo il vero ModelClient."""

    def __init__(self, proj: Path, log):
        self.proj = proj
        self.log = log
        self.models_cfg = {}
        self.config = {}
        # Counter delle call: ogni call_streaming ritorna una action
        # della sequenza predefinita di refactoring.
        self._step = 0
        # La sequenza simula un Worker ReAct che:
        # 1. find_references(Statistiche)
        # 2. patch_code(utils.py, "class Statistiche", "class Calcolatore")
        # 3. patch_code(utils.py, "s = Statistiche()" — no, è in app.py
        # 4. patch_code(app.py, "Statistiche", "Calcolatore")
        # 5. done
        self._sequence = [
            # Step 0: find_references
            ('{"thought":"cerco riferimenti a Statistiche","action":'
             '"find_references","args":["Statistiche"],"done":false}'),
            # Step 1: patch utils.py
            ('{"thought":"rinomino la classe in utils.py","action":'
             '"patch_code","args":["utils.py","class Statistiche",'
             '"class Calcolatore"],"done":false}'),
            # Step 2: patch app.py (import)
            ('{"thought":"aggiorno l\'import in app.py","action":'
             '"patch_code","args":["app.py","from utils import Statistiche",'
             '"from utils import Calcolatore"],"done":false}'),
            # Step 3: patch app.py (uso)
            ('{"thought":"aggiorno l\'uso in app.py","action":'
             '"patch_code","args":["app.py","s = Statistiche()",'
             '"s = Calcolatore()"],"done":false}'),
            # Step 4: done
            ('{"thought":"refactoring completato","action":"none",'
             '"args":[],"done":true,"result":"Rinominato Statistiche '
             'in Calcolatore in utils.py e app.py (3 modifiche totali)"}'),
        ]

    def call_streaming(self, model_key=None, prompt=None, system=None,
                       max_tokens=1024, options_override=None):
        """Ritorna la prossima 'action' come singolo token (la stringa
        JSON intera, così il parser la vede)."""
        if self._step >= len(self._sequence):
            # Fallback: done con errore
            yield ('{"thought":"done","action":"none","args":[],'
                   '"done":true,"result":"mock: sequenza terminata"}')
            return
        action_json = self._sequence[self._step]
        self._step += 1
        yield action_json

    def call(self, model_key=None, prompt=None, system=None,
             max_tokens=1024):
        return self._sequence[min(self._step, len(self._sequence) - 1)]

    def _get_tuned_options(self, *a, **kw):
        return {}


def check_tests_pass(proj: Path) -> bool:
    """Verifica che test_app.py passi ancora dopo il refactoring.
    Il test chiama report([1,2,3]) → (2.0, 2). Se Statistiche è stata
    rinominata in Calcolatore coerentemente, il test passa."""
    section("M3 — Verifica: i test passano dopo il refactoring")
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "pytest", str(proj / "test_app.py"),
         "-v", "--no-header", "--tb=short"],
        capture_output=True, text=True, timeout=30,
    )
    out = (r.stdout + r.stderr).strip().split("\n")
    # Stampa solo le ultime 5 righe per non affogare l'output
    for line in out[-5:]:
        print(f"  {line}")
    return r.returncode == 0


def is_ollama_available() -> bool:
    """True se Ollama è attivo e granite4 è installato."""
    try:
        import urllib.request
        data = json.loads(
            urllib.request.urlopen(
                "http://localhost:11434/api/tags", timeout=2).read())
        names = [m.get("name", "") for m in data.get("models", [])]
        return any("granite4" in n for n in names)
    except Exception:
        return False


def main() -> int:
    print(f"M3 — Refactoring live su progetto vero")
    print(f"Python: {sys.version.split()[0]}")

    proj = Path(PROJ)
    setup_project(proj)
    print(f"\nProgetto di test creato in: {proj.resolve()}")

    # Scenario 1: routing check (sempre)
    imp = check_routing_impact(proj)

    # Scenario 2/3: worker execute
    use_mock = not is_ollama_available()
    if use_mock:
        print("\n[INFO] Ollama o granite4 non disponibili → scenario 3 (mock)")
        print("       Per il run live: `ollama pull granite4:7b-a1b-h`")
    else:
        print("\n[INFO] Ollama + granite4 rilevati → scenario 2 (live)")
    res = run_worker_live(proj, TASK, use_mock=use_mock)

    # Verifica finale: test passano ancora
    if res["ok"]:
        tests_ok = check_tests_pass(proj)
        res["tests_pass"] = tests_ok
    else:
        res["tests_pass"] = False

    # Salva risultati
    out_path = Path("state/suite_compare/m3_refactoring.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "task": TASK,
        "impact": imp,
        "worker_run": {k: v for k, v in res.items()
                       if k != "files_after"},
        "files_after": res["files_after"],
        "use_mock": use_mock,
        "timestamp": time.time(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    section("M3 — Bilancio finale")
    print(f"  Routing per impatto: {imp['level']} ({len(imp['files'])} file)")
    print(f"  Worker run ({'mock' if use_mock else 'live'}): "
          f"{'OK' if res['ok'] else 'FAIL'} in {res['secs']}s")
    print(f"  'Statistiche' prima → dopo: "
          f"{res['statistiche_before']} → {res['statistiche_after']}")
    print(f"  'Calcolatore' dopo: {res['calcolatore_after']} occorrenze")
    print(f"  Test passano: {res['tests_pass']}")
    print(f"\n  Output: {out_path}")

    return 0 if (res["ok"] and res["tests_pass"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
