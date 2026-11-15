"""Gestione temi QSS per BYTE-SWARMY."""
import re
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
    # Temi chiari generati per inversione luminanza dei temi scuri
    "light_dark": "Chiaro Inverso",
    "light_dracula": "Dracula Chiaro",
    "light_hacker": "Hacker Chiaro",
    "light_neon": "Neon Chiaro",
    "light_nord": "Nord Chiaro",
    "light_pink": "Rosa Chiaro",
    "light_solar": "Solare Chiaro",
    "light_venom_blue": "Venom Blu Chiaro",
    "light_venom_green": "Venom Verde Chiaro",
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


_HEX_COLOR = __import__("re").compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def _luminance(hex_color: str) -> float:
    """Luminanza percettiva 0..1 di un colore #rrggbb (o #rgb)."""
    h = hex_color.strip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return 0.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def theme_kind(name: str) -> str:
    """Classifica un tema come "light" o "dark".

    Analizza i colori di sfondo del .qss (luminanza media dei hex che
    appaiono accanto a "background"): se il fondo è più scuro della
    metà della scala, il tema è scuro. Fallback euristico sul nome
    (prefisso light_/chiaro) per qss senza colori riconoscibili.
    """
    try:
        qss = _load(name)
    except OSError:
        return "dark"
    bgs = []
    for m in _HEX_COLOR.finditer(qss):
        start = max(0, m.start() - 40)
        if "background" in qss[start:m.start()].lower():
            bgs.append(_luminance(m.group(0)))
    if bgs:
        return "light" if (sum(bgs) / len(bgs)) > 0.5 else "dark"
    lower = name.lower()
    return "light" if ("light" in lower or "chiaro" in lower) else "dark"


def load_stylesheet(name: str) -> str:
    """Contenuto QSS del tema `name`, con fallback al tema dark."""
    if name not in available_themes():
        name = "dark"
    return _load(name)


def palette_for(kind: str):
    """Palette applicativa coerente col kind del tema (light/dark).

    Il QSS non copre i primitive disegnati dallo stile NATIVO quando
    nessuna regola matcha: l'esempio principale è l'indicatore checkbox
    degli item view (QTreeView/QListWidget con flag checkable), che in
    offscreen/alcune piattaforme viene disegnato nativamente con i
    colori della PALETTE → nei temi scuri restava un quadratino bianco
    (regressione 'white panels'). Le regole QSS ::indicator per gli
    item view vengono infatti ignorate dallo stile foglio di stile.
    Settare la palette a tema risolve la classe di bug alla radice.
    """
    from PyQt6.QtGui import QPalette, QColor
    p = QPalette()
    if kind != "dark":
        return p  # palette default = light: coerente coi temi chiari
    dark = {
        QPalette.ColorRole.Window: "#1b1f27",
        QPalette.ColorRole.WindowText: "#e6e9ef",
        QPalette.ColorRole.Base: "#161a22",
        QPalette.ColorRole.AlternateBase: "#1b1f27",
        QPalette.ColorRole.Text: "#e6e9ef",
        QPalette.ColorRole.Button: "#232935",
        QPalette.ColorRole.ButtonText: "#e6e9ef",
        QPalette.ColorRole.Highlight: "#2a5db0",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#161a22",
        QPalette.ColorRole.ToolTipText: "#e6e9ef",
        QPalette.ColorRole.PlaceholderText: "#8892a4",
        QPalette.ColorRole.Light: "#3a4252",
        QPalette.ColorRole.Midlight: "#2a303b",
        QPalette.ColorRole.Mid: "#232935",
        QPalette.ColorRole.Dark: "#12151b",
        QPalette.ColorRole.Shadow: "#0b0d11",
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Link: "#5b92ff",
        QPalette.ColorRole.LinkVisited: "#bd93f9",
    }
    for role, hexcol in dark.items():
        p.setColor(role, QColor(hexcol))
    # Gruppo Disabled: testo attenuato su superfici leggermente più scure.
    for role, hexcol in (
            (QPalette.ColorRole.WindowText, "#6b7280"),
            (QPalette.ColorRole.Text, "#6b7280"),
            (QPalette.ColorRole.ButtonText, "#6b7280"),
            (QPalette.ColorRole.Base, "#14171e"),
            (QPalette.ColorRole.Button, "#1d222b")):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(hexcol))
    return p


def apply_palette(app, name: str) -> None:
    """Setta la palette dell'applicazione secondo il kind del tema."""
    if app is not None:
        app.setPalette(palette_for(theme_kind(name)))


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


# Colore di un token semantico (property `role=` per QLabel) dal QSS corrente.
_ROLE_RE = re.compile(
    r'QLabel\[role="([a-z]+)"\]\s*\{[^}]*?color:\s*(#[0-9a-fA-F]{6})')


def token_color(name: str):
    """Colore `#rrggbb` del token `role=name` nel tema corrente (o None)."""
    m = _ROLE_RE.search(_load(current_theme()))
    for m in _ROLE_RE.finditer(_load(current_theme())):
        if m.group(1) == name:
            return m.group(2)
    return None


# Mappatura semantica → property `banner` usata dai .qss
# (info/ok/error/warn esistono in entrambi i temi).
_BANNERS = {"info": "info", "ok": "ok", "error": "error", "warn": "warn"}


def set_banner(widget, kind):
    set_prop(widget, "banner", _BANNERS.get(kind or "", ""))
