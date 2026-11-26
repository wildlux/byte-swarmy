"""test_tool_proposer.py — Gate e lifecycle delle proposte di tool generati."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.tool_proposer import propose, gate, approve, reject, list_proposals, _gate


def _safe_code(name="my_tool"):
    return (
        f"def {name}(x: int) -> int:\n"
        f"    \"\"\"Restituisce x+1.\"\"\"\n"
        f"    return x + 1\n"
        f"\n__all__ = [\"{name}\"]\n"
    )


def _unsafe_code():
    return (
        "import os\n"
        "def bad(x):\n"
        "    os.system('rm -rf /')\n"
        "    return x\n"
        "\n__all__ = ['bad']\n"
    )


def test_gate_verde_su_codice_sicuro():
    r = _gate("t", _safe_code())
    assert r.ok, r.reasons()


def test_gate_rosso_su_codice_pericoloso():
    r = _gate("t", _unsafe_code())
    assert not r.ok
    assert any("sicurezza" in c.name for c in r.checks if not c.ok)


def test_gate_rosso_su_sintassi_invalida():
    r = _gate("t", "def broken(\n")
    assert not r.ok


def test_gate_rosso_senza_funzione():
    r = _gate("t", "x = 5\n")
    assert not r.ok


def test_propose_e_list():
    with tempfile.TemporaryDirectory() as td:
        # redirige PROPOSALS_DIR via monkeypatch manuale
        import CORE.tool_proposer as tp
        orig = tp.PROPOSALS_DIR
        tp.PROPOSALS_DIR = Path(td) / "proposals"
        tp.REGISTRY_FILE = tp.PROPOSALS_DIR / "registry.json"
        tp.PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            pid = propose("alpha", _safe_code("alpha"))
            assert pid == "alpha"
            assert ("alpha", "pending") in list_proposals()
        finally:
            tp.PROPOSALS_DIR = orig
            tp.REGISTRY_FILE = tp.PROPOSALS_DIR / "registry.json"


def test_approve_blocca_se_gate_rosso():
    with tempfile.TemporaryDirectory() as td:
        import CORE.tool_proposer as tp
        orig_dir = tp.PROPOSALS_DIR
        orig_reg = tp.REGISTRY_FILE
        orig_gen = tp.GENERATED_FILE
        tp.PROPOSALS_DIR = Path(td) / "proposals"
        tp.REGISTRY_FILE = tp.PROPOSALS_DIR / "registry.json"
        tp.GENERATED_FILE = Path(td) / "generated_tools.py"
        tp.PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            propose("bad", _unsafe_code())
            assert approve("bad") is False
            assert not tp.GENERATED_FILE.exists()
        finally:
            tp.PROPOSALS_DIR = orig_dir
            tp.REGISTRY_FILE = orig_reg
            tp.GENERATED_FILE = orig_gen
