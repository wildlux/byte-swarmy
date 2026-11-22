"""test_eval_by_slot.py — SLOT-5: reporter per-slot, preparazione offline.

Nessun LLM, rete o GPU: i risultati sono sintetici e il live richiede un file
con evidenza termica verificata. I test bloccano classificazione, aggregazione,
rifiuto dei surrogati e dichiarazione di SIMULAZIONE nel report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.eval_by_slot as es  # noqa: E402


def test_classificazione_deterministica_dalla_eval_suite():
    cases = es.load_cases()
    by_id = {c["id"]: es.classify(c) for c in cases}
    assert by_id["eval-slot-01"] == "function"
    assert by_id["eval-arch-01"] == "class"
    assert by_id["eval-gui-03"] == "widget"
    assert by_id["eval-minimal-02"] == "function"
    assert set(by_id.values()) <= set(es.SLOT_KINDS)
    assert len(cases) == 11  # 2 casi gate/chiarimento esclusi


def test_size_bucket():
    assert es.size_bucket(0) == "small"
    assert es.size_bucket(40) == "small"
    assert es.size_bucket(41) == "medium"
    assert es.size_bucket(120) == "medium"
    assert es.size_bucket(121) == "large"
    assert es.size_bucket(500) == "large"


def test_sintesi_per_slot_e_dimensione():
    data = {
        "records": [
            {"case_id": "a", "slot_kind": "function", "output_lines": 10,
             "passed": True},
            {"case_id": "b", "slot_kind": "function", "output_lines": 200,
             "passed": False},
            {"case_id": "c", "slot_kind": "widget", "output_lines": 50,
             "passed": True},
        ]
    }
    s = es.summarize(data)
    assert s["total"] == 3
    assert s["by_slot"]["function"] == {"passed": 1, "total": 2,
                                        "rate": 0.5}
    assert s["by_slot"]["widget"]["rate"] == 1.0
    assert s["by_size"]["small"]["total"] == 1
    assert s["by_size"]["large"]["passed"] == 0
    assert s["by_size"]["medium"]["total"] == 1


def test_simulazione_e_deterministica_e_non_chiude_slot5():
    cases = es.load_cases()
    a = es.synthetic_results(cases)
    b = es.synthetic_results(cases)
    assert a == b
    assert a["source"] == "simulation"
    text = es.markdown(a, es.summarize(a), False)
    assert "SIMULAZIONE" in text
    assert "non è una misura" in text
    assert "non chiude SLOT-5" in text
    assert "12+ casi reali" in text
    assert "1000000000" not in text  # range large leggibile


def test_gate_termico_rifiuta_live_senza_evidenza(tmp_path):
    cases = es.load_cases()
    path = tmp_path / "results.json"
    records = [{"case_id": cases[0]["id"], "slot_kind": "function",
                "output_lines": 10, "passed": True}]
    for source, thermal in (("live", None),
                            ("live", {"fan_rpm": 0, "temp_c": 40}),
                            ("live", {"fan_rpm": 1800, "temp_c": 75}),
                            ("sconosciuta", {"fan_rpm": 1800, "temp_c": 40})):
        path.write_text(json.dumps({"source": source, "thermal": thermal,
                                    "records": records}), encoding="utf-8")
        with pytest.raises(ValueError) as exc:
            es.load_results(path, cases)
        assert "surrogato" in str(exc) or "source deve essere" in str(exc)

    path.write_text(json.dumps({
        "source": "live", "thermal": {"fan_rpm": 1800, "temp_c": 50},
        "records": records}), encoding="utf-8")
    data, live = es.load_results(path, cases)
    assert live is True and data["source"] == "live"


def test_results_con_casi_sconosciuti_o_campi_mancanti_sono_rifiutati(tmp_path):
    cases = es.load_cases()
    path = tmp_path / "bad.json"
    bad = [
        {"source": "simulation", "records": [{
            "case_id": "inesistente", "slot_kind": "function",
            "output_lines": 10, "passed": True}]},
        {"source": "simulation", "records": [{
            "case_id": cases[0]["id"], "slot_kind": "inventato",
            "output_lines": 10, "passed": True}]},
        {"source": "simulation", "records": [{
            "case_id": cases[0]["id"], "slot_kind": "function",
            "output_lines": 10}]},
    ]
    for payload in bad:
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            es.load_results(path, cases)


def test_cli_json_e_blocco_live(tmp_path, capsys):
    assert es.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["live"] is False
    assert payload["summary"]["total"] == 11

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"source": "live", "records": []}),
                   encoding="utf-8")
    assert es.main(["--results", str(bad)]) == 2
    assert "RIFIUTATO" in capsys.readouterr().err


def test_report_deterministico_e_live_non_dichiara_simulazione():
    data = es.synthetic_results(es.load_cases())
    summary = es.summarize(data)
    assert es.markdown(data, summary, False) == es.markdown(data, summary,
                                                           False)
    live_text = es.markdown(data, summary, True)
    assert "Modalità: **LIVE**" in live_text
    assert "SIMULAZIONE" not in live_text


def test_modulo_non_importa_client_llm():
    src = (ROOT / "tools" / "eval_by_slot.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response"):
        assert forbidden not in src
