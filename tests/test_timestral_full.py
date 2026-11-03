"""Test per Round 2: Timestral completo (A1, A2, A3, A4).

Cosa testiamo:
- A1: TimestralGatekeeper.resume_temp è cablato da actors.json
  (non è più hardcoded a 65)
- A2: TimestralGatekeeper.check() latcha pausa se tok_per_sec è
  sotto min_tokens_per_sec (con isteresi sulla ripresa)
- A3: orchestratore._thermal_gate_pass() bypassa il gate se
  check_only_if_gpu=True e gpu_temp == 0
  (I1: i test chiamano il VERO metodo via Orchestrator.__new__,
  niente più repliche della logica nei test)
- A4: orchestratore._thermal_gate_pass() ferma/rilancia il
  generic_planner se pause_decision_model_too=True
  (I2: set_paused(True/False) verificato sul metodo reale)
"""
import sys, os, json, tempfile, shutil
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch


# ============ A1: resume_temp da actors.json ============

def test_a1_gatekeeper_resume_temp_default():
    """A1: senza override, resume_temp è il default 65."""
    from MONITORING.thermal_manager import TimestralGatekeeper, RESUME_TEMP
    gate = TimestralGatekeeper()
    assert gate.resume_temp == RESUME_TEMP
    assert gate.resume_temp == 65.0


def test_a1_gatekeeper_resume_temp_override():
    """A1: con resume_temp=70, scatta a 80 ma riprende solo sotto 70."""
    from MONITORING.thermal_manager import TimestralGatekeeper
    gate = TimestralGatekeeper(
        pause_cpu=80, pause_gpu=80, resume_temp=70
    )
    # Sopra soglia → pausa
    assert gate.check(85, 0) is True
    # 72 > 70 → ancora in pausa (non è ancora sotto resume)
    assert gate.check(72, 0) is True
    # 69 < 70 → ripresa
    assert gate.check(69, 0) is False
    assert gate.resume_temp == 70


def test_a1_load_timestral_overrides_resume():
    """A1: load_timestral_overrides legge resume_temp_threshold."""
    from MONITORING.thermal_manager import load_timestral_overrides
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "timestral": {
                "cpu_temp_threshold": 80,
                "gpu_temp_threshold": 75,
                "resume_temp_threshold": 70,
                "min_tokens_per_sec": 5.0,
            }
        }, f)
        path = f.name
    try:
        ts = load_timestral_overrides(path)
        assert ts["resume_temp_threshold"] == 70
        assert ts["cpu_temp_threshold"] == 80
    finally:
        os.unlink(path)


def test_a1_load_timestral_overrides_missing_resume_uses_default():
    """A1: se actors.json manca di resume_temp_threshold, l'orchestratore
    usa il default RESUME_TEMP (65) via fallback."""
    from MONITORING.thermal_manager import load_timestral_overrides, RESUME_TEMP
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "timestral": {
                "cpu_temp_threshold": 80,
                # manca resume_temp_threshold
            }
        }, f)
        path = f.name
    try:
        ts = load_timestral_overrides(path)
        # Se il campo manca, dict.get(key, default) restituisce None → l'orchestratore
        # fa fallback a RESUME_TEMP. Verifica che .get() ritorni None.
        assert ts.get("resume_temp_threshold") is None
        # Simula il fallback dell'orchestratore:
        resume = float(ts.get("resume_temp_threshold", RESUME_TEMP))
        assert resume == RESUME_TEMP
    finally:
        os.unlink(path)


# ============ A2: min_tokens_per_sec nel gatekeeper ============

def test_a2_gatekeeper_min_tps_disabled_by_default():
    """A2: senza min_tokens_per_sec, throughput check è disattivato."""
    from MONITORING.thermal_manager import TimestralGatekeeper
    gate = TimestralGatekeeper()
    assert gate.min_tokens_per_sec == 0.0
    # tok/s basso non latcha pausa se min=0
    assert gate.check(50, 0, tok_per_sec=1.0) is False


def test_a2_gatekeeper_min_tps_pause_when_low():
    """A2: tok/s=3 sotto soglia 5 → pausa con motivo 'throughput'."""
    from MONITORING.thermal_manager import TimestralGatekeeper
    gate = TimestralGatekeeper(min_tokens_per_sec=5.0)
    # Temperatura OK, ma throughput basso → pausa
    assert gate.check(40, 0, tok_per_sec=3.0) is True
    assert gate.paused is True
    assert "throughput" in gate.pause_reason
    assert "3.0" in gate.pause_reason
    assert "5.0" in gate.pause_reason


