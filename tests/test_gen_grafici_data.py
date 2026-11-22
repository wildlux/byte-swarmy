"""
test_gen_grafici_data.py — il grafico "miglioramenti" è data-driven.
Nessun LLM, GUI o rete: controlla che rigenerare dopo un cambio docs
produca un SVG diverso (e che i valori derivino dai documenti).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import gen_grafici as g  # noqa: E402


def test_ciclo_e_meccanismi_derivano_dai_doc():
    assert g.latest_cycle() >= 94
    assert g.mechanism_count() >= 37


def test_svg_contiene_i_valori_derivati():
    svg = g.build_svg()
    assert f"Cycle 70 → {g.latest_cycle()}" in svg
    assert f"dei {g.mechanism_count()} meccanismi" in svg
    assert f"oggi (Cycle {g.latest_cycle()})" in svg


def test_rigenerazione_deterministica():
    assert g.build_svg() == g.build_svg()
