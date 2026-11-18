"""Verifica approfondita: cerca riferimenti self.<attr> non assegnati.

Per ogni attributo referenziato come self.X nei metodi di FileTreeDrawer,
verifica che X sia mai assegnato (in __init__ o in qualsiasi altro metodo).
Salta gli attributi ereditati da QFrame/Qt (style, parent, ecc.).
"""
import ast
import sys
from pathlib import Path

REPO = Path("/home/z/my-project/byte-swarmy")
GUI = REPO / "GUI"

# Attributi ereditati da QFrame/QWidget/Qt o gestiti dinamicamente
INHERITED_OK = {
    "parent", "close", "show", "hide", "update", "repaint", "isVisible",
    "isVisibleTo", "setMinimumWidth", "setMaximumWidth", "setMinimumHeight",
    "setMaximumHeight", "sizeHint", "minimumSizeHint", "geometry",
    "frameGeometry", "pos", "size", "x", "y", "width", "height",
    "rect", "contentsRect", "setGeometry", "move", "resize",
    "setSizePolicy", "sizePolicy", "setMinimumSize", "setMaximumSize",
    "setBaseSize", "baseSize", "sizeIncrement", "setSizeIncrement",
    "setWindowTitle", "windowTitle", "setWindowIcon", "windowIcon",
    "isWindow", "isModal", "isTopLevel", "isActiveWindow",
    "activateWindow", "raise_", "lower",
    "setFocus", "setFocusPolicy", "focusPolicy", "hasFocus",
    "font", "setFont", "layout", "setLayout", "layoutDirection",
    "setLayoutDirection", "style", "setStyle", "palette", "setPalette",
    "backgroundRole", "setBackgroundRole", "foregroundRole",
    "setForegroundRole", "styleSheet", "setStyleSheet",
    "objectName", "setObjectName", "findChild", "findChildren",
    "isWidgetType", "isWindowType", "isAncestorOf", "isDescendantOf",
    "isEnabled", "setEnabled", "isEnabledTo", "setVisible",
    "setHidden", "setShown", "showMinimized", "showMaximized",
    "showFullScreen", "showNormal", "isMinimized", "isMaximized",
    "isFullScreen", "mapToGlobal", "mapFromGlobal", "mapToParent",
    "mapFromParent", "mapTo", "mapFrom", "underMouse", "cursor", "setCursor",
    "unsetCursor", "grab", "render", "scroll", "widget", "setUpdatesEnabled",
    "updatesEnabled", "visibleRegion", "childrenRegion", "setMask", "mask",
    "clearMask", "setWindowOpacity", "windowOpacity", "setWindowFlags",
    "windowFlags", "windowState", "setWindowState", "saveGeometry",
    "restoreGeometry", "saveState", "restoreState", "setWindowState",
    "setParent", "setTabOrder", "focusWidget", "focusProxy", "setFocusProxy",
    "focusNextChild", "focusPreviousChild", "contextMenuPolicy",
    "setContextMenuPolicy", "cursor", "setCursor", "mouseTracking",
    "setMouseTracking", "tabletTracking", "setTabletTracking",
    "acceptDrops", "setAcceptDrops", "dragEnabled", "setDragEnabled",
    "statusBar",  # forward to main_win
    "centralWidget",  # forward to main_win
    "task_list",  # alias set in __init__
    "deleteLater",
}

# Attributi assegnati dinamicamente altrove (in metodi non-__init__)
DYNAMIC_OK = {
    "_pending_editor_path", "_editor_open_timer",
}


def collect_self_refs(tree, class_name):
    """Restituisce dict {attr: [line numbers]} per ogni self.attr usato in lettura."""
    refs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    for stmt in ast.walk(member):
                        if (isinstance(stmt, ast.Attribute)
                                and isinstance(stmt.value, ast.Name)
                                and stmt.value.id == "self"):
                            attr = stmt.attr
                            # Skip attribute writes: self.X = ...
                            # (handled separately)
                            refs.setdefault(attr, []).append(stmt.lineno)
    return refs


def collect_self_assigns(tree, class_name):
    """Restituisce set di attributi assegnati (self.X = ...) in qualsiasi metodo."""
    assigns = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    for stmt in ast.walk(member):
                        if isinstance(stmt, ast.Assign):
                            for tgt in stmt.targets:
                                if (isinstance(tgt, ast.Attribute)
                                        and isinstance(tgt.value, ast.Name)
                                        and tgt.value.id == "self"):
                                    assigns.add(tgt.attr)
                        elif isinstance(stmt, ast.AnnAssign):
                            if (isinstance(stmt.target, ast.Attribute)
                                    and isinstance(stmt.target.value, ast.Name)
                                    and stmt.target.value.id == "self"):
                                assigns.add(stmt.target.attr)
                        elif isinstance(stmt, ast.AugAssign):
                            if (isinstance(stmt.target, ast.Attribute)
                                    and isinstance(stmt.target.value, ast.Name)
                                    and stmt.target.value.id == "self"):
                                assigns.add(stmt.target.attr)
    return assigns


def main():
    print("\n" + "=" * 70)
    print("VERIFICA ATTRIBUTI SELF — file_tree_drawer.py")
    print("=" * 70)

    src = (GUI / "file_tree_drawer.py").read_text(encoding="utf-8")
    tree = ast.parse(src, filename="file_tree_drawer.py")

    refs = collect_self_refs(tree, "FileTreeDrawer")
    assigns = collect_self_assigns(tree, "FileTreeDrawer")

    # Attributi referenziati ma MAI assegnati
    never_assigned = []
    for attr, lines in sorted(refs.items()):
        if attr in assigns:
            continue
        if attr in INHERITED_OK:
            continue
        if attr in DYNAMIC_OK:
            continue
        # Metodi su self (chiamate come self.method())
        if attr in get_class_methods(tree, "FileTreeDrawer"):
            continue
        never_assigned.append((attr, lines))

    if never_assigned:
        print("FAIL Attributi self.X referenziati ma mai assegnati:")
        for attr, lines in never_assigned:
            print("  - self." + attr + " (linee: " + str(sorted(set(lines))) + ")")
        return 1
    else:
        print("OK Tutti gli attributi self.X sono assegnati da qualche parte")
        print("    (totale attributi unici assegnati: " + str(len(assigns)) + ")")
        return 0


def get_class_methods(tree, class_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return []


if __name__ == "__main__":
    sys.exit(main())
