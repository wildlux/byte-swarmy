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
    assert "python-version: \"3.14\"" in text
    assert "runs-on: ubuntu-latest" in text


def test_trigger_push_su_main_per_sbloccare_m2_m6():
    """Il trigger manuale richiede gh+auth: il push esegue la suite su CI."""
    text = _text()
    assert "push:" in text
    assert "branches: [main]" in text
    # La diagnostica deve restare nel log pubblico, non solo nell'artifact.
    assert "tail -60 collect.log" in text
    assert "tail -80 pytest_profile.log" in text


def test_errore_collezione_esposto_in_annotations_pubbliche():
    """Senza auth il log è privato: le annotations sono leggibili via API."""
    text = _text()
    assert "::error title=collect_exit::EXIT=$code" in text
    assert 'echo "::error::${line}"' in text
    assert "check-runs/{id}/annotations" in text


def test_fallimento_suite_esposto_in_annotations_pubbliche():
    """Cycle 126: EXIT=1 della suite deve mostrare i FAILED senza auth."""
    text = _text()
    assert "::error title=pytest_exit::EXIT=$code" in text
    assert "grep -E '^FAILED ' pytest_profile.log" in text
    assert "tail -20 pytest_profile.log" in text


def test_librerie_qt_headless_installate_sul_runner():
    """Run #4: EXIT=2 per `ImportError: libEGL.so.1` in PyQt6.QtWidgets."""
    text = _text()
    assert "Librerie di sistema per Qt headless (libEGL)" in text
    assert "libegl1" in text
    assert "sudo apt-get install -y --no-install-recommends" in text
    # Deve essere prima della collezione, altrimenti l'import fallisce ancora.
    assert text.index("libegl1") < text.index("Diagnostica collezione")


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
