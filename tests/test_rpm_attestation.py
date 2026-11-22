"""test_rpm_attestation.py — M3: misura RPM esterna attestata, senza surrogati.

Il sensore non espone i RPM: una misura fisica con tachometro può essere
registrata solo tramite ricevuta con strumento/metodo/operatore/timestamp.
Nessun LLM, rete o GPU. La temperatura resta letta live e il duty-cycle non
diventa mai una prova dei giri.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import blocker_probe as bp  # noqa: E402

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def _receipt(tmp_path: Path, **overrides) -> Path:
    data = {
        "fan_rpm": 1800,
        "instrument": "tachometro ottico DT-6234B",
        "method": "lettura ottica su paletta ventola CPU",
        "operator": "wildlux",
        "measured_at": "2026-11-22T11:55:00+00:00",
        "notes": "5 minuti prima della lettura temperatura",
    }
    data.update(overrides)
    path = tmp_path / "rpm_attestation.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def live_temp(monkeypatch):
    """Sensori finti: temperatura live + nbfc senza RPM (caso reale M3)."""
    monkeypatch.setattr(bp, "read_cpu_temp_c", lambda base: (53.0, "fixture"))
    monkeypatch.setattr(bp, "nbfc_probe", lambda: {
        "rpm": 0, "rpm_source": None, "fan_duty_pct": 20.0,
        "service_state": "daemon attivo", "unit_state": "active",
        "detail": "Current Fan Speed : 0.00",
    })
    monkeypatch.setattr(bp, "read_pwm", lambda base: [])


def test_ricevuta_valida_accettata(tmp_path):
    data = bp.load_rpm_attestation(_receipt(tmp_path), now=NOW)
    assert data["fan_rpm"] == 1800
    assert data["operator"] == "wildlux"
    assert data["instrument"].startswith("tachometro")
    assert data["measured_at"].startswith("2026-11-22T11:55:00")


@pytest.mark.parametrize("missing", bp.ATTEST_REQUIRED_FIELDS)
def test_campi_obbligatori_mancanti_rifiutati(tmp_path, missing):
    path = _receipt(tmp_path, **{missing: ""})
    with pytest.raises(ValueError, match="campi obbligatori"):
        bp.load_rpm_attestation(path, now=NOW)


@pytest.mark.parametrize("bad", [0, 1, 299, 6001, "1800", True, None])
def test_rpm_fuori_range_o_non_numerico_rifiutato(tmp_path, bad):
    path = _receipt(tmp_path, fan_rpm=bad)
    with pytest.raises(ValueError) as exc:
        bp.load_rpm_attestation(path, now=NOW)
    assert "fan_rpm" in str(exc.value)


def test_misura_stale_e_futuro_rifiutati(tmp_path):
    stale = _receipt(tmp_path, measured_at="2026-11-22T10:00:00+00:00")
    with pytest.raises(ValueError, match="troppo vecchia"):
        bp.load_rpm_attestation(stale, now=NOW)
    future = _receipt(tmp_path, measured_at="2026-11-22T13:00:00+00:00")
    with pytest.raises(ValueError, match="futuro"):
        bp.load_rpm_attestation(future, now=NOW)
    malformed = _receipt(tmp_path, measured_at="non-una-data")
    with pytest.raises(ValueError, match="non valido"):
        bp.load_rpm_attestation(malformed, now=NOW)


def test_ricevuta_naive_usata_come_utc(tmp_path):
    path = _receipt(tmp_path, measured_at="2026-11-22T11:55:00")
    data = bp.load_rpm_attestation(path, now=NOW)
    assert data["measured_at"].endswith("+00:00")


def test_ricevuta_dentro_repo_rifiutata(tmp_path):
    assert bp._attestation_path_ok(tmp_path / "ok.json") is True
    assert bp._attestation_path_ok(
        ROOT / "data" / "state" / "ok.json") is True
    assert bp._attestation_path_ok(ROOT / "ok.json") is False
    assert bp._attestation_path_ok(ROOT / "DOCS" / "ok.json") is False
    bad = ROOT / "rpm_attestation_in_tree.json"
    try:
        bad.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="fuori posto"):
            bp.load_rpm_attestation(bad, now=NOW)
    finally:
        bad.unlink(missing_ok=True)


def test_ricevuta_non_json_rifiutata(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{non json", encoding="utf-8")
    with pytest.raises(ValueError, match="non leggibile"):
        bp.load_rpm_attestation(path, now=NOW)


def test_temperatura_resta_live_e_duty_non_e_prova(tmp_path, monkeypatch,
                                                   live_temp):
    att = bp.load_rpm_attestation(_receipt(tmp_path), now=NOW)
    snap = bp.attested_rpm_snapshot(att, tmp_path)
    assert snap["fan_rpm"] == 1800
    assert snap["cpu_temp_c"] == 53.0
    assert snap["gate"]["verified"] is True
    # nbfc legge 0 RPM e duty 20%: il duty è solo contesto, non decide il gate.
    assert snap["fan_duty_pct"] == 20.0
    assert snap["rpm_source"].startswith("misura esterna")

    monkeypatch.setattr(bp, "read_cpu_temp_c", lambda base: (71.0, "fixture"))
    hot = bp.attested_rpm_snapshot(att, tmp_path)
    assert hot["gate"]["fan_rpm_positivo"] is True
    assert hot["gate"]["temp_entro_60c"] is False
    assert hot["gate"]["verified"] is False
    with pytest.raises(ValueError, match="Rifiutato"):
        bp.write_fan_verification(hot, tmp_path / "gate.json")


def test_gate_scritto_con_provenienza_esplicita(tmp_path, live_temp):
    att = bp.load_rpm_attestation(_receipt(tmp_path), now=NOW)
    out = tmp_path / "fan_verified.json"
    path = bp.write_fan_verification(bp.attested_rpm_snapshot(att, tmp_path),
                                     out)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["fan_rpm"] == 1800
    assert data["temp_c"] == 53.0
    assert "--attest-rpm" in data["method"]
    assert "tachometro" in data["sources"]["fan_rpm"]
    assert data["attestation"]["operator"] == "wildlux"
    assert data["fan_duty_pct_context_only"] == 20.0
    assert bp.read_stored_fan(path)["valid"] is True


def test_cli_attest_rpm_happy_path_e_rifiuti(tmp_path, monkeypatch, capsys,
                                             live_temp):
    fresh = datetime.now(timezone.utc).isoformat(timespec="seconds")
    receipt = _receipt(tmp_path, measured_at=fresh)
    gate = tmp_path / "gate.json"
    monkeypatch.setattr(bp, "FAN_FILE", gate)
    assert bp.main(["--attest-rpm", str(receipt)]) == 0
    assert "provenienza misura esterna attestata" in capsys.readouterr().out
    assert bp.read_stored_fan(gate)["valid"] is True

    bad = _receipt(tmp_path, fan_rpm=0)
    assert bp.main(["--attest-rpm", str(bad)]) == 1
    assert "RIFIUTO" in capsys.readouterr().out
    assert bp.main(["--attest-rpm", str(receipt), "--write-fan"]) == 1
    assert "mutuamente esclusivi" in capsys.readouterr().out


def test_cli_non_accetta_rpm_diretto(capsys):
    with pytest.raises(SystemExit):
        bp.main(["--rpm", "1800"])
    assert "--rpm" in capsys.readouterr().err


def test_default_gate_risolto_a_runtime_non_congelato(tmp_path, monkeypatch,
                                                      live_temp):
    """Regressione: un default arg congelato scriveva nel gate reale."""
    fake_gate = tmp_path / "gate.json"
    monkeypatch.setattr(bp, "FAN_FILE", fake_gate)
    snap = bp.fan_snapshot(tmp_path)
    snap["fan_rpm"] = 1800
    snap["gate"]["verified"] = True
    bp.write_fan_verification(snap)
    assert fake_gate.is_file()
    assert bp.read_stored_fan()["valid"] is True


def test_docstring_dichiara_niente_valori_cli():
    src = (ROOT / "tools" / "blocker_probe.py").read_text(encoding="utf-8")
    assert "Nessun valore può essere passato come argomento CLI" in src
    assert "--attest-rpm" in src
    assert "temperatura" in src
