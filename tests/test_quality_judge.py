"""test_quality_judge.py — Fase H: giudice mai sovrano, preparazione offline.

Nessun LLM, rete o GPU. I test bloccano l'invariante di non-sovranità in ogni
direzione, il blocco degli override, il gate termico sui pareri live, la
validazione dei record e l'onestà del report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.quality_judge as qj  # noqa: E402


@pytest.mark.parametrize("gate,judge", [
    (True, None), (True, "approve"), (True, "reject"),
    (False, None), (False, "approve"), (False, "reject"),
])
def test_giudice_non_e_mai_sovrano(gate, judge):
    r = qj.adjudicate("c1", gate, judge)
    assert r["final"] is gate, (gate, judge, r)


@pytest.mark.parametrize("gate,judge,expected", [
    (True, None, "not_consulted"),
    (True, "approve", "concur_pass"),
    (True, "reject", "judge_dissent"),
    (False, None, "not_consulted"),
    (False, "approve", "judge_ignored_gate_fail"),
    (False, "reject", "judge_ignored_gate_fail"),
])
def test_classificazione_accordo(gate, judge, expected):
    assert qj.adjudicate("c1", gate, judge)["agreement"] == expected


def test_override_bloccato_e_segnalato_mai_applicato():
    r = qj.adjudicate("c1", False, "approve", override=True)
    assert r["final"] is False
    assert r["override_requested"] is True
    assert r["override_blocked"] is True
    r2 = qj.adjudicate("c1", True, "reject", override=True)
    assert r2["final"] is True and r2["override_blocked"] is True


def test_verdetto_gudice_sconosciuto_rifiutato():
    with pytest.raises(ValueError) as exc:
        qj.adjudicate("c1", True, "maybe")
    assert "sconosciuto" in str(exc.value)


def test_gate_termico_rifiuta_pareri_live_senza_evidenza(tmp_path):
    cases = qj.load_cases()
    records = [{"case_id": cases[0]["id"], "gate_pass": True,
                "judge": "approve"}]
    path = tmp_path / "results.json"
    for thermal in (None, {"fan_rpm": 0, "temp_c": 40},
                    {"fan_rpm": 1800, "temp_c": 75}):
        path.write_text(json.dumps({"source": "live", "thermal": thermal,
                                    "records": records}), encoding="utf-8")
        with pytest.raises(ValueError) as exc:
            qj.load_results(path, cases)
        assert "surrogato" in str(exc.value) or "fan_rpm" in str(exc.value)
    assert qj.thermal_ok({"fan_rpm": 1800, "temp_c": 50}) is True
    assert qj.thermal_ok({"fan_rpm": "1800", "temp_c": "50"}) is True
    assert qj.thermal_ok({"fan_rpm": "x", "temp_c": 50}) is False


def test_record_non_validi_rifiutati(tmp_path):
    cases = qj.load_cases()
    path = tmp_path / "bad.json"
    bad = [
        {"source": "simulation", "records": [
            {"case_id": "inesistente", "gate_pass": True}]},
        {"source": "simulation", "records": [
            {"case_id": cases[0]["id"], "gate_pass": True,
             "judge": "boh"}]},
        {"source": "sconosciuta", "records": []},
        {"source": "simulation", "records": "non-lista"},
    ]
    for payload in bad:
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            qj.load_results(path, cases)


def test_live_accettato_con_evidenza_e_finale_invariato(tmp_path):
    cases = qj.load_cases()
    path = tmp_path / "live.json"
    path.write_text(json.dumps({
        "source": "live",
        "thermal": {"fan_rpm": 1800, "temp_c": 50},
        "records": [
            {"case_id": cases[0]["id"], "gate_pass": True,
             "judge": "reject", "override": True},
            {"case_id": cases[1]["id"], "gate_pass": False,
             "judge": "approve"},
        ]}), encoding="utf-8")
    data, live = qj.load_results(path, cases)
    assert live is True
    summary = qj.summarize(data)
    assert summary["override_bloccati"] == 1
    assert summary["gate_invariato"] is True
    assert [r["final"] for r in data["records"]] == [True, False]


def test_simulazione_deterministica_e_non_chiude_fase_h():
    cases = qj.load_cases()
    a = qj.synthetic_results(cases)
    assert a == qj.synthetic_results(cases)
    assert a["source"] == "simulation"
    text = qj.markdown(a, qj.summarize(a), False)
    assert "SIMULAZIONE" in text
    assert "non è una misura" in text
    assert "non chiude Fase H" in text
    assert "20 casi reali" in text


def test_report_live_non_dichiara_simulazione():
    data = qj.synthetic_results(qj.load_cases())
    text = qj.markdown(data, qj.summarize(data), True)
    assert "Modalità: **LIVE**" in text
    assert "SIMULAZIONE" not in text
    assert "Gate invariato | True" in text


def test_cli_json_e_blocco_live(tmp_path, capsys):
    assert qj.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["live"] is False
    assert payload["summary"]["totali"] == 13

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"source": "live", "records": []}),
                   encoding="utf-8")
    assert qj.main(["--results", str(bad)]) == 2
    assert "RIFIUTATO" in capsys.readouterr().err


def test_modulo_non_importa_client_llm():
    src = (ROOT / "tools" / "quality_judge.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response", "Timestral("):
        assert forbidden not in src
