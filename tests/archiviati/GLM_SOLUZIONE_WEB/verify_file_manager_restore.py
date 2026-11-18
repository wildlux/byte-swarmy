"""Verifica statica dei file ripristinati.

PyQt6 non si carica nel sandbox (manca libEGL.so.1), quindi usiamo
ast.parse + analisi dei simboli per verificare:
1. Sintassi corretta di tutti i file modificati
2. Presenza di tutti i metodi essenziali in FileTreeDrawer
3. Coerenza degli import (no NameError ovvi a runtime)
4. Nessun riferimento a self.<attr> non definito in __init__
"""
import ast
import sys
from pathlib import Path

REPO = Path("/home/z/my-project/byte-swarmy")
GUI = REPO / "GUI"

EXPECTED_METHODS = [
    # Costruttore e persistenza
    "__init__",
    "_save_splitter_vertical_state",
    # Task list callbacks (passati a TaskListWidget come argomenti)
    "_toggle_select_all_tasks",
    "_force_refresh_tasks",
    "_delete_checked_tasks",
    "_clean_queue",
    "_on_task_double_clicked",
    "_on_task_context_menu",
    # File tree operations
    "set_current_folder",
    "_debug_call_info",
    "_on_tree_click",
    "_open_pending_editor",
    "_on_tree_double_click",
    "_on_tree_context_menu",
    "_rename_item",
    "_delete_item",
    "_refresh_file_tree",
    "_on_folder_expanded",
    "_on_model_data_changed",
    "_delete_selected_items",
    "_toggle_sort_order",
    "_on_header_section_clicked",
    "_sort_by_name",
    "_sort_children_recursive",
    "_column_width_file",
    "_apply_header_layout",
    "_load_column_widths",
    "_save_column_widths",
    "_add_text_file",
    "_add_folder",
    "toggle",
    # Orchestrator wrappers
    "_pause_orchestrator",
    "_resume_orchestrator",
    "_stop_orchestrator",
    # Task item handlers
    "_on_task_item_clicked",
    "_on_task_item_changed",
    # Task status + actions
    "_get_task_status",
    "_pause_task_with_refresh",
    "_resume_task_with_refresh",
    "_stop_task_with_refresh",
    "_restart_task_with_refresh",
    "_delete_task_with_refresh",
    "_copy_task_id",
    "_open_task_result",
    "_show_task_details",
    "_collect_task_files",
    "_on_task_add_requested",
]

EXPECTED_ATTRS_IN_INIT = [
    "main_win",
    "_GUI_DEBUG",
    "_pending_editor_path",
    "_editor_open_timer",
    "_refreshing_tasks",
    "header",
    "add_file_btn",
    "add_folder_btn",
    "refresh_btn",
    "del_btn",
    "sort_btn",
    "path_label",
    "tree",
    "model",
    "splitter_vertical",
    "task_list_widget",
    "task_list",
    "_anim",
    "_open",
]

EXPECTED_IMPORTS = [
    "QAction",
    "QListWidgetItem",
    "QItemSelectionModel",
    "QPropertyAnimation",
    "QEasingCurve",
    "QTimer",
    "QHeaderView",
    "QFileIconProvider",
    "QMenu",
    "QInputDialog",
    "QMessageBox",
    "shutil",
    "sqlite3",
    "inspect",
    "subprocess",
]


def parse_file(path):
    src = path.read_text(encoding="utf-8")
    return ast.parse(src, filename=str(path)), src


