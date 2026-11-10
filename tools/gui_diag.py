#!/usr/bin/env python3
"""gui_diag.py — Diagnostica interfaccia grafica BYTE-SWARMY.

Funge da "occhio" per un agente LLM: cattura uno screenshot della finestra
(offscreen o desktop) e lo converte in un albero accessibilità JSON che
descrive ogni widget (tipo, testo, geometria, stato, gerarchia), così l'LLM
può analizzare l'interfaccia senza bisogno di "vedere" davvero l'immagine.

Uso da riga di comando:
    python tools/gui_diag.py                       # cattura Control Center se avviato
    python tools/gui_diag.py --widget "MyWidget"   # cattura un widget per nome classe
    python tools/gui_diag.py --out diag_20261108   # prefisso file di output
    python tools/gui_diag.py --list-widgets         # stampa solo l'albero (no immagine)

Prodotto:
    <out>_screenshot.png   immagine della finestra
    <out>_tree.json        albero accessibilità (formato LLM-friendly)
    <out>_tree.txt         versione compatta testo (incollabile in prompt LLM)

Variabili d'ambiente:
    QT_QPA_PLATFORM=offscreen  (consigliato su server senza display)
    BSWARM_GUI_DEBUG=1         stampa dettagli su stdout
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QImage
from PyQt6.QtCore import QTimer, QSize

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

DEFAULT_OUT = "gui_diag"
LOG_DIR = Path("logs")


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Albero accessibilità
# ---------------------------------------------------------------------------

def _role_hint(widget: QWidget) -> str:
    """Ritorna un ruolo leggibile per l'LLM (best effort, senza QAccessible)."""
    cls = widget.__class__.__name__
    name = (widget.objectName() or "").strip()
    text = ""
    try:
        text = widget.text().strip()
    except Exception:
        pass
    if cls == "QPushButton":
        return "button"
    if cls == "QLabel":
        return "label"
    if cls == "QLineEdit":
        return "text_input"
    if cls == "QPlainTextEdit" or cls == "QTextEdit":
        return "text_area"
    if cls == "QComboBox":
        return "combo_box"
    if cls == "QCheckBox":
        return "checkbox"
    if cls == "QRadioButton":
        return "radio_button"
    if cls == "QSpinBox" or cls == "QDoubleSpinBox":
        return "spinner"
    if cls == "QProgressBar":
        return "progress_bar"
    if cls == "QScrollArea":
        return "scroll_area"
    if cls == "QGroupBox":
        return "group_box"
    if cls == "QTabWidget":
        return "tab_widget"
    if cls == "QTreeView" or cls == "QListView" or cls == "QListWidget":
        return "list_view"
    if cls == "QFrame":
        return "frame" + (f" #{name}" if name else "")
    if cls == "QStackedWidget":
        return "stacked_widget"
    if cls == "QMainWindow":
        return "control_center"
    if cls == "QDialog":
        return "dialog"
    if cls == "QMenuBar":
        return "menu_bar"
    if cls == "QToolBar":
        return "tool_bar"
    if cls == "QStatusBar":
        return "status_bar"
    return cls.lower()


def _widget_entry(widget: QWidget, depth: int = 0) -> Dict[str, Any]:
    """Costruisce l'entry JSON per un singolo widget (senza ricorsione)."""
    try:
        geo = widget.geometry()
        rect = [geo.x(), geo.y(), geo.width(), geo.height()]
    except Exception:
        rect = [0, 0, 0, 0]

    entry: Dict[str, Any] = {
        "class": widget.__class__.__name__,
        "objectName": widget.objectName() or "",
        "role": _role_hint(widget),
        "text": (widget.text().strip()[:120] if hasattr(widget, "text") else ""),
        "geometry": rect,
        "visible": bool(widget.isVisible()),
        "enabled": bool(widget.isEnabled()),
        "depth": depth,
    }
    # tooltip se presente (utile contesto per l'LLM)
    try:
        tip = widget.toolTip().strip()
        if tip:
            entry["toolTip"] = tip[:120]
    except Exception:
        pass
    # stato speciale
    try:
        if hasattr(widget, "isChecked") and callable(widget.isChecked):
            entry["checked"] = bool(widget.isChecked())
    except Exception:
        pass
    return entry


def build_tree(root: QWidget, max_depth: int = 12) -> List[Dict[str, Any]]:
    """Costruisce l'albero gerarchico dei widget a partire da root."""
    tree: List[Dict[str, Any]] = []

    def _walk(widget: QWidget, depth: int, parent_path: str) -> None:
        if depth > max_depth:
            return
        entry = _widget_entry(widget, depth)
        entry["path"] = parent_path + ">" + widget.__class__.__name__ + (
            f"#{widget.objectName()}" if widget.objectName() else ""
        )
        tree.append(entry)
        # figli diretti tramite layout + findChildren limitato al primo livello
        try:
            children = widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly)
        except Exception:
            children = []
        # fallback: layout children
        if not children:
            lay = widget.layout()
            if lay is not None:
                for i in range(lay.count()):
                    item = lay.itemAt(i)
                    if item is None:
                        continue
                    w = item.widget()
                    if w is not None:
                        children.append(w)
        for child in children:
            _walk(child, depth + 1, entry["path"])

    from PyQt6.QtCore import Qt  # noqa: PLC0415 (import locale per avoid ciclico)
    _walk(root, 0, "root")
    return tree


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

def grab_screenshot(widget: QWidget) -> QImage:
    """Ritorna l'immagine del widget (grab del widget stesso)."""
    # assicura che il widget sia stato mostrato / resizeato altrimenti grab è vuoto
    if not widget.isVisible():
        widget.show()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    pixmap = widget.grab()
    return pixmap.toImage()


