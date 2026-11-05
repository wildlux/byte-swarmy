"""Test per Round 3 — H1/H2/H3/H4/H5: Strategia hardware + pesi modelli.

Cosa testiamo:
- H1: SettingsPanel con sezione "Strategia Hardware" (combo a 4 voci + hint)
- H2: settings_store con hardware_strategy + auto-detect GPU
- H3: ActorsPanel con light/medium/heavy per LLM e Decision; mapping weight_default_model
- H4: Timestral sempre "light" + force_cpu=True (cablato)
- H5: orchestrator._resolve_actor_target (CPU/GPU in base alla strategia)
- H5: orchestrator._resolve_actor_model (modello da actors.json)
"""
import sys, os, json, tempfile, shutil
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import Optional

# Crea QApplication PRIMA di qualsiasi import che potrebbe creare QWidget.
# Tutti i test condividono questa app (singleton).
from PyQt6.QtWidgets import QApplication, QMessageBox
_APP = QApplication.instance() or QApplication(sys.argv)
_APP.processEvents()
QMessageBox.exec = lambda self, *a, **k: 1
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(
    lambda *a, **k: QMessageBox.StandardButton.Yes)


def _ensure_app():
    return _APP


# ============ H2: settings_store con hardware_strategy ============

def test_h2_defaults_include_hardware_strategy():
    """H2: DEFAULTS contiene hardware_strategy + detect_gpu_at_startup."""
    _ensure_app()
    from GUI.settings_store import DEFAULTS, HARDWARE_STRATEGIES
    assert "hardware_strategy" in DEFAULTS
    assert "detect_gpu_at_startup" in DEFAULTS
    assert DEFAULTS["hardware_strategy"] in HARDWARE_STRATEGIES
    assert DEFAULTS["detect_gpu_at_startup"] is True


def test_h2_set_get_hardware_strategy():
    """H2: set_hardware_strategy salva + get_hardware_strategy legge."""
    _ensure_app()
    from GUI import settings_store as ss
    # Backup
    backup = None
    if os.path.exists(ss.SETTINGS_FILE):
        with open(ss.SETTINGS_FILE) as f:
            backup = f.read()
    try:
        ss.set_hardware_strategy("gpu+cpu", user_set=True)
        assert ss.get_hardware_strategy() == "gpu+cpu"
        ss.set_hardware_strategy("cpu_only", user_set=True)
        assert ss.get_hardware_strategy() == "cpu_only"
    finally:
        if backup is not None:
            with open(ss.SETTINGS_FILE, "w") as f:
                f.write(backup)
        elif os.path.exists(ss.SETTINGS_FILE):
            os.remove(ss.SETTINGS_FILE)


def test_h2_invalid_strategy_falls_back_to_cpu_only():
    """H2: set con strategia invalida → fallback cpu_only."""
    _ensure_app()
    from GUI import settings_store as ss
    backup = None
    if os.path.exists(ss.SETTINGS_FILE):
        with open(ss.SETTINGS_FILE) as f:
            backup = f.read()
    try:
        ss.set_hardware_strategy("invalid_strategy", user_set=True)
        assert ss.get_hardware_strategy() == "cpu_only"
    finally:
        if backup is not None:
            with open(ss.SETTINGS_FILE, "w") as f:
                f.write(backup)
        elif os.path.exists(ss.SETTINGS_FILE):
            os.remove(ss.SETTINGS_FILE)


def test_h2_get_effective_strategy_description():
    """H2: descrizione umana per ogni strategia."""
    _ensure_app()
    from GUI.settings_store import get_effective_strategy_description
    assert "GPU+CPU" in get_effective_strategy_description("gpu+cpu")
    assert "Solo GPU" in get_effective_strategy_description("gpu_only")
    assert "Solo CPU" in get_effective_strategy_description("cpu_only")
    assert "CPU→GPU" in get_effective_strategy_description("cpu_then_gpu")


def test_h2_auto_detect_returns_valid_strategy():
    """H2: auto_detect_hardware_strategy ritorna sempre una strategia valida."""
    _ensure_app()
    from GUI.settings_store import auto_detect_hardware_strategy, HARDWARE_STRATEGIES
    s = auto_detect_hardware_strategy()
    assert s in HARDWARE_STRATEGIES


# ============ H3: ActorsPanel con light/medium/heavy ============