def test_a2_gatekeeper_min_tps_no_pause_when_high():
    """A2: tok/s=10 sopra soglia 5 → nessuna pausa da throughput."""
    from MONITORING.thermal_manager import TimestralGatekeeper
    gate = TimestralGatekeeper(min_tokens_per_sec=5.0)
    # Temperatura OK, throughput OK
    assert gate.check(40, 0, tok_per_sec=10.0) is False
    assert gate.paused is False


def test_a2_gatekeeper_min_tps_resume_requires_high_tps():
    """A2: isteresi — dopo pausa throughput, riprende solo se tps sopra soglia."""
    from MONITORING.thermal_manager import TimestralGatekeeper
    gate = TimestralGatekeeper(
        pause_cpu=80, resume_temp=60, min_tokens_per_sec=5.0
    )
    # Scatta pausa per throughput
    assert gate.check(50, 0, tok_per_sec=2.0) is True
    # Ora temperatura OK, throughput ancora basso → deve restare in pausa
    assert gate.check(40, 0, tok_per_sec=3.0) is True
    # Ora temperatura OK + throughput OK → riprende
    assert gate.check(40, 0, tok_per_sec=8.0) is False


def test_a2_gatekeeper_min_tps_none_skips_check():
    """A2: se tok_per_sec=None, il check tps è skippato (backward compat)."""
    from MONITORING.thermal_manager import TimestralGatekeeper
    gate = TimestralGatekeeper(min_tokens_per_sec=5.0)
    # None → skip, gate funziona solo su temperatura
    assert gate.check(40, 0, tok_per_sec=None) is False
    assert gate.check(90, 0, tok_per_sec=None) is True


# ============ A3: check_only_if_gpu nell'orchestratore ============

@dataclass
class FakeSample:
    """Stub di ThermalSample per testare l'orchestratore senza I/O reali."""
    cpu_temp_max: float = 90.0
    gpu_temp: float = 0.0
    tokens_per_sec: Optional[float] = None


def _make_real_orch(actors_ts: dict):
    """I1: crea un VERO Orchestrator (senza __init__, che vuole DB/Ollama)
    con gli attributi usati da `_thermal_gate_pass` iniettati a mano.

    Così se il codice reale del metodo cambia, i test catturano la
    regressione (niente più repliche della logica nei test).
    """
    from CORE.orchestrator import Orchestrator
    from MONITORING.thermal_manager import (
        TimestralGatekeeper, PAUSE_CPU, PAUSE_GPU, RESUME_TEMP,
    )
    pause_cpu = float(actors_ts.get("cpu_temp_threshold", PAUSE_CPU))
    pause_gpu = float(actors_ts.get("gpu_temp_threshold", PAUSE_GPU))
    resume_temp = float(actors_ts.get("resume_temp_threshold", RESUME_TEMP))
    min_tps = float(actors_ts.get("min_tokens_per_sec", 0.0))
    check_only_if_gpu = bool(actors_ts.get("check_only_if_gpu", False))
    pause_dm = bool(actors_ts.get("pause_decision_model_too", True))

    orch = Orchestrator.__new__(Orchestrator)
    orch.thermal_gate = TimestralGatekeeper(
        pause_cpu=pause_cpu, pause_gpu=pause_gpu,
        resume_temp=resume_temp, min_tokens_per_sec=min_tps,
    )
    orch.timestral = SimpleNamespace(last_sample=None, get_advice=lambda: None)
    orch.check_only_if_gpu = check_only_if_gpu
    orch.pause_decision_model_too = pause_dm
    orch.queue = MagicMock()      # pause_thermal/resume_thermal mockati
    orch.log = MagicMock()
    return orch


def _set_sample(orch, sample):
    orch.timestral.last_sample = sample


def test_a3_no_gpu_no_check_when_flag_true():
    """A3 (I1, metodo VERO): check_only_if_gpu=True + GPU assente → bypass."""
    orch = _make_real_orch({"check_only_if_gpu": True, "cpu_temp_threshold": 80})
    _set_sample(orch, FakeSample(cpu_temp_max=95, gpu_temp=0.0))
    # CPU 95 > 80 → normalmente pausa, ma il flag bypassa il gate
    assert orch._thermal_gate_pass() is True
    orch.queue.pause_thermal.assert_not_called()


