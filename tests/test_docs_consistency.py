"""
test_docs_consistency.py — C1: le regole scritte devono combaciare col codice.

Controlli puramente testuali/filesystem: nessun LLM, rete o scrittura.
Protegge le quattro correzioni del Cycle 91: MAX_STEPS, baseline security,
duplicate GUI/IMPLEMENTED, symlink state → data/state.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AGENT = ROOT / "AGENT.md"
SPEC = ROOT / "DOCS" / "SPECIFICATIONS.md"
VERIFY = ROOT / "tools" / "verify_cycle.sh"
GUI_LOG = ROOT / "GUI" / "IMPLEMENTED.md"
CANONICAL_LOG = ROOT / "DOCS" / "IMPLEMENTED.md"


def test_max_steps_allineato_al_worker():
    from CORE.worker import Worker

    assert Worker.MAX_STEPS == 10
    agent = AGENT.read_text(encoding="utf-8")
    spec = SPEC.read_text(encoding="utf-8")
    assert "MAX_STEPS = 10" in agent
    assert "MAX_STEPS = 10" in spec
    assert "MAX_STEPS = 6" not in agent
    assert "MAX_STEPS = 6" not in spec


def test_baseline_security_scan_unica():
    agent = AGENT.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    assert "baseline unica: 7 errori" in verify
    assert "baseline 15 errori" not in verify
    assert "**7 errori**" in agent
    assert "baseline: 7 errori" in verify


def test_log_gui_non_duplica_il_registro_canonico():
    gui = GUI_LOG.read_text(encoding="utf-8")
    canonical = CANONICAL_LOG.read_text(encoding="utf-8")
    assert "Stub di indirizzo" in gui
    # nessuna riga lunga del vecchio duplicato deve essere rimasta
    long_gui = {line for line in gui.splitlines() if len(line) > 80}
    long_canonical = {line for line in canonical.splitlines()
                      if len(line) > 80}
    assert not (long_gui & long_canonical)


def test_symlink_state_dichiarato():
    agent = AGENT.read_text(encoding="utf-8")
    assert "symlink a `data/state/`" in agent
    state = ROOT / "state"
    # il symlink è per-install e gitignored: se c'è, deve puntare a data/state
    if state.is_symlink():
        assert state.readlink().as_posix() == "data/state"
