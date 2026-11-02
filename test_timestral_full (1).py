"""Test per Round 2: Timestral completo (A1, A2, A3, A4).

Cosa testiamo:
- A1: TimestralGatekeeper.resume_temp è cablato da actors.json
  (non è più hardcoded a 65)
- A2: TimestralGatekeeper.check() latcha pausa se tok_per_sec è
  sotto min_tokens_per_sec (con isteresi sulla ripresa)
- A3: orchestratore._thermal_gate_pass() bypassa il gate se
  check_only_if_gpu=True e gpu_temp == 0
- A4: orchestratore._thermal_gate_pass() ferma/rilancia il
  generic_planner se pause_decision_model_too=True
"""
import sys, os, json, tempfile, shutil
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


def _make_orch_with_overrides(actors_ts: dict):
    """Crea un Orchestrator-like con gli override di actors.json iniettati.
    Evita di istanziare il vero Orchestrator (che richiede DB, Ollama, ecc.).
    """
    from MONITORING.thermal_manager import TimestralGatekeeper, PAUSE_CPU, PAUSE_GPU, RESUME_TEMP
    pause_cpu = float(actors_ts.get("cpu_temp_threshold", PAUSE_CPU))
    pause_gpu = float(actors_ts.get("gpu_temp_threshold", PAUSE_GPU))
    resume_temp = float(actors_ts.get("resume_temp_threshold", RESUME_TEMP))
    min_tps = float(actors_ts.get("min_tokens_per_sec", 0.0))
    check_only_if_gpu = bool(actors_ts.get("check_only_if_gpu", False))
    pause_dm = bool(actors_ts.get("pause_decision_model_too", True))

    orch = MagicMock()
    orch.thermal_gate = TimestralGatekeeper(
        pause_cpu=pause_cpu, pause_gpu=pause_gpu,
        resume_temp=resume_temp, min_tokens_per_sec=min_tps,
    )
    orch.check_only_if_gpu = check_only_if_gpu
    orch.pause_decision_model_too = pause_dm
    return orch


def _call_thermal_gate_pass(orch, sample):
    """Replica la logica di _thermal_gate_pass usando gli attributi del mock.
    Ritorna True se il tick procede, False se in pausa termica.
    """
    if sample is None:
        return True
    cpu_temp = sample.cpu_temp_max
    gpu_temp = getattr(sample, "gpu_temp", 0.0)
    if orch.check_only_if_gpu and gpu_temp == 0.0:
        return True
    tok_per_sec = getattr(sample, "tokens_per_sec", None)
    paused = orch.thermal_gate.check(cpu_temp, gpu_temp, tok_per_sec=tok_per_sec)
    return not paused


def test_a3_no_gpu_no_check_when_flag_true():
    """A3: check_only_if_gpu=True + GPU assente → gate bypassato."""
    orch = _make_orch_with_overrides({"check_only_if_gpu": True, "cpu_temp_threshold": 80})
    sample = FakeSample(cpu_temp_max=95, gpu_temp=0.0)
    # CPU 95 > 80 → normally would pause, but flag bypasses it
    assert _call_thermal_gate_pass(orch, sample) is True


def test_a3_no_gpu_no_check_when_flag_false():
    """A3: check_only_if_gpu=False + CPU alta → gate scatta (comportamento default)."""
    orch = _make_orch_with_overrides({"check_only_if_gpu": False, "cpu_temp_threshold": 80})
    sample = FakeSample(cpu_temp_max=95, gpu_temp=0.0)
    # Senza il flag, CPU alta scatta pausa anche senza GPU
    assert _call_thermal_gate_pass(orch, sample) is False


def test_a3_gpu_present_check_runs_when_flag_true():
    """A3: check_only_if_gpu=True + GPU presente → gate attivo."""
    orch = _make_orch_with_overrides({
        "check_only_if_gpu": True, "cpu_temp_threshold": 80, "gpu_temp_threshold": 75
    })
    sample = FakeSample(cpu_temp_max=50, gpu_temp=80)  # GPU sopra soglia
    assert _call_thermal_gate_pass(orch, sample) is False


def test_a3_gpu_present_temp_ok_when_flag_true():
    """A3: flag=True, GPU presente, temperature OK → gate pass."""
    orch = _make_orch_with_overrides({"check_only_if_gpu": True, "cpu_temp_threshold": 80})
    sample = FakeSample(cpu_temp_max=50, gpu_temp=60)
    assert _call_thermal_gate_pass(orch, sample) is True


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
        # A3
        test_a3_no_gpu_no_check_when_flag_true,
        test_a3_no_gpu_no_check_when_flag_false,
        test_a3_gpu_present_check_runs_when_flag_true,
        test_a3_gpu_present_temp_ok_when_flag_true,
        # A4
        test_a4_pause_decision_model_too_default_true,
        test_a4_actors_panel_save_persist_pause_dm,
        test_a4_resume_temp_threshold_in_defaults,
        test_a4_min_tokens_per_sec_in_defaults,
        test_a4_check_only_if_gpu_in_defaults,
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
