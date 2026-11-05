"""Gestione temi QSS per BYTE-SWARMY."""
from pathlib import Path
from PyQt6.QtCore import QSettings

THEME_DIR = Path(__file__).parent
SETTINGS = ("byte-swarmy", "control-center")

# Nomi "amichevoli" per i temi base (gli altri derivano dal nome file).
_FRIENDLY = {
    "dark": "Scuro",
    "light": "Chiaro",
    "dark_amber": "Scuro Ambra",
    "dark_classic": "Scuro Classico",
    "dark_cyan": "Scuro Ciano",
    "dark_green": "Scuro Verde",
    "dark_lavender": "Scuro Lavanda",
    "dark_ocean": "Scuro Oceano",
    "dark_purple": "Scuro Viola",
    "dark_rainbow": "Scuro Arcobaleno",
    "dark_sunset": "Scuro Tramonto",
    "dracula": "Dracula",
    "hacker": "Hacker",
    "light_mint": "Chiaro Menta",
    "light_rose": "Chiaro Rosa",
    "light_sand": "Chiaro Sabbia",
    "light_sky": "Chiaro Cielo",
    "military": "Militare",
    "neon": "Neon",
    "nord": "Nord",
    "pink": "Rosa",
    "solar": "Solare",
    "venom_blue": "Venom Blu",
    "venom_green": "Venom Verde",
    "venom_orange": "Venom Arancio",
    "venom_red": "Venom Rosso",
}


def _load(name):
    return (THEME_DIR / (name + ".qss")).read_text(encoding="utf-8")


def available_themes():
    """Lista dei temi disponibili (nomi file senza estensione, escluso
    base.qss che è solo un parziale)."""
    out = []
    for p in sorted(THEME_DIR.glob("*.qss")):
        if p.stem == "base":
            continue
        out.append(p.stem)
    return out


def theme_display_name(name):
    if name in _FRIENDLY:
        return _FRIENDLY[name]
    return name.replace("_", " ").title()


def current_theme():
    t = QSettings(*SETTINGS).value("theme", "dark")
    if t not in available_themes():
        return "dark"
    return t


def apply_theme(app, name=None):
    name = name or current_theme()
    if name not in available_themes():
        name = "dark"
    app.setStyleSheet(_load(name))
    QSettings(*SETTINGS).setValue("theme", name)
    return name


def toggle_theme(app):
    themes = available_themes()
    cur = current_theme()
    idx = themes.index(cur) if cur in themes else 0
    nxt = themes[(idx + 1) % len(themes)]
    return apply_theme(app, nxt)


def set_prop(widget, prop, value):
    widget.setProperty(prop, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# Mappatura semantica → property `banner` usata dai .qss
# (info/ok/error/warn esistono in entrambi i temi).
_BANNERS = {"info": "info", "ok": "ok", "error": "error", "warn": "warn"}


def set_banner(widget, kind):
    set_prop(widget, "banner", _BANNERS.get(kind or "", ""))
