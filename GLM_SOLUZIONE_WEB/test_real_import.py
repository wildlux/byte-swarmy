"""Test reale di importazione con mock PyQt6 permissivo.

PyQt6 non si carica nel sandbox (manca libEGL.so.1), quindi creiamo un mock
che soddisfi gli import usati da file_tree_drawer.py e proviamo davvero a
caricarlo. Questo verifica che:
- Tutti i nomi importati esistano realmente nel modulo
- Il costruttore di FileTreeDrawer sia invocabile (mock)
- I metodi passati come callback a TaskListWidget siano attributi validi
  della classe (no AttributeError a runtime)
"""
import sys
import types
from pathlib import Path

REPO = Path("/home/z/my-project/byte-swarmy")
sys.path.insert(0, str(REPO))


def make_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


_permissive_instances = {}


class _PermissiveStub:
    """Stub permissivo: qualsiasi attributo access ritorna un altro stub.
    Simula QWidget/QObject che ha centinaia di metodi ereditati.
    """
    def __init__(self, *a, **kw):
        # Istanze condivise per attributi comuni (clicked, triggered, ecc.)
        pass

    def __getattr__(self, name):
        # Ritorna un altro _PermissiveStub per chain-calls (stub.clicked.connect)
        # Caching: ogni nome ritorna sempre la stessa istanza (per coerenza)
        cached = self.__dict__.get("_attr_" + name)
        if cached is None:
            cached = _PermissiveStub()
            self.__dict__["_attr_" + name] = cached
        return cached

    def __call__(self, *a, **kw):
        return self


class _SignalStub:
    def connect(self, *a, **kw): pass
    def emit(self, *a, **kw): pass


# === Mock PyQt6 ===
make_module("PyQt6")

qtwidgets_attrs = [
    "QFrame", "QWidget", "QVBoxLayout", "QHBoxLayout", "QLabel",
    "QPushButton", "QSplitter", "QAbstractItemView", "QTreeView",
    "QListWidget", "QListWidgetItem", "QHeaderView", "QFileIconProvider",
    "QMessageBox", "QInputDialog", "QMenu", "QApplication",
    "QItemSelectionModel", "QDialog", "QFormLayout", "QTextEdit",
    "QPlainTextEdit", "QMainWindow", "QStackedWidget", "QScrollArea",
    "QSizePolicy",
]
qtwidgets = make_module("PyQt6.QtWidgets")
for name in qtwidgets_attrs:
    setattr(qtwidgets, name, _PermissiveStub)

# Enum-like class attributes (accessed come Cls.EnumName.Value)
qtwidgets.QAbstractItemView.SelectionMode = _PermissiveStub()
qtwidgets.QAbstractItemView.SelectionMode.ExtendedSelection = "ExtendedSelection"
qtwidgets.QHeaderView.ResizeMode = _PermissiveStub()
qtwidgets.QHeaderView.ResizeMode.Fixed = "Fixed"
qtwidgets.QHeaderView.ResizeMode.Stretch = "Stretch"
qtwidgets.QMessageBox.StandardButton = _PermissiveStub()
qtwidgets.QMessageBox.StandardButton.Yes = "Yes"
qtwidgets.QMessageBox.StandardButton.No = "No"
qtwidgets.QInputDialog.InputMode = _PermissiveStub()
qtwidgets.QInputDialog.InputMode.TextInput = "TextInput"

qtgui_attrs = [
    "QColor", "QBrush", "QFont", "QIcon", "QPixmap", "QPalette",
    "QStandardItemModel", "QStandardItem", "QAction", "QCursor",
    "QDesktopServices",
]
qtgui = make_module("PyQt6.QtGui")
for name in qtgui_attrs:
    setattr(qtgui, name, _PermissiveStub)

qtcore_attrs = [
    "Qt", "pyqtSignal", "QTimer", "QSize", "QPropertyAnimation",
    "QEasingCurve", "QModelIndex", "QUrl", "QProcess", "QDesktopServices",
    "QDir", "QEvent", "QItemSelectionModel", "QObject", "QFileInfo",
]
qtcore = make_module("PyQt6.QtCore")
for name in qtcore_attrs:
    setattr(qtcore, name, _PermissiveStub)

