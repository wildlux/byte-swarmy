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


# Mappatura semantica → property `banner` usata dai .qss
# (info/ok/error/warn esistono in entrambi i temi).
_BANNERS = {"info": "info", "ok": "ok", "error": "error", "warn": "warn"}


def set_banner(widget, kind: str | None):
    """Stato colore-tema di una label di stato (info/ok/error/warn).

    `kind=None` torna al colore neutro del tema (banner="").
    Usa le property dei .qss così il colore segue il tema live
    (il toggle re-polisha tutto l'app).
    """
    set_prop(widget, "banner", _BANNERS.get(kind or "", ""))
