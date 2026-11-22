"""test_slot_prompt.py — SLOT-4: prompt per-slot, preparazione offline.

Nessun LLM, rete o GPU: i prompt sono generati dal piano deterministico.
I test bloccano isolamento delle refs, fail-closed sui piani rifiutati e
dichiarazione esplicita che il benchmark reale resta bloccato.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.slot_planner import plan_slots  # noqa: E402
import tools.slot_prompt as sp  # noqa: E402


def test_un_prompt_per_slot_con_refs_isolate():
    plan = plan_slots("finestra con titolo")
    assert plan.ok and len(plan.slots) == 2
    prompts = sp.build_all_prompts(plan)
    assert len(prompts) == 2
    assert "`TITLE`" in prompts[0] and "`WIDTH`" not in prompts[0]
    assert "`WIDTH`" in prompts[1] and "`TITLE`" not in prompts[1]
    assert "impostare il titolo della finestra" in prompts[0]
    assert "impostare larghezza e altezza iniziali" in prompts[1]


def test_anchor_reale_e_regole_output_piccolo():
    plan = plan_slots("finestra con titolo")
    text = sp.build_slot_prompt(plan, 0)
    assert "# SLOT: titolo della finestra" in text
    assert "Massimo 40 righe, nessuna spiegazione" in text
    assert "Rispondi SOLO con il codice di questo slot (statement)" in text
    assert "Le ref degli altri slot non sono incluse" in text
    assert "`WIDTH`" not in text  # nessuna ref di altri slot, nemmeno in nota


def test_piano_rifiutato_non_genera_prompt():
    plan = plan_slots("fai qualcosa di ambiguo con layout e finestra")
    assert plan.rejected
    with pytest.raises(ValueError) as exc:
        sp.build_slot_prompt(plan, 0)
    assert "piano rifiutato" in str(exc.value)


def test_indice_fuori_range():
    plan = plan_slots("thread in background")
    with pytest.raises(ValueError) as exc:
        sp.build_slot_prompt(plan, 5)
    assert "fuori range" in str(exc.value)


def test_determinismo_e_report():
    plan = plan_slots("widget con layout e pulsante")
    data = sp.report(plan)
    assert data["slot_count"] == 2
    assert [p["kind"] for p in data["prompts"]] == ["statement", "statement"]
    assert sp.report(plan) == data
    assert sp.build_all_prompts(plan) == [p["text"] for p in data["prompts"]]


def test_markdown_dichiara_benchmark_bloccato(tmp_path):
    data = sp.report(plan_slots("finestra con titolo"))
    text = sp.markdown(data)
    assert "Nessun modello è stato chiamato" in text
    assert "benchmark con 3 task reali resta 🔒 termico" in text
    assert "## Prompt 1" in text and "## Prompt 2" in text
    assert "```text" in text


def test_cli_json_e_rifiuto(capsys):
    assert sp.main(["--task", "finestra con titolo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["slot_count"] == 2
    assert len(payload["prompts"]) == 2

    assert sp.main(["--task", "fai qualcosa con layout e finestra"]) == 1
    assert "RIFIUTATO" in capsys.readouterr().err


def test_cli_scrive_file(tmp_path, capsys):
    out = tmp_path / "prompts.md"
    assert sp.main(["--task", "thread in background", "--out", str(out)]) == 0
    assert out.is_file()
    assert "# SLOT-4" in out.read_text(encoding="utf-8")


def test_modulo_non_importa_client_llm():
    src = (ROOT / "tools" / "slot_prompt.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response"):
        assert forbidden not in src
