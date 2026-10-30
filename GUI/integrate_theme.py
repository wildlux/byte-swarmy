#!/usr/bin/env python3
"""integrate_theme.py — Integra il nuovo tema QSS (light/dark) in BYTE-SWARMY."""
import shutil
from pathlib import Path

ROOT = Path(".")
THEME_DIR = ROOT / "GUI" / "theme"
GUI_FILE = ROOT / "GUI" / "main_window.py"
GUI_BACKUP = GUI_FILE.with_suffix(".py.bak.theme")


def create_theme_files():
    """Crea GUI/theme/ con theme.py, light.qss, dark.qss."""
    THEME_DIR.mkdir(parents=True, exist_ok=True)
    
    # theme.py
    (THEME_DIR / "__init__.py").write_text("")
    (THEME_DIR / "theme.py").write_text('''"""Gestione temi QSS per BYTE-SWARMY."""
from pathlib import Path
from PyQt6.QtCore import QSettings

THEME_DIR = Path(__file__).parent
SETTINGS = ("byte-swarmy", "control-center")


def _load(name):
    return (THEME_DIR / (name + ".qss")).read_text(encoding="utf-8")


def current_theme():
    return QSettings(*SETTINGS).value("theme", "dark")


def apply_theme(app, name=None):
    name = name or current_theme()
    app.setStyleSheet(_load(name))
    QSettings(*SETTINGS).setValue("theme", name)
    return name


def toggle_theme(app):
    return apply_theme(app, "dark" if current_theme() == "light" else "light")


def set_prop(widget, prop, value):
    """Cambia una property dinamica e rinfresca lo stile."""
    widget.setProperty(prop, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
''')
    
    # light.qss
    (THEME_DIR / "light.qss").write_text("""/* BYTE-SWARMY - tema chiaro */
* { font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif; font-size: 10.5pt; font-style: normal; font-weight: 400; }
QWidget { background: #f6f7f9; color: #1f2430; }
QMainWindow, QDialog { background: #f6f7f9; }
QToolTip { background: #1f2430; color: #ffffff; border: none; padding: 4px 8px; }
QTabWidget::pane { border: none; border-top: 1px solid #dfe3ea; background: #f6f7f9; }
QTabBar::tab { background: transparent; color: #5b6475; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; margin-right: 4px; }
QTabBar::tab:hover { color: #1f2430; }
QTabBar::tab:selected { color: #1f2430; font-weight: 600; border-bottom: 2px solid #2f6fed; }
QPushButton { background: #ffffff; border: 1px solid #d3d8e0; border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { background: #eef2f9; border-color: #b9c2d0; }
QPushButton:pressed { background: #e2e8f3; }
QPushButton[role="primary"] { background: #2f6fed; color: #ffffff; border-color: #2f6fed; font-weight: 600; }
QPushButton[role="start"] { background: #1e8e5a; color: #ffffff; border-color: #1e8e5a; font-weight: 600; }
QPushButton[role="stop"] { background: #c0392b; color: #ffffff; border-color: #c0392b; font-weight: 600; }
QLineEdit, QSpinBox, QComboBox { background: #ffffff; border: 1px solid #d3d8e0; border-radius: 6px; padding: 5px 8px; }
QLineEdit:focus { border: 1px solid #2f6fed; }
QLineEdit#quickCommand { padding: 8px 12px; font-size: 11.5pt; }
QTableWidget { background: #ffffff; border: 1px solid #dfe3ea; border-radius: 6px; alternate-background-color: #f9fafc; gridline-color: transparent; selection-background-color: #e3edff; }
QHeaderView::section { background: #f6f7f9; color: #5b6475; font-weight: 600; padding: 6px 8px; border: none; border-bottom: 1px solid #dfe3ea; }
QGroupBox { background: #ffffff; border: 1px solid #dfe3ea; border-radius: 8px; margin-top: 14px; padding: 12px; }
QLabel[role="muted"] { color: #6b7587; }
QLabel[role="metric"] { font-size: 20pt; font-weight: 600; }
QLabel[state="done"] { color: #176f46; background: #dff3e8; border-radius: 9px; padding: 2px 10px; }
QLabel[state="running"] { color: #1c4fb0; background: #dde8ff; border-radius: 9px; padding: 2px 10px; }
QLabel[state="pending"] { color: #8a5a00; background: #fff0cf; border-radius: 9px; padding: 2px 10px; }
QLabel[state="failed"] { color: #a32a1d; background: #fde3df; border-radius: 9px; padding: 2px 10px; }
QLabel[thermal="normal"] { color: #176f46; background: #dff3e8; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QLabel[thermal="warm"] { color: #8a5a00; background: #fff0cf; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QLabel[thermal="hot"] { color: #a32a1d; background: #fde3df; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #c5ccd8; border-radius: 5px; min-height: 30px; }
QStatusBar { background: #ffffff; border-top: 1px solid #dfe3ea; color: #5b6475; }
""")
    
    # dark.qss
    (THEME_DIR / "dark.qss").write_text("""/* BYTE-SWARMY - tema scuro */
* { font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif; font-size: 10.5pt; font-style: normal; font-weight: 400; }
QWidget { background: #14171d; color: #e6e9ef; }
QMainWindow, QDialog { background: #14171d; }
QToolTip { background: #e6e9ef; color: #1b1f27; border: none; padding: 4px 8px; }
QTabWidget::pane { border: none; border-top: 1px solid #2a303b; background: #14171d; }
QTabBar::tab { background: transparent; color: #9aa4b5; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; margin-right: 4px; }
QTabBar::tab:hover { color: #e6e9ef; }
QTabBar::tab:selected { color: #e6e9ef; font-weight: 600; border-bottom: 2px solid #5b92ff; }
QPushButton { background: #1b1f27; border: 1px solid #363d4a; border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { background: #242a35; border-color: #4a5365; }
QPushButton[role="primary"] { background: #5b92ff; color: #1b1f27; border-color: #5b92ff; font-weight: 600; }
QPushButton[role="start"] { background: #2aa86e; color: #1b1f27; border-color: #2aa86e; font-weight: 600; }
QPushButton[role="stop"] { background: #e5584a; color: #1b1f27; border-color: #e5584a; font-weight: 600; }
QLineEdit, QSpinBox, QComboBox { background: #1b1f27; border: 1px solid #363d4a; border-radius: 6px; padding: 5px 8px; }
QLineEdit:focus { border: 1px solid #5b92ff; }
QLineEdit#quickCommand { padding: 8px 12px; font-size: 11.5pt; }
QTableWidget { background: #1b1f27; border: 1px solid #2a303b; border-radius: 6px; alternate-background-color: #1e232c; gridline-color: transparent; selection-background-color: #1f3560; }
QHeaderView::section { background: #14171d; color: #9aa4b5; font-weight: 600; padding: 6px 8px; border: none; border-bottom: 1px solid #2a303b; }
QGroupBox { background: #1b1f27; border: 1px solid #2a303b; border-radius: 8px; margin-top: 14px; padding: 12px; }
QLabel[role="muted"] { color: #8f99ab; }
QLabel[role="metric"] { font-size: 20pt; font-weight: 600; }
QLabel[state="done"] { color: #6fd3a1; background: #173626; border-radius: 9px; padding: 2px 10px; }
QLabel[state="running"] { color: #a9c6ff; background: #1f3560; border-radius: 9px; padding: 2px 10px; }
QLabel[state="pending"] { color: #f0c56a; background: #3d2f10; border-radius: 9px; padding: 2px 10px; }
QLabel[state="failed"] { color: #ff9b8f; background: #3d1b17; border-radius: 9px; padding: 2px 10px; }
QLabel[thermal="normal"] { color: #6fd3a1; background: #173626; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QLabel[thermal="warm"] { color: #f0c56a; background: #3d2f10; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QLabel[thermal="hot"] { color: #ff9b8f; background: #3d1b17; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #3d4553; border-radius: 5px; min-height: 30px; }
QStatusBar { background: #1b1f27; border-top: 1px solid #2a303b; color: #9aa4b5; }
""")
    
    print("[1/2] Created GUI/theme/ with theme.py, light.qss, dark.qss")


