"""Gestione temi QSS per BYTE-SWARMY (PyQt5/PyQt6/PySide6).

Uso:
    from theme import apply_theme, toggle_theme
    apply_theme(app)            # all'avvio (ricorda l'ultima scelta)
    toggle_theme(app)           # es. da Ctrl+Shift+T o da un'azione di menu
"""
from pathlib import Path

try:
    from PyQt6.QtCore import QSettings
except ImportError:
    from PyQt5.QtCore import QSettings

THEME_DIR = Path(__file__).parent
SETTINGS = ("byte-swarmy", "control-center")


def _load(name: str) -> str:
    return (THEME_DIR / f"{name}.qss").read_text(encoding="utf-8")


def current_theme() -> str:
    return QSettings(*SETTINGS).value("theme", "light")


def apply_theme(app, name: str | None = None) -> str:
    name = name or current_theme()
    app.setStyleSheet(_load(name))
    QSettings(*SETTINGS).setValue("theme", name)
    return name


def toggle_theme(app) -> str:
    return apply_theme(app, "dark" if current_theme() == "light" else "light")


def set_prop(widget, prop: str, value: str) -> None:
    """Cambia una property dinamica (state, thermal, banner, role) e rinfresca lo stile."""
    widget.setProperty(prop, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
