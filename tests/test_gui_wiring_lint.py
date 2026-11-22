# -*- coding: utf-8 -*-
"""Test deterministici della regola W011 (wiring GUI) di `lint_style.py`.

Riproduce il bug dell'Archivio 2026-11-22: `sectionClicked.connect(...)`
senza `setSectionsClickable(True)` → i click reali non emettevano il segnale.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import lint_style as ls  # noqa: E402


def _w011(src, tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "ROOT", tmp_path)
    path = tmp_path / "GUI" / "demo.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")
    findings = []
    ls._check_file(path, findings)
    return [f for f in findings if f.code == "W011"]


_BROKEN = '''\
"""Demo."""

class Demo:
    def __init__(self):
        self.tree.header().sectionClicked.connect(self.on_click)

    def on_click(self, index):
        pass
'''

_FIXED = _BROKEN.replace(
    "        self.tree.header().sectionClicked.connect(self.on_click)",
    "        self.tree.header().setSectionsClickable(True)\n"
    "        self.tree.header().sectionClicked.connect(self.on_click)",
)


def test_w011_segnala_click_header_disabilitato(tmp_path, monkeypatch):
    found = _w011(_BROKEN, tmp_path, monkeypatch)
    assert len(found) == 1
    assert found[0].level == "warn"
    assert "setSectionsClickable(True)" in found[0].msg


def test_w011_non_segnala_codice_corretto(tmp_path, monkeypatch):
    assert _w011(_FIXED, tmp_path, monkeypatch) == []


def test_w011_rispetta_nolint(tmp_path, monkeypatch):
    src = _BROKEN.replace(
        "sectionClicked.connect(self.on_click)",
        "sectionClicked.connect(self.on_click)  # nolint: test",
    )
    assert _w011(src, tmp_path, monkeypatch) == []


def test_w011_ignora_segnali_non_header(tmp_path, monkeypatch):
    src = _BROKEN.replace("header().sectionClicked", "button().clicked")
    assert _w011(src, tmp_path, monkeypatch) == []


def test_file_reale_non_genera_w011():
    """Il fix dell'Archivio non deve essere segnalato come regressione."""
    findings = []
    ls._check_file(ROOT / "GUI" / "file_tree_drawer.py", findings)
    assert [f for f in findings if f.code == "W011"] == []
