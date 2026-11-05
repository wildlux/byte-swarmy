"""gen_theme.py — genera temi byte-swarmy-compatible da palette.

Prende GUI/theme/dark.qss come template e sostituisce la palette base con
quella fornita, scrivendo GUI/theme/<name>.qss. Le palette sono ispirate
ai temi di Prismalux (https://github.com/wildlux/Prismalux/tree/master/gui/themes)
ma adattate al vocabolario di byte-swarmy (role=, banner=, QGroupBox, ...).

Uso:
    .venv/bin/python tools/gen_theme.py            # genera tutti i temi definiti
    .venv/bin/python tools/gen_theme.py dracula    # solo un tema
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_DIR = ROOT / "GUI" / "theme"
TEMPLATE = (THEME_DIR / "dark.qss").read_text(encoding="utf-8")

# Palette base di byte-swarmy (dark.qss) → slot → colore.
# Ogni tema sovrascrive solo gli slot che vuole; il resto resta dark.
BASE = {
    "#14171d": "window",
    "#1b1f27": "surface",
    "#242933": "elevated",
    "#1a1e25": "pressed",
    "#1b1f26": "input",
    "#191c22": "alt",
    "#21252d": "grid",
    "#2a303b": "border",
    "#333a46": "border_hover",
    "#e6e9ef": "text",
    "#eef1f6": "bright",
    "#b9c1cc": "text_soft",
    "#8f99ab": "muted",
    "#5a6270": "faint",
    "#5b92ff": "accent",
    "#2f6fd1": "sel_bg",
    "#6fd3a1": "ok",
    "#f0c56a": "warn",
    "#ff9b8f": "err",
    "#2c313b": "handle",
}

# Palette ispirate a Prismalux (solo gli slot che cambiano).
PALETTES = {
    "dracula": {
        "window": "#282a36", "surface": "#44475a", "elevated": "#343746",
        "pressed": "#21222c", "input": "#282a36", "alt": "#21222c",
        "grid": "#343746", "border": "#44475a", "border_hover": "#6272a4",
        "text": "#f8f8f2", "bright": "#ffffff", "text_soft": "#e0e0e0",
        "muted": "#6272a4", "faint": "#44475a",
        "accent": "#bd93f9", "sel_bg": "#6272a4",
        "ok": "#50fa7b", "warn": "#f1fa8c", "err": "#ff5555",
        "handle": "#44475a",
    },
    "nord": {
        "window": "#2e3440", "surface": "#3b4252", "elevated": "#434c5e",
        "pressed": "#242933", "input": "#3b4252", "alt": "#2e3440",
        "grid": "#3b4252", "border": "#4c566a", "border_hover": "#5e81ac",
        "text": "#eceff4", "bright": "#ffffff", "text_soft": "#d8dee9",
        "muted": "#4c566a", "faint": "#3b4252",
        "accent": "#88c0d0", "sel_bg": "#5e81ac",
        "ok": "#a3be8c", "warn": "#ebcb8b", "err": "#bf616a",
        "handle": "#434c5e",
    },
    "neon": {
        "window": "#0a0a0a", "surface": "#1a1a2e", "elevated": "#16213e",
        "pressed": "#050505", "input": "#1a1a2e", "alt": "#0a0a0a",
        "grid": "#16213e", "border": "#00ff41", "border_hover": "#00cc33",
        "text": "#00ff41", "bright": "#39ff14", "text_soft": "#00cc33",
        "muted": "#008f11", "faint": "#003b00",
        "accent": "#00ff41", "sel_bg": "#003b00",
        "ok": "#39ff14", "warn": "#ffff00", "err": "#ff0040",
        "handle": "#1a1a2e",
    },
    "solar": {
        "window": "#002b36", "surface": "#073642", "elevated": "#0a4050",
        "pressed": "#001f27", "input": "#073642", "alt": "#002b36",
        "grid": "#073642", "border": "#586e75", "border_hover": "#268bd2",
        "text": "#839496", "bright": "#93a1a1", "text_soft": "#657b83",
        "muted": "#586e75", "faint": "#073642",
        "accent": "#268bd2", "sel_bg": "#073642",
        "ok": "#859900", "warn": "#b58900", "err": "#dc322f",
        "handle": "#073642",
    },
    "hacker": {
        "window": "#0d0208", "surface": "#001a00", "elevated": "#002200",
        "pressed": "#000d00", "input": "#001a00", "alt": "#0d0208",
        "grid": "#001a00", "border": "#00ff41", "border_hover": "#00cc33",
        "text": "#00ff41", "bright": "#39ff14", "text_soft": "#00cc33",
        "muted": "#008f11", "faint": "#003b00",
        "accent": "#00ff41", "sel_bg": "#003b00",
        "ok": "#39ff14", "warn": "#ffff00", "err": "#ff0040",
        "handle": "#001a00",
    },
    "pink": {
        "window": "#1a0a14", "surface": "#2a1525", "elevated": "#3a2035",
        "pressed": "#120610", "input": "#2a1525", "alt": "#1a0a14",
        "grid": "#2a1525", "border": "#9d5c7c", "border_hover": "#ec4899",
        "text": "#fce7f3", "bright": "#ffffff", "text_soft": "#f9a8d4",
        "muted": "#9d5c7c", "faint": "#3a2035",
        "accent": "#ec4899", "sel_bg": "#9d5c7c",
        "ok": "#34d399", "warn": "#fbbf24", "err": "#f87171",
        "handle": "#2a1525",
    },
    "venom_blue": {
        "window": "#0a0e1a", "surface": "#111827", "elevated": "#1e293b",
        "pressed": "#050810", "input": "#111827", "alt": "#0a0e1a",
        "grid": "#111827", "border": "#334155", "border_hover": "#3b82f6",
        "text": "#e2e8f0", "bright": "#f1f5f9", "text_soft": "#cbd5e1",
        "muted": "#64748b", "faint": "#1e293b",
        "accent": "#3b82f6", "sel_bg": "#1d4ed8",
        "ok": "#22c55e", "warn": "#f59e0b", "err": "#ef4444",
        "handle": "#111827",
    },
    "venom_green": {
        "window": "#0a1a0a", "surface": "#112211", "elevated": "#1a331a",
        "pressed": "#050d05", "input": "#112211", "alt": "#0a1a0a",
        "grid": "#112211", "border": "#335533", "border_hover": "#22c55e",
        "text": "#e2f0e2", "bright": "#f0fdf4", "text_soft": "#bbf7d0",
        "muted": "#64748b", "faint": "#1a331a",
        "accent": "#22c55e", "sel_bg": "#16a34a",
        "ok": "#4ade80", "warn": "#fbbf24", "err": "#f87171",
        "handle": "#112211",
    },
    "dracula": {
        "window": "#282a36", "surface": "#44475a", "elevated": "#343746",
        "pressed": "#21222c", "input": "#44475a", "alt": "#21222c",
        "grid": "#44475a", "border": "#6272a4", "border_hover": "#bd93f9",
        "text": "#f8f8f2", "bright": "#ffffff", "text_soft": "#e0e0e0",
        "muted": "#6272a4", "faint": "#44475a",
        "accent": "#bd93f9", "sel_bg": "#6272a4",
        "ok": "#50fa7b", "warn": "#f1fa8c", "err": "#ff5555",
        "handle": "#44475a",
    },
}


def generate(name: str) -> str:
    if name not in PALETTES:
        raise KeyError(name)
    pal = PALETTES[name]
    # invert base → palette slot
    slot_to_color = {v: k for k, v in BASE.items()}
    out = TEMPLATE
    for slot, base_color in slot_to_color.items():
        new_color = pal.get(slot)
        if not new_color:
            continue
        out = out.replace(base_color, new_color)
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    if args.list:
        print("\n".join(sorted(PALETTES)))
        return 0
    names = args.names or list(PALETTES)
    for n in names:
        if n not in PALETTES:
            print(f"tema sconosciuto: {n}", file=__import__("sys").stderr)
            continue
        (THEME_DIR / (n + ".qss")).write_text(generate(n), encoding="utf-8")
        print(f"generato GUI/theme/{n}.qss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