def test_a3_no_gpu_no_check_when_flag_false():
    """A3 (I1, metodo VERO): flag=False + CPU alta → gate scatta."""
    orch = _make_real_orch({"check_only_if_gpu": False, "cpu_temp_threshold": 80})
    _set_sample(orch, FakeSample(cpu_temp_max=95, gpu_temp=0.0))
    assert orch._thermal_gate_pass() is False
    orch.queue.pause_thermal.assert_called_once()


def test_a3_gpu_present_check_runs_when_flag_true():
    """A3 (I1, metodo VERO): flag=True + GPU presente sopra soglia → pausa."""
    orch = _make_real_orch({
        "check_only_if_gpu": True, "cpu_temp_threshold": 80, "gpu_temp_threshold": 75
    })
    _set_sample(orch, FakeSample(cpu_temp_max=50, gpu_temp=80))
    assert orch._thermal_gate_pass() is False
    orch.queue.pause_thermal.assert_called_once()


def test_a3_gpu_present_temp_ok_when_flag_true():
    """A3 (I1, metodo VERO): flag=True, GPU presente, temperature OK → pass."""
    orch = _make_real_orch({"check_only_if_gpu": True, "cpu_temp_threshold": 80})
    _set_sample(orch, FakeSample(cpu_temp_max=50, gpu_temp=60))
    assert orch._thermal_gate_pass() is True
    orch.queue.pause_thermal.assert_not_called()


def test_a3_no_sample_no_gate():
    """A3 (I1, metodo VERO): sensori assenti (last_sample None) → degradato,
    gate non blocca."""
    orch = _make_real_orch({"check_only_if_gpu": False, "cpu_temp_threshold": 80})
    _set_sample(orch, None)          # timestral senza sample
    assert orch._thermal_gate_pass() is True
    orch.queue.pause_thermal.assert_not_called()


# ============ A4 (I2): pause_decision_model_too sul metodo VERO ============

def test_a4_real_pause_stops_decision_model_too():
    """I2: pause_decision_model_too=True + gate che scatta → il generic
    planner viene messo in pausa (set_paused(True) chiamato)."""
    orch = _make_real_orch({"pause_decision_model_too": True,
                            "cpu_temp_threshold": 80})
    orch.generic_planner = MagicMock()
    _set_sample(orch, FakeSample(cpu_temp_max=95, gpu_temp=0.0))
    assert orch._thermal_gate_pass() is False
    # A4: anche il decision model fermato
    orch.generic_planner.set_paused.assert_called_once_with(True)


def test_a4_real_pause_resume_restarts_decision_model():
    """I2: dopo la pausa termica, con temperatura sotto la soglia di
    ripresa → resume → set_paused(False) sul decision model."""
    orch = _make_real_orch({"pause_decision_model_too": True,
                            "cpu_temp_threshold": 80})
    orch.generic_planner = MagicMock()
    _set_sample(orch, FakeSample(cpu_temp_max=95, gpu_temp=0.0))
    assert orch._thermal_gate_pass() is False          # pausa
    orch.queue.resume_thermal.return_value = 2         # 2 task riaccodati
    _set_sample(orch, FakeSample(cpu_temp_max=50, gpu_temp=0.0))
    assert orch._thermal_gate_pass() is True           # ripresa
    assert orch.generic_planner.set_paused.call_args_list == [
        call(True), call(False)]


def test_a4_real_pause_false_does_not_touch_planner():
    """I2: pause_decision_model_too=False → il planner NON viene toccato."""
    orch = _make_real_orch({"pause_decision_model_too": False,
                            "cpu_temp_threshold": 80})
    orch.generic_planner = MagicMock()
    _set_sample(orch, FakeSample(cpu_temp_max=95, gpu_temp=0.0))
    assert orch._thermal_gate_pass() is False
    orch.generic_planner.set_paused.assert_not_called()


# ============ A4: pause_decision_model_too ============

def test_a4_pause_decision_model_too_default_true():
    """A4: default di pause_decision_model_too è True (sicuro)."""
    from GUI.actors_panel import DEFAULTS
    assert DEFAULTS["timestral"]["pause_decision_model_too"] is True