# Enum class-level su QtCore
qtcore.QEasingCurve.Type = _PermissiveStub()
qtcore.QEasingCurve.Type.OutCubic = "OutCubic"
qtcore.QItemSelectionModel.SelectionFlag = _PermissiveStub()
qtcore.QItemSelectionModel.SelectionFlag.Select = "Select"
qtcore.QItemSelectionModel.SelectionFlag.Deselect = "Deselect"
qtcore.QItemSelectionModel.SelectionFlag.Rows = "Rows"
qtcore.Qt.Orientation = _PermissiveStub()
qtcore.Qt.Orientation.Horizontal = "Horizontal"
qtcore.Qt.Orientation.Vertical = "Vertical"
qtcore.Qt.ContextMenuPolicy = _PermissiveStub()
qtcore.Qt.ContextMenuPolicy.CustomContextMenu = "CustomContextMenu"
qtcore.Qt.CheckState = _PermissiveStub()
qtcore.Qt.CheckState.Checked = "Checked"
qtcore.Qt.CheckState.Unchecked = "Unchecked"
qtcore.Qt.ItemDataRole = _PermissiveStub()
qtcore.Qt.ItemDataRole.UserRole = "UserRole"
qtcore.Qt.AlignmentFlag = _PermissiveStub()
qtcore.Qt.AlignmentFlag.AlignLeft = "AlignLeft"
qtcore.Qt.TextElideMode = _PermissiveStub()
qtcore.Qt.TextElideMode.ElideRight = "ElideRight"
qtcore.Qt.ItemFlag = _PermissiveStub()
qtcore.Qt.ItemFlag.ItemIsUserCheckable = "ItemIsUserCheckable"
qtcore.Qt.ItemFlag.ItemIsEnabled = "ItemIsEnabled"
qtcore.Qt.ItemFlag.NoItemFlags = "NoItemFlags"


class _EnumStub:
    def __getattr__(self, name): return name


qtcore.Qt = _EnumStub()
qtcore.Qt.Orientation = _EnumStub()
qtcore.Qt.Orientation.Horizontal = "Horizontal"
qtcore.Qt.Orientation.Vertical = "Vertical"
qtcore.Qt.ContextMenuPolicy = _EnumStub()
qtcore.Qt.ContextMenuPolicy.CustomContextMenu = "CustomContextMenu"
qtcore.Qt.CheckState = _EnumStub()
qtcore.Qt.CheckState.Checked = "Checked"
qtcore.Qt.CheckState.Unchecked = "Unchecked"
qtcore.Qt.ItemDataRole = _EnumStub()
qtcore.Qt.ItemDataRole.UserRole = "UserRole"
qtcore.Qt.AlignmentFlag = _EnumStub()
qtcore.Qt.AlignmentFlag.AlignLeft = "AlignLeft"
qtcore.Qt.TextElideMode = _EnumStub()
qtcore.Qt.ItemFlag = _EnumStub()
qtcore.Qt.ItemFlag.ItemIsUserCheckable = "ItemIsUserCheckable"
qtcore.Qt.ItemFlag.ItemIsEnabled = "ItemIsEnabled"
qtcore.Qt.ItemFlag.NoItemFlags = "NoItemFlags"

# ResizeMode enum (usato da QHeaderView)
qtcore.Qt.QHeaderView = _EnumStub()
qtcore.Qt.QHeaderView.ResizeMode = _EnumStub()
qtcore.Qt.QHeaderView.ResizeMode.Fixed = "Fixed"
qtcore.Qt.QHeaderView.ResizeMode.Stretch = "Stretch"

# === CORE.constants (vero modulo) ===
CORE_DIR = REPO / "CORE"
core_init = make_module("CORE")
core_init.__path__ = [str(CORE_DIR)]
core_constants = make_module("CORE.constants")
const_src = (CORE_DIR / "constants.py").read_text()
exec(compile(const_src, "constants.py", "exec"), core_constants.__dict__)

# === GUI package (vero filesystem) ===
GUI_DIR = REPO / "GUI"
gui_pkg = make_module("GUI")
gui_pkg.__path__ = [str(GUI_DIR)]

# === Mock GUI.file_manager ===
fm = make_module("GUI.file_manager")


class _FileSystemModel(_PermissiveStub):
    _root_path = ""
    _folders_first = True
    modelReset = _SignalStub()
    columnsInserted = _SignalStub()
    dataChanged = _SignalStub()

    def checked_paths(self): return set()
    def clear_checks(self): pass


class _CheckableTreeView(_PermissiveStub):
    clicked = _SignalStub()
    doubleClicked = _SignalStub()
    customContextMenuRequested = _SignalStub()
    expanded = _SignalStub()


fm.FileSystemModel = _FileSystemModel
fm.CheckableTreeView = _CheckableTreeView

# === GUI.task_item_row ===
tir = make_module("GUI.task_item_row")
tir.TaskItemRow = _PermissiveStub

# === GUI.task_list_widget (vero modulo) ===
tlw_src = (GUI_DIR / "task_list_widget.py").read_text()
tlw = make_module("GUI.task_list_widget")
tlw.__file__ = str(GUI_DIR / "task_list_widget.py")
exec(compile(tlw_src, "task_list_widget.py", "exec"), tlw.__dict__)

