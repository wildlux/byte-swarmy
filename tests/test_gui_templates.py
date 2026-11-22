"""
test_gui_templates.py — E3: scaffolding PyQt6 da template curati.
Snapshot offscreen della struttura, prova dei segnali e chiusura del thread.
Nessun LLM, rete o GPU.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout  # noqa: E402

TEMPLATES = ROOT / "GUI" / "refs" / "templates"


def _load(name: str) -> dict:
    path = TEMPLATES / name
    src = path.read_text(encoding="utf-8")
    code = compile(src, str(path), "exec")
    ns: dict = {"__name__": "template_under_test"}
    exec(code, ns)
    return ns


def test_tutti_i_template_compilano_e_hanno_slot():
    files = sorted(TEMPLATES.glob("*.py.tpl"))
    assert len(files) >= 4, files
    assert {f.name for f in files} == {
        "finestra.py.tpl", "layout.py.tpl", "segnali.py.tpl", "thread.py.tpl"}
    for path in files:
        src = path.read_text(encoding="utf-8")
        assert "# SLOT:" in src, path
        compile(src, str(path), "exec")  # Python valido anche con i marker
        assert not re.search(r"\b20\d{2}-\d{2}-\d{2}\b", src), path


def test_finestra_snapshot(qapp):
    ns = _load("finestra.py.tpl")
    win = ns["build_window"]()
    assert win.windowTitle() == "Titolo"
    assert (win.width(), win.height()) == (640, 480)
    central = win.centralWidget()
    assert isinstance(central, QLabel)
    assert central.text() == "Titolo"
    win.close()


def test_layout_snapshot(qapp):
    ns = _load("layout.py.tpl")
    root = ns["build_layout"]()
    assert isinstance(root.layout(), QVBoxLayout)
    assert [w.text() for w in root.findChildren(QLabel)] == ["Nome"]
    assert [w.text() for w in root.findChildren(QPushButton)] == [
        "OK", "Annulla"]
    assert len(root.findChildren(QLineEdit)) == 1
    root.close()


def test_segnali_collegati(qapp):
    ns = _load("segnali.py.tpl")
    widget = ns["LiveLabel"]()
    seen = []
    widget.changed.connect(seen.append)
    widget.edit.setText("ciao")
    qapp.processEvents()
    assert seen == ["ciao"]
    assert widget.label.text() == "ciao"
    widget.close()


def test_thread_completa_e_si_ferma(qapp):
    ns = _load("thread.py.tpl")
    controller = ns["Controller"]()
    seen = []
    controller.finished.connect(seen.append)
    thread = controller.start()
    assert thread.wait(3000), "worker non terminato"
    qapp.processEvents()
    assert seen == ["ok"]
    assert not thread.isRunning()


def test_simboli_qt_verificati_col_gate_corretto():
    """Le classi C++ non hanno firma: qui serve il controllo di esistenza."""
    import logging

    from CORE.tools import ToolSet

    tools = ToolSet({"paths": {"project_root": str(ROOT)}},
                    logging.getLogger("test_gui_templates"))
    for module, symbol in (("PyQt6.QtWidgets", "QMainWindow"),
                           ("PyQt6.QtCore", "QThread")):
        out = tools.api_lookup(module, symbol)
        assert not out.startswith("ERROR"), out
        assert "firma: (non disponibile)" in out
    fake = tools.api_lookup("PyQt6.QtWidgets", "QMainWindowFinto")
    assert fake.startswith("ERROR")


def test_skill_e_keywords_auto_registrati():
    from CORE import auto_skill

    skill = (ROOT / ".opencode" / "skill" / "py-gui-scaffold" / "SKILL.md")
    assert skill.exists()
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: py-gui-scaffold" in text
    assert "## " in text
    hits = auto_skill.detect_names(
        "crea una finestra PyQt6 con layout e segnali")
    assert "py-gui-scaffold" in hits, hits
