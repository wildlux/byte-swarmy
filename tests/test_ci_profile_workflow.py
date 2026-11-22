"""test_ci_profile_workflow.py — lock offline del workflow di profilazione CI.

Verifica che `.github/workflows/profile.yml` contenga le difese aggiunte dopo
il fallimento del run #2 (2026-11-20): pausa e2e, diagnostica di collezione,
profilazione con --durations=0 e upload di entrambi i log. Nessun trigger,
nessuna rete, nessun LLM: solo lettura del file committato.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "profile.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_presente_e_manuale():
    text = _text()
    assert "workflow_dispatch" in text
    assert "python-version: \"3.11\"" in text
    assert "runs-on: ubuntu-latest" in text


def test_pausa_live_e2e():
    assert "touch state/pause.flag" in _text()


def test_diagnostica_collezione_presente():
    text = _text()
    assert "Diagnostica collezione (--collect-only)" in text
    assert "pytest tests/ --collect-only -q -p no:cacheprovider" in text
    assert "collect.log" in text


def test_profilazione_completa_con_durations():
    text = _text()
    assert "Profilazione completa (--durations=0)" in text
    assert "--durations=0" in text
    assert "timeout 3300 python -m pytest tests/" in text
    assert "QT_QPA_PLATFORM: offscreen" in text


def test_artifact_carica_entrambi_i_log():
    text = _text()
    assert "name: pytest-profile" in text
    assert "pytest_profile.log" in text
    assert "collect.log" in text
    assert "if: always()" in text
