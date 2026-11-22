"""
test_memory_ab.py — E4: harness A/B memoria/contesto, preparazione offline.
Nessun LLM, rete o GPU: solver e retriever sono finti; il live resta bloccato.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.memory_ab as ab  # noqa: E402


def test_task_set_congelato():
    assert len(ab.TASK_SET) == 10
    ids = [t["id"] for t in ab.TASK_SET]
    assert len(set(ids)) == 10
    digest = hashlib.sha256(
        json.dumps(ab.TASK_SET, sort_keys=True).encode()).hexdigest()[:12]
    assert digest == ab.TASK_SET_ID


def test_soglie_go_no_go_inconclusive():
    assert ab.verdict(0.60, 0.40) == "GO"
    assert ab.verdict(0.40, 0.50) == "NO-GO"
    assert ab.verdict(0.40, 0.30) == "INCONCLUSIVE"


def test_dry_run_usato_solleva():
    result = ab.run_ab()
    assert result["live"] is False
    assert len(result["tasks"]) == 20  # 10 task x 2 bracci
    assert result["arms"]["with_context"].total == 10
    assert result["arms"]["without_context"].total == 10
    assert result["delta"] > 0
    assert result["verdict"] == "GO"  # verdetto del solo harness finto


def test_retriever_finto_non_da_risposta_ai_task_non_aided():
    r = ab.FakeRetriever()
    aided = r.context_for(ab.TASK_SET[0])
    plain = r.context_for(ab.TASK_SET[-1])
    assert "RISPOSTA:" in aided
    assert "RISPOSTA:" not in plain


def test_gate_termico_blocca_live_senza_verifica(tmp_path, monkeypatch):
    monkeypatch.setattr(ab, "FAN_FILE", tmp_path / "assente.json")
    assert ab.thermal_gate_ok(False) is True  # dry-run sempre ammesso
    assert ab.thermal_gate_ok(True) is False
    try:
        ab.run_ab(live=True)
    except RuntimeError as e:
        assert "ventole" in str(e)
    else:
        raise AssertionError("live non bloccato")


def test_gate_termico_accetta_solo_ventole_e_temperatura_verificate(tmp_path, monkeypatch):
    path = tmp_path / "fan.json"
    monkeypatch.setattr(ab, "FAN_FILE", path)
    path.write_text(json.dumps({"fan_rpm": 0, "temp_c": 40}), encoding="utf-8")
    assert ab.thermal_gate_ok(True) is False
    path.write_text(json.dumps({"fan_rpm": 1800, "temp_c": 75}), encoding="utf-8")
    assert ab.thermal_gate_ok(True) is False
    path.write_text(json.dumps({"fan_rpm": 1800, "temp_c": 55}), encoding="utf-8")
    assert ab.thermal_gate_ok(True) is True


def test_report_deterministico_e_dichiara_non_reale():
    a = ab.markdown(ab.run_ab())
    b = ab.markdown(ab.run_ab())
    assert a == b
    assert "DRY-RUN" in a
    assert "NON è un verdetto reale" in a
    assert "0.60" in a and "0.20" in a
    assert "mem-10" in a
    assert "simulato" in a


def test_modulo_non_importa_client_llm():
    src = (ROOT / "tools" / "memory_ab.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response"):
        assert forbidden not in src
