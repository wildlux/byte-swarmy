"""Test di sincronizzazione tema per i widget GUI (regola generale).

Regola: nessun pannello GUI può reintrodurre colori hardcoded inline
(senza background) o stylesheet "declaration-only" su contenitori, perché
rompono il tema live (vedi commit 1d04ef3). Ogni nuovo widget deve usare
le property del tema app-level (role=..., banner=...) via
GUI/theme/theme.py (set_prop / set_banner).

Due livelli:
  1. Statico: regex sui sorgenti dei pannelli (esclusi control_center.py
     e TEST_GUI_QT_12.py, debito noto documentato).
  2. Runtime: ogni pannello si istanzia in tema scuro E chiaro senza
     crash (offscreen) — guardia contro regressioni del costruttore.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

GUI = ROOT / "GUI"
PANELS = [
    "actors_panel.py",
    "audit_project_panel.py",
    "hardware_panel.py",
    "search_bar.py",
    "settings_panel.py",
    "task_scheduler_panel.py",
    "test_suite_panel.py",
]

_COLOR_INLINE = re.compile(
    r"setStyleSheet\s*\([^)]*color\s*:\s*#[0-9a-fA-F]{3,6}[^)]*\)",
    re.IGNORECASE | re.DOTALL,
)
_COLOR_WITH_BG = re.compile(r"background\s*:", re.IGNORECASE)
_DECL_ONLY = re.compile(
    r'setStyleSheet\s*\(\s*["\']background\s*:\s*transparent\s*;?\s*["\']\s*\)',
    re.IGNORECASE,
)
_LIGHT_ONLY_COLORS = ("#1a1a1a", "#ffffff", "#e8e8ec", "#f8f9fa",
                      "#fafafa", "#f5f5f7", "#f0f9ff", "#f0f0f0")
_MUTED_GRAYS = {"#666", "#666666", "#777", "#777777", "#888",
                "#888888", "#999", "#999999", "#555", "#555555",
                "#444", "#444444", "#333", "#333333", "#aaa",
                "#aaaaaa", "#bbb", "#bbbbbb", "#ccc", "#cccccc",
                "#ddd", "#dddddd"}


@pytest.mark.parametrize("name", PANELS)
def test_no_inline_muted_gray_without_bg(name: str) -> None:
    src = (GUI / name).read_text(encoding="utf-8")
    offenders = []
    for m in _COLOR_INLINE.finditer(src):
        if _COLOR_WITH_BG.search(m.group(0)):
            continue
        cm = re.search(r"#[0-9a-fA-F]{3,6}", m.group(0))
        if cm and cm.group(0).lower() in _MUTED_GRAYS:
            ln = src[:m.start()].count("\n") + 1
            offenders.append((ln, m.group(0).strip()[:80]))
    assert not offenders, (
        f"{name}: setStyleSheet con colore grigio muted hardcodato senza "
        f"background (non sincronizzato col tema): {offenders}"
    )


@pytest.mark.parametrize("name", PANELS)
def test_no_declaration_only_transparent(name: str) -> None:
    src = (GUI / name).read_text(encoding="utf-8")
    matches = _DECL_ONLY.findall(src)
    assert not matches, (
        f"{name}: setStyleSheet('background: transparent;') declaration-only "
        f"azzera lo sfondo dei bottoni figli (usa selettore objectName)"
    )


@pytest.mark.parametrize("name", PANELS)
def test_no_light_only_hardcoded_colors(name: str) -> None:
    src = (GUI / name).read_text(encoding="utf-8")
    offenders = []
    for col in _LIGHT_ONLY_COLORS:
        for m in re.finditer(r"setStyleSheet\s*\([^)]*" + re.escape(col) + r"[^)]*\)",
                              src, re.IGNORECASE | re.DOTALL):
            ln = src[:m.start()].count("\n") + 1
            offenders.append((ln, col))
    assert not offenders, (
        f"{name}: colori light-only hardcoded in setStyleSheet "
        f"(invisibili nel tema scuro): {offenders}"
    )


def test_no_declaration_only_transparent_in_control_center() -> None:
    src = (GUI / "control_center.py").read_text(encoding="utf-8")
    matches = _DECL_ONLY.findall(src)
    assert not matches, (
        "control_center.py: setStyleSheet('background: transparent;') "
        "declaration-only (azzera bottoni figli)"
    )


# ── Runtime smoke: ogni pannello si istanzia in ENTRAMBI i temi ──
_PANEL_CLASSES = {
    "actors_panel.py": ("GUI.actors_panel", "ActorsPanel"),
    "audit_project_panel.py": ("GUI.audit_project_panel", "AuditProjectPanel"),
    "hardware_panel.py": ("GUI.hardware_panel", "HardwarePanel"),
    "settings_panel.py": ("GUI.settings_panel", "SettingsPanel"),
    "search_bar.py": ("GUI.search_bar", "SearchBar"),
    "task_scheduler_panel.py": ("GUI.task_scheduler_panel", "TaskSchedulerPanel"),
    "test_suite_panel.py": ("GUI.test_suite_panel", "TestSuitePanel"),
}


def test_all_panels_instantiate_in_both_themes() -> None:
    import importlib
    import gc
    from GUI.theme import theme as T
    from PyQt6.QtWidgets import QApplication, QPlainTextEdit
    app = QApplication.instance() or QApplication([])
    for fname, (modname, clsname) in _PANEL_CLASSES.items():
        mod = importlib.import_module(modname)
        cls = getattr(mod, clsname)
        for theme in ("dark", "light"):
            app.setStyleSheet(T._load(theme))
            if clsname == "SearchBar":
                w = cls(QPlainTextEdit())
            else:
                w = cls()
            w.resize(800, 600)
            w.show()
            for _ in range(5):
                app.processEvents()
            pm = w.grab()
            assert pm.width() > 0 and pm.height() > 0, (
                f"{fname} non renderizza in tema {theme}"
            )
            w.hide()
            for _ in range(3):
                app.processEvents()
            del w
            gc.collect()
            for _ in range(3):
                app.processEvents()


def test_theme_helpers_exist() -> None:
    from GUI.theme import theme as T
    assert hasattr(T, "set_prop")
    assert hasattr(T, "set_banner")
    assert hasattr(T, "apply_theme")
    from PyQt6.QtWidgets import QApplication, QLabel
    app = QApplication.instance() or QApplication([])
    lab = QLabel("x")
    for kind in ("info", "ok", "error", "warn", None):
        T.set_banner(lab, kind)
