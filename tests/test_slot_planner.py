"""test_slot_planner.py — planner a slot deterministico (SLOT-3 / P2-3).

Zero LLM, rete o GUI: verifica classificazione, fail-closed, refs reali e
integrazione con il gate per-slot. Nessun file di progetto scritto.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.slot_gate import ALLOWED_KINDS, gate_slot  # noqa: E402
from CORE.slot_planner import (  # noqa: E402
    TEMPLATE_DIR,
    SlotPlan,
    SlotSpec,
    _markers,
    plan_slots,
)


def test_classificazione_deterministica():
    task = "crea una finestra con titolo e dimensioni"
    first = plan_slots(task)
    second = plan_slots(task)
    assert first == second
    assert first.ok
    assert first.template == "finestra.py.tpl"
    assert [s.anchor for s in first.slots] == ["titolo", "dimensioni"]
    assert all(s.kind in ALLOWED_KINDS for s in first.slots)


def test_tutti_i_template_hanno_un_piano():
    tasks = {
        "finestra.py.tpl": "finestra di dialogo",
        "layout.py.tpl": "form con etichetta e pulsanti",
        "segnali.py.tpl": "aggiornamento live con segnali",
        "thread.py.tpl": "worker in background con QThread",
    }
    for name, task in tasks.items():
        plan = plan_slots(task)
        assert plan.ok, (name, plan.reason)
        assert plan.template == name
        assert len(plan.slots) == len(_markers(
            (TEMPLATE_DIR / name).read_text(encoding="utf-8")))


def test_fail_closed_su_task_vuoto_o_sconosciuto():
    for task in ("", "   ", "scrivi un romanzo fantasy"):
        plan = plan_slots(task)
        assert plan.rejected
        assert plan.slots == ()
        assert plan.reason
        assert not plan.ok


def test_fail_closed_su_template_ambiguo():
    plan = plan_slots("finestra layout")
    assert plan.rejected
    assert "ambiguo" in plan.reason


def test_refs_sono_nomi_reali_del_template():
    for task in ("finestra", "form con pulsanti", "segnali live",
                 "thread worker"):
        plan = plan_slots(task)
        source = (TEMPLATE_DIR / plan.template).read_text(encoding="utf-8")
        for slot in plan.slots:
            for ref in slot.refs:
                assert ref in source, (slot.anchor, ref)


def test_gate_per_slot_accetta_frammento_con_le_refs_dichiarate():
    plan = plan_slots("finestra con titolo")
    titolo = plan.slots[0]
    verdict = gate_slot('TITLE = "Nuovo"', refs=titolo.refs, kind=titolo.kind)
    assert verdict.ok, verdict.detail()
    bad = gate_slot('TITLE = ALTRO', refs=titolo.refs, kind=titolo.kind)
    assert not bad.ok


def test_markdown_e_json_sono_deterministici():
    plan = plan_slots("finestra")
    assert plan.to_markdown() == plan_slots("finestra").to_markdown()
    assert plan.to_dict() == plan_slots("finestra").to_dict()
    assert "| `titolo`" in plan.to_markdown()
    assert plan.to_dict()["rejected"] is False

    rejected = SlotPlan("x", None, (), True, "motivo")
    assert "RIFIUTATO" in rejected.to_markdown()
    assert rejected.to_dict()["slots"] == []


def test_slot_spec_non_ha_campi_liberi():
    slot = SlotSpec("a", "function", "marker", ("X",), "istruzione", "test_x")
    assert slot.to_dict() == {
        "anchor": "a", "kind": "function", "marker": "marker",
        "refs": ["X"], "instruction": "istruzione", "test": "test_x"}