def test_h3_weight_default_models_mapping():
    """H3: WEIGHT_DEFAULT_MODELS ha 3 pesi per ognuno dei 3 attori."""
    _ensure_app()
    from GUI.actors_panel import WEIGHT_DEFAULT_MODELS, ACTOR_WEIGHTS
    for actor in ("llm", "decision_model", "timestral"):
        assert actor in WEIGHT_DEFAULT_MODELS
        for w in ACTOR_WEIGHTS:
            assert w in WEIGHT_DEFAULT_MODELS[actor]
            # Ogni mapping ritorna un nome modello non vuoto
            assert WEIGHT_DEFAULT_MODELS[actor][w]


def test_h3_weight_default_model_function():
    """H3: weight_default_model(actor, weight) ritorna modello valido."""
    _ensure_app()
    from GUI.actors_panel import weight_default_model
    assert weight_default_model("llm", "light") == "qwen2.5:1.5b"
    assert weight_default_model("llm", "heavy") == "llama3:8b"
    # Timestral: tutti i pesi ritornano light (H4)
    assert weight_default_model("timestral", "light") == "qwen2.5:0.5b"
    assert weight_default_model("timestral", "medium") == "qwen2.5:0.5b"
    assert weight_default_model("timestral", "heavy") == "qwen2.5:0.5b"


def test_h3_actors_panel_has_weight_combos():
    """H3: ActorsPanel ha combo Peso per LLM e Decision Model."""
    _ensure_app()

    # Reset
    from GUI.actors_panel import ACTORS_FILE
    if os.path.exists(ACTORS_FILE):
        os.remove(ACTORS_FILE)
    from GUI.actors_panel import ActorsPanel
    panel = ActorsPanel()
    assert panel.llm_weight.count() == 3  # light, medium, heavy
    assert panel.dec_weight.count() == 3
    # Verifica i data della combo
    weights = [panel.llm_weight.itemData(i) for i in range(3)]
    assert weights == ["light", "medium", "heavy"]


def test_h3_save_persists_weights():
    """H3: salvando ActorsPanel, i pesi sono scritti in actors.json."""
    _ensure_app()

    from GUI.actors_panel import (ActorsPanel, load_actors, ACTORS_FILE,
                                   save_actors)
    if os.path.exists(ACTORS_FILE):
        os.remove(ACTORS_FILE)
    panel = ActorsPanel()
    # Cambia LLM a heavy
    panel.llm_weight.setCurrentIndex(2)  # heavy
    panel._on_save()
    saved = load_actors()
    assert saved["llm"]["weight"] == "heavy"
    assert saved["decision_model"]["weight"] in ("light", "medium", "heavy")


# ============ H4: Timestral sempre light + force_cpu ============

def test_h4_timestral_always_light():
    """H4: DEFAULTS["timestral"]["weight"] è sempre "light"."""
    _ensure_app()
    from GUI.actors_panel import DEFAULTS
    assert DEFAULTS["timestral"]["weight"] == "light"


def test_h4_timestral_force_cpu_default():
    """H4: DEFAULTS["timestral"]["force_cpu"] è True."""
    _ensure_app()
    from GUI.actors_panel import DEFAULTS
    assert DEFAULTS["timestral"]["force_cpu"] is True


def test_h4_save_persists_timestral_light_force_cpu():
    """H4: salvando ActorsPanel, timestral.weight è "light" + force_cpu=True."""
    _ensure_app()

    from GUI.actors_panel import ActorsPanel, load_actors, ACTORS_FILE
    if os.path.exists(ACTORS_FILE):
        os.remove(ACTORS_FILE)
    panel = ActorsPanel()
    panel._on_save()  # salva con valori di default
    saved = load_actors()
    assert saved["timestral"]["weight"] == "light"
    assert saved["timestral"]["force_cpu"] is True


# ============ H5: orchestrator._resolve_actor_target ============

@dataclass
class FakeSample:
    cpu_temp_max: float = 50.0
    gpu_temp: float = 0.0
    cpu_load: float = 0.5  # 0.0 - 1.0
    tokens_per_sec: Optional[float] = None


def _make_orchestrator_mock(strategy: str, gpu: bool):
    """Crea un Orchestrator-like con gli attributi H5 impostati."""
    orch = MagicMock()
    orch.hardware_strategy = strategy
    orch.gpu_available = gpu
    orch.timestral = MagicMock()
    orch.timestral.last_sample = FakeSample(cpu_load=0.5)
    # Binda il vero metodo _resolve_actor_target
    from CORE.orchestrator import Orchestrator
    orch._resolve_actor_target = Orchestrator._resolve_actor_target.__get__(orch)
    return orch


