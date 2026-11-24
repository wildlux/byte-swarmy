"""
test_brutal_honesty.py — Cycle 100: il report dice la verità dai dati reali.

Nessun LLM, rete o GPU: legge pyflakes, TOML, corpus e documenti locali.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import brutal_honesty_report as bh  # noqa: E402


def test_report_deterministico():
    first = bh.markdown(bh.collect_all())
    second = bh.markdown(bh.collect_all())
    assert first == second
    assert "zero LLM, zero rete, zero GPU, zero timestamp" in first
    assert "Verdetto sintetico" in first
    assert "Da dove viene il 0.958" in first


def test_pyflakes_conteggio_viene_dal_gate_reale():
    snap = bh.collect_all()
    pf = snap["pyflakes"]
    assert pf["available"] is True, pf
    text = bh.markdown(snap)
    assert f"{pf['findings']} finding di pyflakes" in text
    for line in pf["undefined"][:2]:
        assert line in text


def test_config_letto_dal_toml_vero():
    snap = bh.config_snapshot()
    assert isinstance(snap["fast_lane_enabled"], bool)
    assert snap["best_of_n"] >= 1
    text = bh.markdown(bh.collect_all())
    assert (f"`fast_lane.enabled="
            f"{str(snap['fast_lane_enabled']).lower()}`") in text
    assert f"`best_of_n={snap['best_of_n']}`" in text


def test_corpus_con_caveat_e_provenienza():
    snap = bh.corpus_snapshot()
    assert snap["total"] >= snap["unique"] >= snap["tasks"]
    text = bh.markdown(bh.collect_all())
    assert "fixture interne" in text
    assert f"{snap['tasks']} task distinti" in text
    assert "Copertura retrieval" in text


def test_documenti_sono_stati_realmente_corretti():
    docs = bh.docs_snapshot()
    assert all(docs.values()), docs


def test_modulo_non_importa_client_llm():
    src = (ROOT / "tools" / "brutal_honesty_report.py").read_text(
        encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response"):
        assert forbidden not in src


def _live_file(tmp_path: Path, *, fan_rpm: int = 2400,
               aborted: bool = False) -> Path:
    from tools import eval_by_slot as es

    cases = es.load_cases()
    records = [{
        "case_id": c["id"],
        "slot_kind": es.classify(c),
        "output_lines": 10,
        "passed": i % 2 == 0,
    } for i, c in enumerate(cases)]
    payload = {
        "source": "live",
        "thermal": {"fan_rpm": fan_rpm, "temp_c": 58.3,
                    "temp_max_c": 60.0},
        "records": records,
        "aborted": aborted,
    }
    path = tmp_path / "eval_live_results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_live_snapshot_accetta_solo_evidenza_termica(tmp_path):
    ok = bh.live_snapshot(_live_file(tmp_path))
    assert ok["accepted"] is True
    assert ok["cases"] >= 10
    assert ok["passed"] > 0

    rejected = bh.live_snapshot(_live_file(tmp_path / "sub", fan_rpm=0))
    assert rejected["accepted"] is False
    assert "nessun surrogato" in rejected["reason"]

    aborted = bh.live_snapshot(
        _live_file(tmp_path / "abort", aborted=True))
    assert aborted["accepted"] is False
    assert aborted["aborted"] is True


def test_report_racconta_live_misurato_o_non_misurato(tmp_path):
    snap = bh.collect_all()
    snap["live"] = bh.live_snapshot(_live_file(tmp_path))
    text = bh.markdown(snap)
    assert "Pass@1 live (SLOT-5)" in text
    assert "Il task GUI live è **misurato**" in text
    assert "E3 live è misurato" in text

    snap["live"] = bh.live_snapshot(_live_file(tmp_path / "sub", fan_rpm=0))
    text = bh.markdown(snap)
    assert "Il task GUI live resta 🔒 non misurato." in text
