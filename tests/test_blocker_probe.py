"""
test_blocker_probe.py — sonde M2-M6: mai un dato inventato, mai una suite
completa locale. I valori sintetici qui sotto servono solo a testare i parsers.
"""
from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import blocker_probe as bp  # noqa: E402


def test_parse_nbfc_rpm():
    assert bp.parse_nbfc_rpm("Fan 1: 3200 RPM\nFan 2: 2800 RPM") == 3200
    assert bp.parse_nbfc_rpm("ERROR: connect(): No such file or directory") == 0
    assert bp.parse_nbfc_rpm("") == 0


def test_parse_nbfc_formato_053_senza_unita_rpm():
    text = ("Current Fan Speed        : 0.00\n"
            "Target Fan Speed         : 100.00\n")
    assert bp.parse_nbfc_rpm(text) == 0
    assert bp.parse_nbfc_duty(text) == 100.0
    assert bp.parse_nbfc_rpm("Current Fan Speed : 3200.00") == 3200
    assert bp.parse_nbfc_duty("nessun dato") is None


def test_parse_hwmon_temp():
    assert bp.parse_hwmon_temp("53000\n") == 53.0
    assert bp.parse_hwmon_temp("N/A") == 0.0
    assert bp.parse_hwmon_temp("") == 0.0


def test_gate_false_senza_rpm_reale(monkeypatch, tmp_path):
    monkeypatch.setattr(bp, "read_cpu_temp_c", lambda base: (53.0, "fixture"))
    monkeypatch.setattr(bp, "nbfc_probe", lambda: {
        "rpm": 0, "rpm_source": None,
        "service_state": "inactive", "detail": "nbfc non risponde",
    })
    monkeypatch.setattr(bp, "read_pwm", lambda base: [])
    snap = bp.fan_snapshot(tmp_path)
    assert snap["gate"]["verified"] is False
    assert snap["gate"]["temp_entro_60c"] is True
    assert snap["gate"]["fan_rpm_positivo"] is False
    assert snap["misure_inventate"] is False


def test_gate_false_se_temperatura_sopra_soglia(monkeypatch, tmp_path):
    monkeypatch.setattr(bp, "read_cpu_temp_c", lambda base: (71.0, "fixture"))
    monkeypatch.setattr(bp, "nbfc_probe", lambda: {
        "rpm": 3200, "rpm_source": "fixture",
        "service_state": "running", "detail": "ok",
    })
    monkeypatch.setattr(bp, "read_pwm", lambda base: [])
    assert bp.fan_snapshot(tmp_path)["gate"]["verified"] is False


def test_scrittura_rifiutata_se_gate_non_verificato(tmp_path):
    snap = {"gate": {"verified": False}, "fan_rpm": 0, "cpu_temp_c": 53.0}
    with pytest.raises(ValueError, match="Rifiutato"):
        bp.write_fan_verification(snap, tmp_path / "fan.json")
    assert not (tmp_path / "fan.json").exists()


def test_scrittura_solo_con_provenienza_e_permessi_0600(tmp_path):
    snap = {
        "gate": {"verified": True}, "fan_rpm": 3200, "cpu_temp_c": 53.0,
        "temp_source": "fixture", "rpm_source": "fixture",
        "nbfc_service_state": "running",
    }
    path = bp.write_fan_verification(snap, tmp_path / "fan.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["fan_rpm"] == 3200
    assert data["temp_c"] == 53.0
    assert data["measured_at"]
    assert data["sources"]["temperature"] == "fixture"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert bp.read_stored_fan(path)["valid"] is True


def test_gate_salvato_senza_provenienza_non_e_valido(tmp_path):
    path = tmp_path / "fan.json"
    path.write_text(json.dumps({"fan_rpm": 3200, "temp_c": 53.0}),
                    encoding="utf-8")
    result = bp.read_stored_fan(path)
    assert result["valid"] is False
    assert result["checks"]["provenienza"] is False


def test_remote_token_rilevato_e_maskato():
    assert bp.mask_remote("https://SEGRETO@github.com/x/y.git") == \
        "https://***@github.com/x/y.git"
    assert bp.remote_token_free("git@github.com:x/y.git") is True
    assert bp.remote_token_free("https://SEGRETO@github.com/x/y.git") is False


def test_gh_health_rileva_interprete_shebang_assente(tmp_path):
    fake = tmp_path / "gh"
    fake.write_text("#!/usr/local/bin/python3.14\nimport os\n", encoding="utf-8")
    health = bp.gh_health(str(fake))
    assert health["ok"] is False
    assert "/usr/local/bin/python3.14" in health["reason"]


def test_gh_health_non_confonde_script_browser_con_cli(tmp_path):
    fake = tmp_path / "gh"
    fake.write_text(
        "#!/usr/bin/python3\n# Open your Github project in a browser\n",
        encoding="utf-8")
    health = bp.gh_health(str(fake))
    assert health["ok"] is False
    assert health["kind"] == "script-browser"
    assert health["install_hint"] == "sudo apt install gh"


def test_nbfc_probe_controlla_l_unita_giusta(monkeypatch):
    calls = []

    def fake_cmd(argv, timeout=8):
        calls.append(argv)
        return "active\n" if "is-active" in argv else ""

    monkeypatch.setattr(bp, "_cmd", fake_cmd)
    result = bp.nbfc_probe()
    assert ["systemctl", "is-active", "nbfc_service"] in calls
    assert result["service_state"] == "active"


def test_report_deterministico_e_dichiara_i_blocchi():
    first = bp.collect(base=Path("/sys/non-esiste"), repo=ROOT)
    second = bp.collect(base=Path("/sys/non-esiste"), repo=ROOT)
    first["generated_at"] = second["generated_at"] = "FISSO"
    assert bp.markdown(first) == bp.markdown(second)
    text = bp.markdown(first)
    for marker in ("M2 suite completa", "M3 ventole", "M4 credenziali",
                   "M5 hardening", "M6 profiling CI",
                   "Nessun asse del radar", "Nessun valore",
                   "NON dimostra", "misurare RPM con strumento esterno"):
        assert marker in text
    assert "avviare nbfc con pkexec" not in text