def patch_gui():
    """Patch GUI/main_window.py per usare il nuovo tema."""
    if not GUI_FILE.exists():
        print("  ERROR: GUI/main_window.py not found")
        return False
    
    content = GUI_FILE.read_text()
    
    if "from GUI.theme.theme import apply_theme" in content:
        print("[2/2] Already patched")
        return True
    
    shutil.copy2(GUI_FILE, GUI_BACKUP)
    
    # 1. Sostituisci il vecchio STYLESHEET con il nuovo sistema
    # Cerca "app.setStyleSheet" nel main()
    old_main = "    app.setApplicationName"
    if old_main in content:
        new_main = """    # Apply new QSS theme
    try:
        from GUI.theme.theme import apply_theme
        theme = apply_theme(app)
        print(f"Theme: {theme}")
    except Exception as e:
        print(f"Theme load failed: {e}")
    
    app.setApplicationName"""
        content = content.replace(old_main, new_main, 1)
    
    # 2. Aggiungi scorciatoia Ctrl+Shift+T per toggle theme
    old_init = "        self._update_status_bar()"
    if old_init in content and "toggle_theme" not in content:
        new_init = """        self._update_status_bar()
        
        # Theme toggle shortcut (Ctrl+Shift+T)
        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, 
                  activated=lambda: self._toggle_theme())"""
        content = content.replace(old_init, new_init, 1)
    
    # 3. Aggiungi metodo _toggle_theme
    old_method = "    def _on_tab_changed"
    if old_method in content and "_toggle_theme" not in content:
        new_method = """    def _toggle_theme(self):
        \"\"\"Toggle light/dark theme.\"\"\"
        try:
            from GUI.theme.theme import toggle_theme
            import sys
            app = QApplication.instance()
            theme = toggle_theme(app)
            self.status_bar.showMessage(f"Theme: {theme}", 2000)
        except Exception as e:
            print(f"Theme toggle failed: {e}")
    
    def _on_tab_changed"""
        content = content.replace(old_method, new_method, 1)
    
    # 4. Imposta objectName sui widget chiave per il QSS
    # Quick command input
    content = content.replace(
        'self.quick_input = QLineEdit()',
        'self.quick_input = QLineEdit()\n            self.quick_input.setObjectName("quickCommand")',
        1
    )
    
    GUI_FILE.write_text(content)
    
    try:
        compile(content, "main_window.py", "exec")
        print("[2/2] Patched GUI/main_window.py: theme + Ctrl+Shift+T toggle")
        return True
    except SyntaxError as e:
        print(f"  SYNTAX ERROR: {e}")
        shutil.copy2(GUI_BACKUP, GUI_FILE)
        return False


def main():
    print("=" * 60)
    print("THEME INTEGRATION")
    print("=" * 60)
    
    create_theme_files()
    patch_gui()
    
    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print()
    print("Cosa cambia:")
    print("  - Nuovo tema QSS professionale (light + dark)")
    print("  - Font sans-serif normale (no piu' grassetto corsivo monospace)")
    print("  - Tab con sottolineatura blu (non riquadri)")
    print("  - Badge arrotondati per stati task (done/running/pending/failed)")
    print("  - Badge Timestral colorati (normal/warm/hot)")
    print("  - Scrollbar sottili")
    print("  - Toggle theme: Ctrl+Shift+T")
    print("  - Tema ricordato tra riavvii (QSettings)")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*gui' 2>/dev/null; sleep 1")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh --gui")


if __name__ == "__main__":
    main()
