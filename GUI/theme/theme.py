"""Gestione temi QSS per BYTE-SWARMY."""
from pathlib import Path
from PyQt6.QtCore import QSettings
THEME_DIR = Path(__file__).parent
SETTINGS = ("byte-swarmy", "control-center")
def _load(name): return (THEME_DIR / (name + ".qss")).read_text(encoding="utf-8")
def current_theme(): return QSettings(*SETTINGS).value("theme", "dark")
def apply_theme(app, name=None):
    name = name or current_theme()
    app.setStyleSheet(_load(name))
    QSettings(*SETTINGS).setValue("theme", name)
    return name
def toggle_theme(app): return apply_theme(app, "dark" if current_theme() == "light" else "light")
def set_prop(widget, prop, value):
    widget.setProperty(prop, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