def test_h5_resolve_timestral_always_cpu():
    """H5: Timestral va SEMPRE su CPU, qualunque strategia."""
    for strategy in ("cpu_only", "gpu_only", "gpu+cpu", "cpu_then_gpu"):
        orch = _make_orchestrator_mock(strategy, gpu=True)
        assert orch._resolve_actor_target("timestral") == "cpu", (
            f"strategy={strategy} should route Timestral to CPU")


def test_h5_cpu_only_routes_all_to_cpu():
    """H5: cpu_only → tutto su CPU."""
    orch = _make_orchestrator_mock("cpu_only", gpu=True)
    for actor in ("llm", "decision_model", "timestral"):
        assert orch._resolve_actor_target(actor) == "cpu"


def test_h5_gpu_only_routes_llm_decision_to_gpu():
    """H5: gpu_only → LLM e Decision su GPU; Timestral su CPU."""
    orch = _make_orchestrator_mock("gpu_only", gpu=True)
    assert orch._resolve_actor_target("llm") == "gpu"
    assert orch._resolve_actor_target("decision_model") == "gpu"
    assert orch._resolve_actor_target("timestral") == "cpu"


def test_h5_gpu_plus_cpu_routes_llm_to_gpu():
    """H5: gpu+cpu → LLM su GPU, Decision su CPU, Timestral su CPU."""
    orch = _make_orchestrator_mock("gpu+cpu", gpu=True)
    assert orch._resolve_actor_target("llm") == "gpu"
    assert orch._resolve_actor_target("decision_model") == "cpu"
    assert orch._resolve_actor_target("timestral") == "cpu"


def test_h5_cpu_then_gpu_default_cpu():
    """H5: cpu_then_gpu con CPU non overload → CPU di default."""
    orch = _make_orchestrator_mock("cpu_then_gpu", gpu=True)
    orch.timestral.last_sample = FakeSample(cpu_load=0.5)  # 50% < 90%
    assert orch._resolve_actor_target("llm") == "cpu"
    assert orch._resolve_actor_target("decision_model") == "cpu"


def test_h5_cpu_then_gpu_overload_switches_to_gpu():
    """H5: cpu_then_gpu con CPU > 90% → LLM switcha a GPU."""
    orch = _make_orchestrator_mock("cpu_then_gpu", gpu=True)
    orch.timestral.last_sample = FakeSample(cpu_load=0.95)  # 95% > 90%
    assert orch._resolve_actor_target("llm") == "gpu"
    # Decision resta su CPU
    assert orch._resolve_actor_target("decision_model") == "cpu"


def test_h5_no_gpu_routes_all_to_cpu():
    """H5: GPU non disponibile → tutto su CPU anche se strategy=gpu_only."""
    orch = _make_orchestrator_mock("gpu_only", gpu=False)
    assert orch._resolve_actor_target("llm") == "cpu"
    assert orch._resolve_actor_target("decision_model") == "cpu"


# ============ Run ============

