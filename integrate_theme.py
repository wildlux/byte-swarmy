#!/usr/bin/env python3
"""integrate_theme.py — Integra il nuovo tema QSS in BYTE-SWARMY."""
import shutil
from pathlib import Path

ROOT = Path(".")
THEME_DIR = ROOT / "GUI" / "theme"
GUI_FILE = ROOT / "GUI" / "main_window.py"
GUI_BACKUP = GUI_FILE.with_suffix(".py.bak.theme")


def create_theme_files():
    THEME_DIR.mkdir(parents=True, exist_ok=True)
    (THEME_DIR / "__init__.py").write_text("")
    (THEME_DIR / "theme.py").write_text(
        '"""Gestione temi QSS per BYTE-SWARMY."""\n'
        'from pathlib import Path\n'
        'from PyQt6.QtCore import QSettings\n'
        'THEME_DIR = Path(__file__).parent\n'
        'SETTINGS = ("byte-swarmy", "control-center")\n'
        'def _load(name): return (THEME_DIR / (name + ".qss")).read_text(encoding="utf-8")\n'
        'def current_theme(): return QSettings(*SETTINGS).value("theme", "dark")\n'
        'def apply_theme(app, name=None):\n'
        '    name = name or current_theme()\n'
        '    app.setStyleSheet(_load(name))\n'
        '    QSettings(*SETTINGS).setValue("theme", name)\n'
        '    return name\n'
        'def toggle_theme(app): return apply_theme(app, "dark" if current_theme() == "light" else "light")\n'
        'def set_prop(widget, prop, value):\n'
        '    widget.setProperty(prop, value)\n'
        '    widget.style().unpolish(widget)\n'
        '    widget.style().polish(widget)\n'
    )
    (THEME_DIR / "light.qss").write_text(Path("/home/z/my-project/upload/light.qss").read_text() if Path("/home/z/my-project/upload/light.qss").exists() else "/* light theme */")
    (THEME_DIR / "dark.qss").write_text(Path("/home/z/my-project/upload/dark.qss").read_text() if Path("/home/z/my-project/upload/dark.qss").exists() else "/* dark theme */")
    print("[1/2] Created GUI/theme/")


def patch_gui():
    if not GUI_FILE.exists():
        return False
    content = GUI_FILE.read_text()
    if "from GUI.theme.theme import apply_theme" in content:
        print("[2/2] Already patched")
        return True
    shutil.copy2(GUI_FILE, GUI_BACKUP)
    old = "    app.setApplicationName"
    if old in content:
        content = content.replace(old, '    try:\n        from GUI.theme.theme import apply_theme\n        apply_theme(app)\n    except Exception as e:\n        print(f"Theme: {e}")\n\n    app.setApplicationName', 1)
    GUI_FILE.write_text(content)
    try:
        compile(content, "main_window.py", "exec")
        print("[2/2] Patched GUI/main_window.py")
        return True
    except SyntaxError as e:
        print(f"ERROR: {e}")
        shutil.copy2(GUI_BACKUP, GUI_FILE)
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("THEME INTEGRATION")
    print("=" * 50)
    create_theme_files()
    patch_gui()
    print("\nDone! Riavvia con: ./avvia.sh --gui")
    print("Toggle theme: Ctrl+Shift+T")
