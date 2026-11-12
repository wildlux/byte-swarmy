"""Run live M9 — routing anche in ReAct, senza LLM.

Cosa fa:
  M9 dimostra che Worker._route_model_key() integra lo stesso routing
  di run_direct (complessità MAX(keyword, impatto dal grafo) + isteresi
  M7 + guardia termica M4) nel loop ReAct, non solo in direct mode.

  Scenari:
    1. Worker con client NON-ModelClient (test) → routing OFF, resta base
       (stesso determinismo di run_direct con FakeClient)
    2. Worker con ModelClient "reale" + task ALTA + heavy installato →
       routing verso worker_granite
    3. Worker con ModelClient reale + task BASSA → resta base
    4. Worker con ModelClient reale + task ALTA + heavy NON installato →
       resta base con fallback
    5. Worker con ModelClient reale + termico in zona pausa → resta base
    6. Worker con ModelClient reale + route_model_key che solleva →
       fail-open, resta base senza crash

  Inoltre: progetto temporaneo con simboli per dimostrare che il
  routing considera l'impatto sul grafo del code_map (M9+M7+M4+M6
  insieme come in produzione).

Tutto senza LLM: uso stub di ModelClient e monkey-patch di
route_model_key + model_knowledge.installed_names.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.worker import Worker
import CORE.routing as routing
import CORE.ollama_client as oc
import CORE.model_knowledge as mk
import CORE.orchestrator as orch


# Config di prova
CFG = {
    "complexity_routing": {
        "enabled": True,
        "heavy_model": "worker_granite",
    },
    "models": {
        "worker_coder": {"name": "qwen2.5-coder:3b"},
        "worker_granite": {"name": "granite4:7b-a1b-h"},
    },
}
BASE = "worker_coder"
GRANITE_NAME = "granite4:7b-a1b-h"

TASK_ALTA_KW = "task thread con lock e join"
TASK_MEDIA = "crea una classe semplice con json"
TASK_BANALE = "stampa ciao mondo"
TASK_IMPATTO = "riusa la classe Statistiche per calcolare la media"


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def make_stub_worker(model_key, models, project_root=".", agent_id="demo-worker"):
    """Crea un Worker-like tramite SimpleNamespace con i soli attributi
    che _route_model_key legge: model_key, models, tools, log, agent_id."""
    class _StubLogger:
        def info(self, msg): pass
        def warning(self, msg): pass
    w = SimpleNamespace(
        model_key=model_key,
        models=models,
        tools=SimpleNamespace(project_root=project_root),
        log=_StubLogger(),
        agent_id=agent_id,
    )
    # Binda il metodo reale di Worker
    w._route_model_key = lambda task: Worker._route_model_key(w, task)
    return w


def make_real_model_client():
    """Restituisce un'istanza FakeModelClient ma registrata come
    'reale' tramite monkey-patch temporaneo di oc.ModelClient."""
    class FakeModelClient:
        pass
    orig = oc.ModelClient
    oc.ModelClient = FakeModelClient
    return FakeModelClient(), orig


def make_fake_model_client():
    """Restituisce un oggetto generico NON-ModelClient."""
    return object()


def setup_patched_env(installed_set, cfg):
    """Patch mk.installed_names e orch.load_config. Ritorna tuple di
    originali per restore."""
    orig_installed = getattr(mk, "installed_names", None)
    orig_load = getattr(orch, "load_config", None)
    mk.installed_names = lambda: installed_set
    orch.load_config = lambda: cfg
    return orig_installed, orig_load


def restore_env(orig_installed, orig_load):
    if orig_installed is not None:
        mk.installed_names = orig_installed
    if orig_load is not None:
        orch.load_config = orig_load


def demo_m9() -> None:
    section("M9 — Routing anche in ReAct: Worker._route_model_key()")
    routing.reset_hysteresis()

    # ── Scenario 1: client finto (test) → routing OFF
    print("\n[1] Worker con client NON-ModelClient (test) → routing OFF")
    models = make_fake_model_client()
    w = make_stub_worker(BASE, models)
    key, level, route = w._route_model_key(
        {"title": TASK_ALTA_KW, "description": ""})
    print(f"  → key={key}  level={level!r}  route={route!r}")
    assert key == BASE, "Client finto: deve restituire il base"
    assert level == "" and route == "", "Nessuna decisione registrata"

    # ── Scenario 2: client reale + task ALTA + heavy installato → heavy
    print("\n[2] Worker con ModelClient reale + task ALTA + heavy installato")
    models, orig_oc = make_real_model_client()
    orig_installed, orig_load = setup_patched_env({GRANITE_NAME}, CFG)
    try:
        w = make_stub_worker(BASE, models)
        key, level, route = w._route_model_key(
            {"title": TASK_ALTA_KW, "description": ""})
        print(f"  → key={key}  level={level}  route={route}")
        assert key == "worker_granite", "ALTA + heavy installato → heavy"
        assert level == "alta"
        assert "complessità alta" in route
    finally:
        oc.ModelClient = orig_oc
        restore_env(orig_installed, orig_load)
        routing.reset_hysteresis()

    # ── Scenario 3: client reale + task BASSA → base
    print("\n[3] Worker con ModelClient reale + task BASSA → resta base")
    models, orig_oc = make_real_model_client()
    orig_installed, orig_load = setup_patched_env({GRANITE_NAME}, CFG)
    try:
        w = make_stub_worker(BASE, models)
        key, level, route = w._route_model_key(
            {"title": TASK_BANALE, "description": ""})
        print(f"  → key={key}  level={level}  route={route}")
        assert key == BASE
        assert level == "bassa"
        assert "complessità bassa" in route
    finally:
        oc.ModelClient = orig_oc
        restore_env(orig_installed, orig_load)
        routing.reset_hysteresis()

    # ── Scenario 4: client reale + task ALTA + heavy NON installato → base fallback
    print("\n[4] Worker con ModelClient reale + task ALTA + heavy NON installato")
    models, orig_oc = make_real_model_client()
    orig_installed, orig_load = setup_patched_env(set(), CFG)  # heavy assente
    try:
        w = make_stub_worker(BASE, models)
        key, level, route = w._route_model_key(
            {"title": TASK_ALTA_KW, "description": ""})
        print(f"  → key={key}  level={level}  route={route}")
        assert key == BASE, "Heavy non installato → fallback al base"
        assert level == "alta"
        assert "NON installato" in route or "non usato" in route
    finally:
        oc.ModelClient = orig_oc
        restore_env(orig_installed, orig_load)
        routing.reset_hysteresis()

    # ── Scenario 5: client reale + termico in zona pausa → base
    print("\n[5] Worker con ModelClient reale + CPU in zona pausa termica")
    models, orig_oc = make_real_model_client()
    orig_installed, orig_load = setup_patched_env({GRANITE_NAME}, CFG)
    orig_thermal = routing._thermal_blocked
    routing._thermal_blocked = lambda: "termico: cpu 82°C gpu 0°C ≥ soglia → heavy evitato"
    try:
        w = make_stub_worker(BASE, models)
        key, level, route = w._route_model_key(
            {"title": TASK_ALTA_KW, "description": ""})
        print(f"  → key={key}  level={level}  route={route}")
        assert key == BASE, "Zona pausa termica → heavy evitato"
        assert "termico" in route
    finally:
        oc.ModelClient = orig_oc
        restore_env(orig_installed, orig_load)
        routing._thermal_blocked = orig_thermal
        routing.reset_hysteresis()

    # ── Scenario 6: route_model_key solleva → fail-open
    print("\n[6] Worker con route_model_key che solleva → fail-open, niente crash")
    models, orig_oc = make_real_model_client()
    orig_route = routing.route_model_key
    def boom(*a, **kw):
        raise RuntimeError("simulato")
    routing.route_model_key = boom
    try:
        w = make_stub_worker(BASE, models)
        key, level, route = w._route_model_key(
            {"title": TASK_ALTA_KW, "description": ""})
        print(f"  → key={key}  level={level!r}  route={route!r}")
        assert key == BASE, "Fail-open: resta base"
        assert level == "" and route == ""
    finally:
        oc.ModelClient = orig_oc
        routing.route_model_key = orig_route
        routing.reset_hysteresis()

    # ── Scenario 7: routing per IMPATTO dal grafo del code_map
    print("\n[7] Routing per IMPATTO: task che cita simboli su progetto multi-file")
    proj = Path(tempfile.mkdtemp())
    (proj / "utils.py").write_text(
        "class Statistiche:\n"
        "    def media(self, numeri):\n        return sum(numeri)/len(numeri)\n",
        encoding="utf-8")
    (proj / "app.py").write_text(
        "from utils import Statistiche\n"
        "def report(numeri):\n"
        "    s = Statistiche()\n"
        "    return s.media(numeri)\n",
        encoding="utf-8")
    models, orig_oc = make_real_model_client()
    orig_installed, orig_load = setup_patched_env({GRANITE_NAME}, CFG)
    try:
        w = make_stub_worker(BASE, models, project_root=str(proj))
        key, level, route = w._route_model_key(
            {"title": TASK_IMPATTO, "description": ""})
        print(f"  → key={key}  level={level}  route={route}")
        assert key == "worker_granite", "Impatto alta (≥2 file) → heavy"
        assert "impatto alta" in route
        assert "Statistiche" in route
    finally:
        oc.ModelClient = orig_oc
        restore_env(orig_installed, orig_load)
        routing.reset_hysteresis()
        shutil.rmtree(proj, ignore_errors=True)

    # ── Scenario 8: isteresi persistente tra più chiamate Worker
    print("\n[8] Isteresi M7: dopo ALTA, un task MEDIA resta heavy")
    models, orig_oc = make_real_model_client()
    orig_installed, orig_load = setup_patched_env({GRANITE_NAME}, CFG)
    try:
        w = make_stub_worker(BASE, models)
        # ALTA → imposta sticky heavy
        _, lv1, _ = w._route_model_key(
            {"title": TASK_ALTA_KW, "description": ""})
        assert lv1 == "alta"
        # MEDIA → resta heavy per isteresi
        key2, lv2, route2 = w._route_model_key(
            {"title": TASK_MEDIA, "description": ""})
        print(f"  → dopo ALTA, MEDIA: key={key2}  level={lv2}  route={route2}")
        assert lv2 == "alta", "Isteresi: MEDIA resta heavy dopo ALTA"
        assert "isteresi" in route2
    finally:
        oc.ModelClient = orig_oc
        restore_env(orig_installed, orig_load)
        routing.reset_hysteresis()

    print("\n✅ M9 PASS: Worker._route_model_key() integra il routing completo")
    print("          (complessità + impatto + isteresi + termico + fail-open)")
    print("          nel loop ReAct, con lo stesso contratto di run_direct")


if __name__ == "__main__":
    print("Run live M9 — routing anche in ReAct, senza LLM")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Worker module: {Worker.__module__}")
    demo_m9()
    print()
    print("=" * 70)
    print("  TUTTI GLI SCENARI M9 PASS — routing nel loop ReAct funzionante")
    print("=" * 70)