if __name__ == "__main__":
    import traceback
    tests = [
        # H2
        test_h2_defaults_include_hardware_strategy,
        test_h2_set_get_hardware_strategy,
        test_h2_invalid_strategy_falls_back_to_cpu_only,
        test_h2_get_effective_strategy_description,
        test_h2_auto_detect_returns_valid_strategy,
        # H3
        test_h3_weight_default_models_mapping,
        test_h3_weight_default_model_function,
        test_h3_actors_panel_has_weight_combos,
        test_h3_save_persists_weights,
        # H4
        test_h4_timestral_always_light,
        test_h4_timestral_force_cpu_default,
        test_h4_save_persists_timestral_light_force_cpu,
        # H5
        test_h5_resolve_timestral_always_cpu,
        test_h5_cpu_only_routes_all_to_cpu,
        test_h5_gpu_only_routes_llm_decision_to_gpu,
        test_h5_gpu_plus_cpu_routes_llm_to_gpu,
        test_h5_cpu_then_gpu_default_cpu,
        test_h5_cpu_then_gpu_overload_switches_to_gpu,
        test_h5_no_gpu_routes_all_to_cpu,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n=== {passed}/{len(tests)} test passati ===")


# ============ Capacità adattiva (compute_capacity, commit 2026-11-05) ============
# Il multi-modello non è più vietato per firma della strategia: è calcolato
# dai modelli REALI in actors.json contro VRAM/RAM. Se cambia l'hardware
# (o i modelli), basta ridetectare e la capacità si aggiorna.

def _make_profile(vram_gb: float, ram_gb: float, actor_sizes: list,
                  force_cpu_actors: tuple = ()):
    """Profilo sintetico con i 3 attori simulati (nome, size, force_cpu)."""
    from CORE import hardware_detector as hd
    p = hd.HardwareProfile()
    p.gpu_type = "nvidia_cuda" if vram_gb > 0 else "none"
    p.vram_total_gb = vram_gb
    p.ram_total_gb = ram_gb
    p.cpu_cores = 8
    p.model_size_gb = max(actor_sizes) if actor_sizes else 2.0
    names = [f"m{i}" for i in range(len(actor_sizes))]
    size_map = {n: s for n, s in zip(names, actor_sizes)}
    actors = [(n, n, n in force_cpu_actors) for n in names]
    with patch.object(hd, "_resolved_actor_models", return_value=actors), \
         patch.object(hd, "_estimate_model_size_gb",
                      side_effect=lambda m: size_map[m]):
        hd.compute_capacity(p)
    return p


def test_capacity_gtx1050_three_small_models_multi_model():
    """4GB VRAM + 3 modelli ~1GB: 2 su GPU + 1 su CPU, multi-modello OK."""
    p = _make_profile(4.0, 7.6, [1.0, 1.0, 1.0])
    assert p.capacity_gpu_models == 2, p.capacity_note
    assert p.capacity_cpu_models == 1
    assert p.models_in_ram == 3
    assert p.supports_multi_model


def test_capacity_bigger_gpu_all_on_gpu():
    """12GB VRAM: tutti e 3 i modelli da 1GB stanno su GPU."""
    p = _make_profile(12.0, 16.0, [1.0, 1.0, 1.0])
    assert p.capacity_gpu_models == 3
    assert p.capacity_cpu_models == 0
    assert p.models_in_ram == 3


def test_capacity_huge_model_not_resident():
    """Modello 4.5GB su 4GB VRAM / 7.6GB RAM: non resta residente, ma
    models_in_ram non scende mai sotto 1 (il Worker deve girare)."""
    p = _make_profile(4.0, 7.6, [4.5])
    assert p.capacity_gpu_models == 0
    assert p.models_in_ram == 1
    assert not p.supports_multi_model


def test_capacity_no_gpu_all_on_cpu():
    """Solo CPU (16GB RAM): 2 modelli da 1GB residenti su CPU."""
    p = _make_profile(0.0, 16.0, [1.0, 1.0])
    assert p.capacity_gpu_models == 0
    assert p.capacity_cpu_models == 2
    assert p.models_in_ram == 2
    assert p.supports_multi_model


def test_capacity_updates_when_hardware_changes():
    """Cambio hardware: stesso actors.json, basta ridetectare.

    4GB VRAM → 2 su GPU + 1 su CPU; aggiornando a 8GB VRAM → 3 su GPU.
    Il piano segue l'hardware, non è bloccato dalla strategia.
    """
    p_small = _make_profile(4.0, 7.6, [1.0, 1.0, 1.0])
    assert (p_small.capacity_gpu_models, p_small.capacity_cpu_models) == (2, 1)
    p_big = _make_profile(8.0, 7.6, [1.0, 1.0, 1.0])
    assert p_big.capacity_gpu_models == 3
    assert p_big.capacity_cpu_models == 0
    assert p_big.supports_multi_model


def test_capacity_timestral_never_on_gpu():
    """Il Timestral (gatekeeper termico) è force_cpu: resta su CPU anche
    se la VRAM libera potrebbe ospitarlo. Il piano conta TUTTI e 3 gli
    attori (llm + decision + timestral ~0.3GB)."""
    # llm 1GB, decision 1GB, timestral 0.3GB force-cpu — 4GB VRAM
    p = _make_profile(4.0, 7.6, [1.0, 1.0, 0.3],
                      force_cpu_actors=("m2",))
    assert p.capacity_gpu_models == 2      # llm + decision su GPU
    assert p.capacity_cpu_models == 1      # timestral su CPU
    assert p.models_in_ram == 3
    assert "sempre su CPU" in p.capacity_note


def test_capacity_never_below_one_worker():
    """Anche con memoria minima il Worker deve poter girare (>= 1)."""
    p = _make_profile(0.0, 2.0, [1.5])
    assert p.models_in_ram >= 1
