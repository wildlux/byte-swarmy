"""test_prompt_variants.py — Fase G: A/B varianti prompt, preparazione offline.

Nessun LLM, rete o GPU: il solver è finto e il live resta bloccato dal gate
termico. I test bloccano il task set congelato, la regola di promozione e
l'onestà del report (SIMULAZIONE non vale verdetto reale).
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.eval_prompt_variants as pv  # noqa: E402


def test_task_set_congelato_dalla_eval_suite():
    cases = pv.load_cases()
    assert len(cases) == 11
    assert len({c.id for c in cases}) == 11
    assert pv.task_set_id(cases) == "182ae2a82284"
    assert all(c.marker for c in cases)


def test_varianti_dichiarate_e_prompt_deterministico():
    case = pv.load_cases()[0]
    assert pv.VARIANTS == ("baseline", "refs_off", "refs_first",
                           "plan_compact")
    assert pv.make_prompt(case, "baseline") == pv.make_prompt(case, "baseline")
    assert "REFS:" not in pv.make_prompt(case, "refs_off")
    assert "REFS:" in pv.make_prompt(case, "refs_first")
    assert "1 azione per turno" in pv.make_prompt(case, "plan_compact")


def test_soglia_promozione_solo_con_margine_e_tasso():
    assert pv.verdict(0.80, 0.40) == "PROMOTE"   # delta 0.40, rate 0.80
    assert pv.verdict(0.60, 0.40) == "PROMOTE"   # esattamente alle soglie
    assert pv.verdict(0.45, 0.25) == "INCONCLUSIVE"  # delta ok, rate no
    assert pv.verdict(0.70, 0.60) == "INCONCLUSIVE"  # rate ok, delta no
    assert pv.verdict(0.30, 0.50) == "REJECT"
    assert pv.verdict(0.50, 0.50) == "REJECT"


def test_dry_run_non_promuove_nulla_e_e_deterministico():
    a = pv.run_ab()
    b = pv.run_ab()
    assert a == b
    assert a["live"] is False and a["simulation"] is True
    assert set(a["arms"]) == set(pv.VARIANTS)
    assert all(row["verdict"] != "PROMOTE" for row in a["confronti"].values())
    assert any(row["verdict"] == "REJECT" for row in a["confronti"].values())
    assert any(row["verdict"] == "INCONCLUSIVE"
               for row in a["confronti"].values())


def test_gate_termico_blocca_live(tmp_path, monkeypatch):
    monkeypatch.setattr(pv, "FAN_FILE", tmp_path / "assente.json")
    assert pv.thermal_gate_ok(False) is True
    assert pv.thermal_gate_ok(True) is False
    try:
        pv.run_ab(live=True)
    except RuntimeError as exc:
        assert "fan_verified.json" in str(exc)
    else:
        raise AssertionError("live non bloccato")

    path = tmp_path / "fan.json"
    monkeypatch.setattr(pv, "FAN_FILE", path)
    for fan, temp, ok in ((0, 40, False), (1800, 75, False),
                          (1800, 55, True)):
        path.write_text(json.dumps({"fan_rpm": fan, "temp_c": temp}),
                        encoding="utf-8")
        assert pv.thermal_gate_ok(True) is ok


def test_live_con_gate_verde_richiede_solver_reale(tmp_path, monkeypatch):
    path = tmp_path / "fan.json"
    path.write_text(json.dumps({"fan_rpm": 1800, "temp_c": 50}),
                    encoding="utf-8")
    monkeypatch.setattr(pv, "FAN_FILE", path)
    try:
        pv.run_ab(live=True)
    except RuntimeError as exc:
        assert "solver reale" in str(exc)
    else:
        raise AssertionError("solver finto accettato nel live")
    result = pv.run_ab(live=True, solver=lambda prompt: "OK")
    assert result["live"] is True and result["simulation"] is False


def test_report_dichiara_simulazione_e_non_autorizza_promozione():
    text = pv.markdown(pv.run_ab())
    assert "SIMULAZIONE" in text
    assert "NON è un esperimento reale" in text
    assert "non autorizza alcuna promozione" in text
    assert "182ae2a82284" in text
    assert "0.60" in text and "0.20" in text
    assert pv.markdown(pv.run_ab()) == text


def test_cli_json_deterministico_e_blocco_live():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        rc = pv.main(["--json"])
    assert rc == 0
    payload = json.loads(buffer.getvalue())
    assert payload["simulation"] is True
    assert payload["task_set_id"] == "182ae2a82284"


def test_modulo_non_importa_client_llm():
    src = (ROOT / "tools" / "eval_prompt_variants.py").read_text(
        encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response"):
        assert forbidden not in src
