# -*- coding: utf-8 -*-
"""Test deterministici per il detector/tool/skill "codice morto" (2026-11-22).

Nessun LLM, nessuna rete, nessuna modifica ai file del progetto: il detector è
report-only e i test usano una cartella temporanea.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import auto_skill, auto_tool  # noqa: E402
from CORE.dead_code import format_report, scan  # noqa: E402
from CORE.tools import TOOL_SIGNATURES, ToolSet  # noqa: E402
from CORE.worker import Worker  # noqa: E402

_FIXTURE_A = """\
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path as _Path


def usata():
    return 1


def mai_chiamata():
    return 2


class ClasseMorta:
    pass


@property
def con_decoratore():
    return 3


def main():
    sys.exit(0)
"""

_FIXTURE_B = """\
from a import usata

usata()
"""


def _fixture(tmp_path):
    (tmp_path / "a.py").write_text(_FIXTURE_A, encoding="utf-8")
    (tmp_path / "b.py").write_text(_FIXTURE_B, encoding="utf-8")
    (tmp_path / "__init__.py").write_text(
        "from a import usata\n", encoding="utf-8")
    return tmp_path


def _digest(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.glob("*")) if p.is_file()}


def test_scan_trova_solo_candidati_realistici(tmp_path):
    """Funzione usata, entry point, decoratori e TYPE_CHECKING sono esclusi."""
    findings = scan(_fixture(tmp_path))
    names = {f["name"] for f in findings}
    assert "mai_chiamata" in names
    assert "ClasseMorta" in names
    assert "os" in names  # import non referenziato
    assert "usata" not in names
    assert "main" not in names
    assert "con_decoratore" not in names
    assert "sys" not in names
    assert "_Path" not in names
    assert all(f["type"] == "dead_code" and f["file"] and f["line"]
               for f in findings)


def test_scan_ordinato_e_report_deterministico(tmp_path):
    """Stesso input → stessa lista e stesso testo, senza timestamp."""
    root = _fixture(tmp_path)
    first = scan(root)
    assert first == scan(root)
    report = format_report(first, ".")
    assert report == format_report(scan(root), ".")
    assert "SOLO LETTURA" in report
    assert "find_references" in report


def test_scan_senza_candidati(tmp_path):
    (tmp_path / "ok.py").write_text("def usata():\n    return 1\n\nusata()\n")
    assert scan(tmp_path) == []
    assert "nessun candidato" in format_report(scan(tmp_path))


def test_tool_e_report_only(tmp_path):
    """Il tool restituisce il report e non tocca alcun file."""
    root = _fixture(tmp_path)
    before = _digest(root)
    fake = SimpleNamespace(project_root=str(root))
    out = ToolSet.find_dead_code(fake, ".")
    assert "CODICE MORTO" in out
    assert "mai_chiamata" in out
    assert _digest(root) == before


def test_tool_gestisce_input_invalido(tmp_path):
    """Nessuna eccezione per path vuoto o fuori root (hardcore test style)."""
    fake = SimpleNamespace(project_root=str(tmp_path))
    for probe in ("", "../", "/etc/passwd", None, 1):
        out = ToolSet.find_dead_code(fake, probe)
        assert isinstance(out, str)
        assert out.startswith("ERROR") or "CODICE MORTO" in out


def test_tool_registrato_in_tutti_i_punti():
    """Firma, allowlist, dispatch worker e auto-tool devono essere allineati."""
    assert "find_dead_code" in TOOL_SIGNATURES
    assert "find_dead_code" in ToolSet.allowed_tools(SimpleNamespace())
    assert Worker.TOOL_CODE_MAP["dead"] == "find_dead_code"
    assert "find_dead_code" in auto_tool.detect_names(
        "trova il codice morto nel progetto")


def test_skill_presente_e_auto_abilitata():
    """La skill agente esiste, ha frontmatter e viene rilevata dalle keyword."""
    skill = ROOT / ".opencode" / "skill" / "codice-morto" / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: codice-morto" in text
    assert "description:" in text
    assert "find_dead_code" in text
    detected = auto_skill.detect_names(
        "c'è del codice morto da rimuovere",
        available=[{"name": "codice-morto", "description": text}])
    assert "codice-morto" in detected
