"""test_attest_rpm.py — gate M3 in un comando, senza LLM e senza tachometro reale.

L'input dell'operatore e la temperatura live sono simulati: i test bloccano
la costruzione della ricevuta, il rifiuto dei valori non validi, i permessi
0600 e il fatto che il gate non venga mai scritto sopra 60 °C.
"""
from __future__ import annotations

import json
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.attest_rpm as ar  # noqa: E402
from tools import blocker_probe as bp  # noqa: E402

NOW = datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc)


def fake_snapshot(temp_c: float):
    def snapshot(base: Path = Path("/sys")) -> dict:
        return {
            "cpu_temp_c": temp_c,
            "temp_source": "coretemp (test)",
            "fan_rpm": 0,
            "rpm_source": "nessun sensore (test)",
            "fan_duty_pct": None,
            "nbfc_service_state": "test",
            "nbfc_unit_state": None,
            "nbfc_detail": "test",
            "pwm": None,
            "gate": {"verified": False},
        }
    return snapshot


def attestation(rpm=1800):
    return ar.build_attestation(rpm, "tachometro ottico X",
                                "lettura su paletta", "wildlux", "3 letture",
                                now=NOW)


def test_modulo_senza_llm_e_rpm_interattivo_validato(monkeypatch):
    src = (ROOT / "tools" / "attest_rpm.py").read_text(encoding="utf-8")
    assert not re.search(r"^(from|import) CORE\b", src, re.MULTILINE)

    values = iter(["abc", "100", "1800"])
    monkeypatch.setattr("builtins.input", lambda _: next(values))
    assert ar.prompt_rpm() == 1800

    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(SystemExit):
        ar.prompt_rpm()


def test_build_attestation_deterministico():
    assert attestation() == {
        "fan_rpm": 1800,
        "instrument": "tachometro ottico X",
        "method": "lettura su paletta",
        "operator": "wildlux",
        "measured_at": "2026-11-23T01:00:00+00:00",
        "notes": "3 letture",
    }


def test_attest_scrive_ricevuta_e_gate_valido(tmp_path, monkeypatch):
    monkeypatch.setattr(bp, "fan_snapshot", fake_snapshot(52.0))
    result = ar.attest(attestation(), state_dir=tmp_path / "state",
                       gate_file=tmp_path / "fan.json", now=NOW)

    receipt = result["attestation_path"]
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert json.loads(receipt.read_text(encoding="utf-8"))["fan_rpm"] == 1800
    gate_path = result["gate_path"]
    assert stat.S_IMODE(gate_path.stat().st_mode) == 0o600
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["fan_rpm"] == 1800
    assert gate["temp_c"] == 52.0
    assert gate["attestation"]["operator"] == "wildlux"
    assert result["gate"]["valid"] is True


def test_attest_rifiuta_temperatura_alta_senza_scrivere_gate(tmp_path,
                                                             monkeypatch):
    monkeypatch.setattr(bp, "fan_snapshot", fake_snapshot(65.0))
    gate_file = tmp_path / "fan.json"
    with pytest.raises(ValueError) as exc:
        ar.attest(attestation(), state_dir=tmp_path / "state",
                  gate_file=gate_file, now=NOW)
    assert "servono fan_rpm" in str(exc)
    assert not gate_file.exists()


def test_attest_rifiuta_rpm_fuori_range(tmp_path, monkeypatch):
    monkeypatch.setattr(bp, "fan_snapshot", fake_snapshot(45.0))
    with pytest.raises(ValueError) as exc:
        ar.attest(attestation(rpm=100), state_dir=tmp_path / "state",
                  gate_file=tmp_path / "fan.json", now=NOW)
    assert "range fisico" in str(exc)


def test_un_solo_comando_apre_il_gate(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bp, "fan_snapshot", fake_snapshot(51.0))
    values = iter(["1800", "tachometro ottico X", "lettura su paletta",
                   "wildlux", "note"])
    monkeypatch.setattr("builtins.input", lambda _: next(values))

    rc = ar.main(["--state-dir", str(tmp_path / "state"),
                  "--gate-file", str(tmp_path / "fan.json")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Gate VALIDO" in out
    assert "run_eval.py --live" in out