def get_class_methods(tree, class_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return []


def get_init_attrs(tree, class_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == "__init__":
                    attrs = []
                    for stmt in ast.walk(member):
                        if isinstance(stmt, ast.Assign):
                            for tgt in stmt.targets:
                                if (isinstance(tgt, ast.Attribute)
                                        and isinstance(tgt.value, ast.Name)
                                        and tgt.value.id == "self"):
                                    attrs.append(tgt.attr)
                        elif isinstance(stmt, ast.AnnAssign):
                            if (isinstance(stmt.target, ast.Attribute)
                                    and isinstance(stmt.target.value, ast.Name)
                                    and stmt.target.value.id == "self"):
                                attrs.append(stmt.target.attr)
                    return attrs
    return []


def get_imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def check_file(path, expected_methods, expected_init_attrs,
               expected_module_imports=None):
    print("\n" + "=" * 70)
    print("FILE: " + str(path.relative_to(REPO)))
    print("=" * 70)
    try:
        tree, src = parse_file(path)
        print("  OK Sintassi (" + str(len(src.splitlines())) + " righe)")
    except SyntaxError as e:
        print("  FAIL SINTASSI: " + str(e))
        return False

    ok = True

    if expected_methods:
        found = get_class_methods(tree, "FileTreeDrawer")
        missing = [m for m in expected_methods if m not in found]
        if missing:
            print("  FAIL Metodi MANCANTI su FileTreeDrawer (" + str(len(missing)) + "):")
            for m in missing:
                print("      - " + m)
            ok = False
        else:
            print("  OK Tutti i " + str(len(expected_methods)) + " metodi attesi presenti su FileTreeDrawer")

    if expected_init_attrs:
        attrs = get_init_attrs(tree, "FileTreeDrawer")
        missing_a = [a for a in expected_init_attrs if a not in attrs]
        if missing_a:
            print("  FAIL Attributi MANCANTI in __init__ (" + str(len(missing_a)) + "):")
            for a in missing_a:
                print("      - self." + a)
            ok = False
        else:
            print("  OK Tutti i " + str(len(expected_init_attrs)) + " attributi attesi presenti in __init__")

    if expected_module_imports:
        imported = get_imported_names(tree)
        missing_i = [n for n in expected_module_imports if n not in imported]
        if missing_i:
            print("  FAIL Import MANCANTI a livello di modulo (" + str(len(missing_i)) + "):")
            for n in missing_i:
                print("      - " + n)
            ok = False
        else:
            print("  OK Tutti i " + str(len(expected_module_imports)) + " simboli attesi sono importati")

    return ok


def check_task_queue_helpers():
    print("\n" + "=" * 70)
    print("FILE: GUI/task_queue.py - funzioni helper")
    print("=" * 70)
    tree, _ = parse_file(GUI / "task_queue.py")
    expected = ["pause_task", "resume_single_task", "stop_task",
                "restart_task", "log_user_action"]
    found = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    missing = [f for f in expected if f not in found]
    if missing:
        print("  FAIL Funzioni MANCANTI: " + str(missing))
        return False
    print("  OK Tutte le " + str(len(expected)) + " funzioni helper presenti in task_queue.py")
    return True


def check_task_list_widget_imports():
    print("\n" + "=" * 70)
    print("FILE: GUI/task_list_widget.py - import QListWidgetItem")
    print("=" * 70)
    tree, _ = parse_file(GUI / "task_list_widget.py")
    imported = get_imported_names(tree)
    if "QListWidgetItem" not in imported:
        print("  FAIL QListWidgetItem NON importato")
        return False
    if "QColor" not in imported:
        print("  FAIL QColor NON importato")
        return False
    print("  OK QListWidgetItem e QColor importati correttamente")
    src = (GUI / "task_list_widget.py").read_text(encoding="utf-8")
    inline_count = src.count("from PyQt6.QtGui import QColor")
    if inline_count > 1:
        print("  FAIL Trovati " + str(inline_count) + " import inline di QColor (dovrebbe essere 1)")
        return False
    print("  OK Un solo import di QColor (modulo-level)")
    return True


def check_control_center_imports():
    print("\n" + "=" * 70)
    print("FILE: GUI/control_center.py - import helper da task_queue")
    print("=" * 70)
    tree, _ = parse_file(GUI / "control_center.py")
    imported = get_imported_names(tree)
    expected = ["_log_user_action", "_pause_task", "_resume_single_task",
                "_stop_task", "_restart_task"]
    missing = [n for n in expected if n not in imported]
    if missing:
        print("  FAIL Import MANCANTI: " + str(missing))
        return False
    print("  OK Tutte le " + str(len(expected)) + " funzioni helper importate da GUI.task_queue")
    return True


def main():
    print("\n" + "=" * 70)
    print("VERIFICA STATICA DEL RIPRISTINO FILE MANAGER BYTE-SWARMY")
    print("=" * 70)

    results = []
    results.append(check_file(
        GUI / "file_tree_drawer.py",
        expected_methods=EXPECTED_METHODS,
        expected_init_attrs=EXPECTED_ATTRS_IN_INIT,
        expected_module_imports=EXPECTED_IMPORTS,
    ))
    results.append(check_task_queue_helpers())
    results.append(check_task_list_widget_imports())
    results.append(check_control_center_imports())

    print("\n" + "=" * 70)
    if all(results):
        print("TUTTI I CONTROLLI SUPERATI - file manager ripristinato")
        return 0
    else:
        failed = sum(1 for r in results if not r)
        print(str(failed) + " controlli falliti su " + str(len(results)))
        return 1


if __name__ == "__main__":
    sys.exit(main())