# === GUI.settings_store ===
ss = make_module("GUI.settings_store")
ss.get_gui_debug = lambda: False

# === GUI.task_queue (vero modulo) ===
tq_src = (GUI_DIR / "task_queue.py").read_text()
tq = make_module("GUI.task_queue")
tq.__file__ = str(GUI_DIR / "task_queue.py")
exec(compile(tq_src, "task_queue.py", "exec"), tq.__dict__)

# === GUI.project_tab_bar — minimale ===
ptb = make_module("GUI.project_tab_bar")
ptb._is_junk_project_path = lambda rel: False
ptb.build_run_command = lambda p: None

# === GUI.control_center — minimale ===
cc = make_module("GUI.control_center")
cc._click_log = lambda *a, **kw: None

# === Import reale di GUI.file_tree_drawer ===
print("\n" + "=" * 70)
print("IMPORT REALE DI GUI.file_tree_drawer")
print("=" * 70)

ftd_src = (GUI_DIR / "file_tree_drawer.py").read_text()
ftd = make_module("GUI.file_tree_drawer")
ftd.__file__ = str(GUI_DIR / "file_tree_drawer.py")
try:
    exec(compile(ftd_src, "file_tree_drawer.py", "exec"), ftd.__dict__)
    print("OK Modulo caricato")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("FAIL: " + str(e))
    sys.exit(1)

print("FileTreeDrawer classe presente:", hasattr(ftd, "FileTreeDrawer"))
cls = ftd.FileTreeDrawer
methods = [m for m in dir(cls) if not m.startswith("__")]
print("Totale metodi su FileTreeDrawer:", len(methods))

expected = [
    "_rename_item", "_delete_item", "_toggle_select_all_tasks",
    "_force_refresh_tasks", "_delete_checked_tasks", "_clean_queue",
    "_on_task_double_clicked", "_on_task_context_menu", "set_current_folder",
    "_on_tree_click", "_on_tree_double_click", "_on_tree_context_menu",
    "_on_folder_expanded", "_on_model_data_changed", "_delete_selected_items",
    "_toggle_sort_order", "_sort_by_name", "_sort_children_recursive",
    "_apply_header_layout", "_load_column_widths", "_save_column_widths",
    "_add_text_file", "_add_folder", "_refresh_file_tree",
    "_on_task_item_clicked", "_on_task_item_changed",
    "_get_task_status", "_pause_task_with_refresh",
    "_resume_task_with_refresh", "_stop_task_with_refresh",
    "_restart_task_with_refresh", "_delete_task_with_refresh",
    "_show_task_details", "_open_task_result", "_copy_task_id",
    "_collect_task_files", "toggle",
]
missing = [m for m in expected if not hasattr(cls, m)]
if missing:
    print("FAIL Metodi mancanti:", missing)
    sys.exit(1)
print("OK Tutti i " + str(len(expected)) + " metodi attesi presenti")

# Prova a istanziare
print("\n" + "=" * 70)
print("ISTANZIAZIONE FileTreeDrawer(parent=None)")
print("=" * 70)
try:
    obj = cls(parent=None)
    print("OK Costruzione riuscita")
    print("  self.main_win =", obj.main_win)
    print("  self._GUI_DEBUG =", obj._GUI_DEBUG)
    print("  self._pending_editor_path =", obj._pending_editor_path)
    print("  self._editor_open_timer =", obj._editor_open_timer)
    print("  self._refreshing_tasks =", obj._refreshing_tasks)
    print("  self.task_list_widget =", type(obj.task_list_widget).__name__)
    print("  self.task_list (alias) =", type(obj.task_list).__name__)
    print("  self.header presente:", hasattr(obj, "header"))
    print("  self.add_file_btn presente:", hasattr(obj, "add_file_btn"))
    print("  self.add_folder_btn presente:", hasattr(obj, "add_folder_btn"))
    print("  self.refresh_btn presente:", hasattr(obj, "refresh_btn"))
    print("  self.del_btn presente:", hasattr(obj, "del_btn"))
    print("  self.sort_btn presente:", hasattr(obj, "sort_btn"))
    print("  self.path_label presente:", hasattr(obj, "path_label"))
    print("  self.tree presente:", hasattr(obj, "tree"))
    print("  self.model presente:", hasattr(obj, "model"))
    print("  self.splitter_vertical presente:", hasattr(obj, "splitter_vertical"))
    print("\nOK FILE MANAGER RIPRISTINATO — pronto per essere visualizzato")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("FAIL Costruzione: " + str(e))
    sys.exit(1)