def save_outputs(
    widget: QWidget,
    out_prefix: str,
    tree: List[Dict[str, Any]],
    write_image: bool = True,
) -> Dict[str, str]:
    """Salva immagine + JSON + TXT. Ritorna i path prodotti."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _ts()
    base = f"{out_prefix}_{stamp}"
    produced: Dict[str, str] = {}

    if write_image:
        img_path = LOG_DIR / f"{base}_screenshot.png"
        img = grab_screenshot(widget)
        img.save(str(img_path), "PNG")
        produced["screenshot"] = str(img_path)
        produced["screenshot_size"] = [img.width(), img.height()]

    # JSON albero (strutturato, per analisi LLM)
    json_path = LOG_DIR / f"{base}_tree.json"
    doc = {
        "timestamp": datetime.now().isoformat(),
        "widget_class": widget.__class__.__name__,
        "widget_objectName": widget.objectName() or "",
        "window_title": widget.windowTitle() or "",
        "geometry": [
            widget.geometry().x(),
            widget.geometry().y(),
            widget.geometry().width(),
            widget.geometry().height(),
        ],
        "widget_count": len(tree),
        "screenshot": produced.get("screenshot"),
        "screenshot_size": produced.get("screenshot_size"),
        "widgets": tree,
    }
    json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    produced["json"] = str(json_path)

    # TXT compatto (incollabile direttamente in un prompt LLM)
    txt_path = LOG_DIR / f"{base}_tree.txt"
    lines: List[str] = []
    lines.append(f"# GUI Diagnosis — {widget.windowTitle() or widget.__class__.__name__}")
    lines.append(f"Timestamp: {doc['timestamp']}")
    lines.append(f"Geometria: x={doc['geometry'][0]} y={doc['geometry'][1]} "
                 f"w={doc['geometry'][2]} h={doc['geometry'][3]}")
    lines.append(f"Widget totali: {doc['widget_count']}")
    lines.append("")
    for w in tree:
        indent = "  " * w["depth"]
        parts = [f"{indent}[{w['role']}] {w['class']}"]
        if w["objectName"]:
            parts.append(f"#{w['objectName']}")
        if w["text"]:
            parts.append(f'testo="{w["text"]}"')
        parts.append(f"geom=({w['geometry'][0]},{w['geometry'][1]},"
                     f"{w['geometry'][2]}x{w['geometry'][3]})")
        parts.append(f"vis={w['visible']} en={w['enabled']}")
        if w.get("checked") is not None:
            parts.append(f"checked={w['checked']}")
        lines.append(" ".join(parts))
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    produced["txt"] = str(txt_path)
    return produced


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_diagnostic(
    widget: Optional[QWidget] = None,
    out_prefix: str = DEFAULT_OUT,
    write_image: bool = True,
    max_depth: int = 12,
) -> Dict[str, str]:
    """Esegue la diagnostica su un widget. Se widget è None usa la finestra
    attiva di QApplication (se esiste), altrimenti crea una QApplication
    vuota e restituisce errore."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    target = widget
    if target is None:
        # usa la top-level widget più recente / attiva
        tops = app.topLevelWidgets()
        if not tops:
            raise RuntimeError("Nessuna finestra/top-level widget trovata. Passa un widget esplicito.")
        target = tops[-1]  # ultima creata (solitamente quella in primo piano)

    if not target.isVisible():
        target.show()
    app.processEvents()

    tree = build_tree(target, max_depth=max_depth)
    produced = save_outputs(target, out_prefix, tree, write_image=write_image)

    if os.environ.get("BSWARM_GUI_DEBUG", "").strip() == "1":
        print(f"[gui_diag] widget={target.__class__.__name__} "
              f"widgets={len(tree)} out_prefix={out_prefix}")
        for k, v in produced.items():
            print(f"[gui_diag] {k}: {v}")

    return produced


def _list_widgets(widget: QWidget, max_depth: int = 12) -> None:
    """Stampa solo l'albero su stdout (utile per analisi rapida)."""
    tree = build_tree(widget, max_depth=max_depth)
    print(f"# Albero widget — {widget.windowTitle() or widget.__class__.__name__}")
    print(f"Totale widget: {len(tree)}")
    for w in tree:
        indent = "  " * w["depth"]
        print(
            f"{indent}[{w['role']}] {w['class']}"
            + (f" #{w['objectName']}" if w["objectName"] else "")
            + (f' testo="{w["text"]}"' if w["text"] else "")
            + f" geom=({w['geometry'][0]},{w['geometry'][1]},"
              f"{w['geometry'][2]}x{w['geometry'][3]})"
            + f" vis={w['visible']} en={w['enabled']}"
        )


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnostica GUI BYTE-SWARMY: screenshot + albero accessibilità JSON per LLM.")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="Prefisso file output (default: gui_diag)")
    parser.add_argument("--no-image", action="store_true",
                        help="Non salvare l'immagine PNG (solo JSON/TXT)")
    parser.add_argument("--list", action="store_true",
                        help="Stampa solo l'albero su stdout (no file)")
    parser.add_argument("--max-depth", type=int, default=12,
                        help="Profondità massima ricorsione widget (default 12)")
    args = parser.parse_args()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    tops = app.topLevelWidgets()
    if not tops:
        print("ERRORE: nessuna finestra Qt aperta. Avvia prima byte-swarmy o passa un widget.", file=sys.stderr)
        return 1

    target = tops[-1]
    target.show()
    app.processEvents()

    if args.list:
        _list_widgets(target, max_depth=args.max_depth)
        return 0

    produced = run_diagnostic(
        widget=target,
        out_prefix=args.out,
        write_image=not args.no_image,
        max_depth=args.max_depth,
    )
    print(f"Diagnostica completata.")
    for k, v in produced.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