def test_a4_actors_panel_save_persist_pause_dm():
    """A4: il campo pause_decision_model_too è salvato nel JSON."""
    from GUI.actors_panel import DEFAULTS, save_actors, load_actors, ACTORS_FILE
    # Salva un config di test
    test_actors = {
        "llm": {"model": "test", "temperature": 0.1, "num_ctx": 2048, "num_predict": 256},
        "decision_model": {"model": "test", "temperature": 0.4, "num_ctx": 3072, "num_predict": 512},
        "timestral": {
            "enabled": True,
            "cpu_temp_threshold": 80, "gpu_temp_threshold": 75,
            "resume_temp_threshold": 65,
            "min_tokens_per_sec": 5.0,
            "thermal_pause_seconds": 30,
            "check_only_if_gpu": False,
            "pause_decision_model_too": False,  # ← test cambio
            "monitor_interval_sec": 30,
        },
    }
    # Backup
    backup = None
    if os.path.exists(ACTORS_FILE):
        with open(ACTORS_FILE) as f:
            backup = f.read()
    try:
        save_actors(test_actors)
        loaded = load_actors()
        assert loaded["timestral"]["pause_decision_model_too"] is False
    finally:
        if backup is not None:
            with open(ACTORS_FILE, "w") as f:
                f.write(backup)
        elif os.path.exists(ACTORS_FILE):
            os.remove(ACTORS_FILE)


def test_a4_resume_temp_threshold_in_defaults():
    """A1 + A4: il campo resume_temp_threshold è nei DEFAULTS (UI lo salva)."""
    from GUI.actors_panel import DEFAULTS
    assert "resume_temp_threshold" in DEFAULTS["timestral"]
    assert DEFAULTS["timestral"]["resume_temp_threshold"] == 65


def test_a4_min_tokens_per_sec_in_defaults():
    """A2: il campo min_tokens_per_sec è nei DEFAULTS."""
    from GUI.actors_panel import DEFAULTS
    assert "min_tokens_per_sec" in DEFAULTS["timestral"]
    assert DEFAULTS["timestral"]["min_tokens_per_sec"] == 5.0


def test_a4_check_only_if_gpu_in_defaults():
    """A3: il campo check_only_if_gpu è nei DEFAULTS."""
    from GUI.actors_panel import DEFAULTS
    assert "check_only_if_gpu" in DEFAULTS["timestral"]
    assert DEFAULTS["timestral"]["check_only_if_gpu"] is False


# ============ Compatibilità: vecchio check(cpu, gpu) senza tok/s ============

def test_backward_compat_check_without_tok_per_sec():
    """Il vecchio check(cpu, gpu) senza tok_per_sec continua a funzionare."""
    from MONITORING.thermal_manager import TimestralGatekeeper
    gate = TimestralGatekeeper(pause_cpu=80, resume_temp=65)
    # API vecchia: solo 2 args
    assert gate.check(90, 0) is True
    assert gate.check(50, 0) is False


# ============ Run ============

if __name__ == "__main__":
    import traceback
    tests = [
        # A1
        test_a1_gatekeeper_resume_temp_default,
        test_a1_gatekeeper_resume_temp_override,
        test_a1_load_timestral_overrides_resume,
        test_a1_load_timestral_overrides_missing_resume_uses_default,
        # A2
        test_a2_gatekeeper_min_tps_disabled_by_default,
        test_a2_gatekeeper_min_tps_pause_when_low,
        test_a2_gatekeeper_min_tps_no_pause_when_high,
        test_a2_gatekeeper_min_tps_resume_requires_high_tps,
        test_a2_gatekeeper_min_tps_none_skips_check,
        # A3 (I1: chiamano il VERO _thermal_gate_pass)
        test_a3_no_gpu_no_check_when_flag_true,
        test_a3_no_gpu_no_check_when_flag_false,
        test_a3_gpu_present_check_runs_when_flag_true,
        test_a3_gpu_present_temp_ok_when_flag_true,
        test_a3_no_sample_no_gate,
        # A4 (I2: metodo VERO con generic_planner mockato)
        test_a4_pause_decision_model_too_default_true,
        test_a4_actors_panel_save_persist_pause_dm,
        test_a4_resume_temp_threshold_in_defaults,
        test_a4_min_tokens_per_sec_in_defaults,
        test_a4_check_only_if_gpu_in_defaults,
        test_a4_real_pause_stops_decision_model_too,
        test_a4_real_pause_resume_restarts_decision_model,
        test_a4_real_pause_false_does_not_touch_planner,
        # Backward compat
        test_backward_compat_check_without_tok_per_sec,
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
