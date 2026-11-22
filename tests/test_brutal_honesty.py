"""
test_brutal_honesty.py — Cycle 100: il report dice la verità dai dati reali.

Nessun LLM, rete o GPU: legge pyflakes, TOML, corpus e documenti locali.
"""
from __future__ import annotations

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
