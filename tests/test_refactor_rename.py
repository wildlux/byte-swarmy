# -*- coding: utf-8 -*-
"""Test del rename in due fasi e del rollback (2026-11-22).

Nessun LLM e nessuna rete: progetto fake in tmp_path, anteprima senza
scritture, apply con snapshot e ripristino byte-identico.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import auto_skill, auto_tool  # noqa: E402
from CORE.tools import TOOL_SIGNATURES, ToolSet  # noqa: E402
from CORE.worker import Worker  # noqa: E402

_A = '''\
"""Modulo A."""
import sys


def old_name(x):
    return x


VALUE = old_name(1)


def main():
    text = "old_name"
    # old_name nel commento
    return old_name(2), sys.version_info
'''

_B = '''\
"""Modulo B."""
from a import old_name


def run():
    return old_name(3)
'''


def _project(tmp_path):
    (tmp_path / "a.py").write_text(_A, encoding="utf-8")
    (tmp_path / "b.py").write_text(_B, encoding="utf-8")
    cfg = {"paths": {"project_root": str(tmp_path)}, "security": {}}
    log = SimpleNamespace(warning=lambda *a, **k: None,
                          info=lambda *a, **k: None)
    return ToolSet(cfg, log)


def _digest(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.glob("*.py"))}


def test_anteprima_non_modifica_nulla(tmp_path):
    fake = _project(tmp_path)
    before = _digest(tmp_path)
    out = ToolSet.rename_symbol(fake, "old_name", "new_name")
    assert "ANTEPRIMA" in out
    assert "nessun file modificato" in out
    assert "in stringhe/commenti (non toccate): 2" in out
    assert _digest(tmp_path) == before


def test_apply_sostituisce_solo_token_codice(tmp_path):
    fake = _project(tmp_path)
    out = ToolSet.rename_symbol(fake, "old_name", "new_name", apply=True)
    assert out.startswith("OK")
    sid = re.search(r"Snapshot '([^']+)'", out).group(1)
    a = (tmp_path / "a.py").read_text(encoding="utf-8")
    b = (tmp_path / "b.py").read_text(encoding="utf-8")
    assert "def new_name" in a
    assert "VALUE = new_name(1)" in a
    assert 'text = "old_name"' in a
    assert "# old_name nel commento" in a
    assert "from a import new_name" in b
    assert (tmp_path / "state" / "refactor_snapshots" / sid
            / "manifest.json").is_file()


def test_rollback_ripristina_byte_identico(tmp_path):
    fake = _project(tmp_path)
    before = _digest(tmp_path)
    out = ToolSet.rename_symbol(fake, "old_name", "new_name", apply=True)
    sid = re.search(r"Snapshot '([^']+)'", out).group(1)
    assert _digest(tmp_path) != before
    assert ToolSet.restore_snapshot(fake, sid).startswith("OK")
    assert _digest(tmp_path) == before


def test_input_invalido_non_solleva(tmp_path):
    fake = _project(tmp_path)
    for old, new in (("", "x"), ("a-b", "x"), ("3bad", "x"),
                     (None, "x"), (1, "x"), ("old_name", "old_name")):
        out = ToolSet.rename_symbol(fake, old, new)
        assert isinstance(out, str) and out.startswith("ERROR")


def test_snapshot_id_invalido(tmp_path):
    fake = _project(tmp_path)
    for probe in ("", "../etc", "a/b", None, 1, "inesistente"):
        out = ToolSet.restore_snapshot(fake, probe)
        assert isinstance(out, str) and out.startswith("ERROR")


def test_registrazione_tool_e_worker():
    assert "apply=False" in TOOL_SIGNATURES["rename_symbol"]
    assert "restore_snapshot" in TOOL_SIGNATURES
    assert "restore_snapshot" in ToolSet.allowed_tools(SimpleNamespace())
    assert Worker.TOOL_CODE_MAP["restore"] == "restore_snapshot"
    assert "rename_symbol" in auto_tool.detect_names("anteprima rename")


def test_skill_presente_e_auto_abilitata():
    skill = ROOT / ".opencode" / "skill" / "refactoring-mecc" / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "name: refactoring-mecc" in text
    assert "rename_symbol" in text and "restore_snapshot" in text
    assert "refactoring-mecc" in auto_skill.detect_names("rinomina funzione")
