"""
GUI/file_manager.py — Componenti del file manager (sidebar sinistra).

Contiene:
- FileSystemModel: QStandardItemModel con colonna checkbox per selezione multipla
  file/cartelle, lazy-loading delle cartelle, ordinamento cartelle prima dei file.
- CheckableTreeView: QTreeView che intercetta i click sulla checkbox (colonna 1)
  per gestire toggle + tracciamento click.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QFileInfo, QEvent, Qt
from PyQt6.QtGui import (QStandardItem, QStandardItemModel, QColor, QIcon,
                         QImage, QPixmap)
from PyQt6.QtWidgets import QTreeView, QFileIconProvider


def tint_icon_for_dark(icon: QIcon) -> QIcon:
    """Ri-tinta un'icona nativa (QFileIconProvider) per i temi scuri.

    L'icona "pagina bianca" generica ha un riempimento quasi bianco
    (224,224,224): nei temi scuri è un bagliore (regressione white
    panels — lo spot (60,300) del test cade proprio sull'icona).
    Remap dei soli pixel estremi, preservando l'alpha:
    - quasi bianchi (>0.78) → grigio-ardesia #aab2c0 (lum ≈0.70)
    - quasi neri (<0.18)    → grigio medio #6b7280 (i contorni neri
      della pagina scompaiono su fondo scuro)
    I toni medi (es. cartelle blu) restano invariati.
    """
    if icon is None or icon.isNull():
        return icon
    img = icon.pixmap(16, 16).toImage()
    if img.isNull():
        return icon
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    light = QColor("#aab2c0")
    dark = QColor("#6b7280")
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 12:
                continue
            lum = (0.2126 * c.red() + 0.7152 * c.green()
                   + 0.0722 * c.blue()) / 255.0
            if lum > 0.78:
                n = QColor(light)
                n.setAlpha(c.alpha())
                img.setPixelColor(x, y, n)
            elif lum < 0.18:
                n = QColor(dark)
                n.setAlpha(c.alpha())
                img.setPixelColor(x, y, n)
    return QIcon(QPixmap.fromImage(img))


class FileSystemModel(QStandardItemModel):
    """QStandardItemModel con colonna 0 checkbox per selezione multipla file/cartelle.

    Colonna 0: checkbox + gerarchia (freccette espansione)
    Colonna 1: nome + icona (solo dati)
    """

    def __init__(self):
        super().__init__()
        self.setColumnCount(4)
        self.setHeaderData(0, Qt.Orientation.Horizontal, "")  # colonna vuota: solo triangolino espandi/collassa
        self.setHeaderData(1, Qt.Orientation.Horizontal, "✓")
        self.setHeaderData(2, Qt.Orientation.Horizontal, "📄")
        self.setHeaderData(3, Qt.Orientation.Horizontal, "Name")
        self._checked_paths = set()
        self._root_path = ""
        self._icon_provider = QFileIconProvider()
        self._dark_icons = False  # icone ri-tintate per tema scuro
        # Ordinamento: True = cartelle prima poi file; False = file prima poi cartelle
        self._folders_first = True

    def set_dark_icons(self, dark: bool) -> None:
        """Attiva/disattiva le icone ri-tintate per tema scuro.

        Se lo stato cambia, rigenera le icone degli item GIÀ caricati
        (cambio tema live); i populate futuri usano lo stato corrente.
        """
        dark = bool(dark)
        changed = dark != self._dark_icons
        self._dark_icons = dark
        if changed:
            self._refresh_loaded_icons()

    def _current_icon(self, full_path: str) -> QIcon:
        """Icona provider (e ri-tintata se il tema è scuro) per un path."""
        icon = self._icon_provider.icon(QFileInfo(full_path))
        if self._dark_icons:
            icon = tint_icon_for_dark(icon)
        return icon

    def _refresh_loaded_icons(self) -> None:
        """Rigenera le icone di colonna 2 per tutti gli item caricati."""
        self._refresh_icons_rec(self.invisibleRootItem())

    def _refresh_icons_rec(self, parent_item) -> None:
        for r in range(parent_item.rowCount()):
            icon_item = parent_item.child(r, 2)
            if icon_item is not None:
                path = icon_item.data(Qt.ItemDataRole.UserRole)
                if path and not icon_item.icon().isNull():
                    icon_item.setIcon(self._current_icon(path))
            child = parent_item.child(r, 0)
            if child is not None and child.rowCount():
                self._refresh_icons_rec(child)

    def set_root_path(self, path):
        self._root_path = os.path.abspath(path)
        self.clear()
        self.setColumnCount(4)
        self.setHeaderData(0, Qt.Orientation.Horizontal, "")  # colonna vuota: solo triangolino
        self.setHeaderData(1, Qt.Orientation.Horizontal, "✓")
        self.setHeaderData(2, Qt.Orientation.Horizontal, "📄")
        self.setHeaderData(3, Qt.Orientation.Horizontal, "Name")
        root_item = self.invisibleRootItem()
        self._populate_folder(self._root_path, root_item)

    def _make_items(self, full_path, is_dir):
        # Colonna 0: vuota (solo per il triangolino di espansione del QTreeView)
        empty = QStandardItem()
        empty.setEditable(False)
        empty.setData(full_path, Qt.ItemDataRole.UserRole)
        empty.setData(is_dir, Qt.ItemDataRole.UserRole + 1)

        # Colonna 1: checkbox di selezione
        checkbox = QStandardItem()
        checkbox.setCheckable(True)
        checkbox.setCheckState(Qt.CheckState.Unchecked)
        checkbox.setEditable(False)
        checkbox.setData(full_path, Qt.ItemDataRole.UserRole)
        checkbox.setData(is_dir, Qt.ItemDataRole.UserRole + 1)

        # Colonna 2: icona (colonna dedicata, separata dal nome)
        icon_item = QStandardItem()
        icon_item.setEditable(False)
        icon_item.setData(full_path, Qt.ItemDataRole.UserRole)
        icon_item.setData(is_dir, Qt.ItemDataRole.UserRole + 1)
        icon = self._current_icon(full_path)
        icon_item.setIcon(icon)

        # Colonna 3: nome (senza icona)
        name = QStandardItem(os.path.basename(full_path))
        name.setData(full_path, Qt.ItemDataRole.UserRole)
        name.setData(is_dir, Qt.ItemDataRole.UserRole + 1)
        name.setEditable(False)
        # Tooltip con il percorso completo: il nome non si legge mai troncato
        name.setToolTip(full_path)
        icon_item.setToolTip(full_path)

        return empty, checkbox, icon_item, name

    def _make_empty_marker(self):
        """Riga 'Cartella vuota' (disabilitata, corsivo) per cartelle senza contenuti."""
        empty = QStandardItem()
        empty.setEnabled(False)
        checkbox = QStandardItem()
        checkbox.setEnabled(False)
        icon_item = QStandardItem()
        icon_item.setEnabled(False)
        name = QStandardItem("Cartella vuota")
        name.setEnabled(False)
        name.setEditable(False)
        font = name.font()
        font.setItalic(True)
        name.setFont(font)
        name.setData(False, Qt.ItemDataRole.UserRole + 1)  # non è una cartella
        return [empty, checkbox, icon_item, name]

    def _populate_folder(self, folder_path, parent_item):
        try:
            entries = sorted(os.listdir(folder_path))
        except Exception:
            return
        # Separa cartelle e file per poterle ordinare a gruppi
        dirs = []
        files = []
        for name in entries:
            # Salta file/cartelle di sistema che non devono apparire nell'albero
            if name == "__init__.py":
                continue
            if name == "__pycache__":
                continue
            if name.endswith(".pyc"):
                continue
            if name == ".git":
                continue
            if name == ".venv":
                continue
            if name.startswith(".") and name not in (".", ".."):
                continue
            full_path = os.path.join(folder_path, name)
            is_dir = os.path.isdir(full_path)
            if is_dir:
                dirs.append((name, full_path, is_dir))
            else:
                files.append((name, full_path, is_dir))
        if self._folders_first:
            ordered = dirs + files
        else:
            ordered = files + dirs
        # Cartella senza contenuti: mostra la riga "Cartella vuota"
        if not ordered:
            parent_item.appendRow(self._make_empty_marker())
            return
        for name, full_path, is_dir in ordered:
            empty, checkbox, icon_item, name_item = self._make_items(full_path, is_dir)
            parent_item.appendRow([empty, checkbox, icon_item, name_item])
            if is_dir:
                # UNA sola riga placeholder (disabilitata, non editabile) per far
                # comparire il triangolino di espansione lazy-loading.
                # Va appesa all'item di colonna 0: QTreeView mostra il triangolino
                # in base ai figli dell'item della prima colonna.
                placeholder = QStandardItem()
                placeholder.setEnabled(False)
                empty.appendRow([placeholder, QStandardItem(), QStandardItem(), QStandardItem()])

    def populate_on_expand(self, parent_item):
        """Chiamato quando una cartella viene espansa: popola i figli reali."""
        full_path = parent_item.data(Qt.ItemDataRole.UserRole)
        if not full_path or not os.path.isdir(full_path):
            return
        # Rimuovi placeholder esistenti
        while parent_item.rowCount() > 0:
            parent_item.removeRow(0)
        try:
            entries = sorted(os.listdir(full_path))
        except Exception:
            return
        # Separa cartelle e file per ordine (stessa logica di _populate_folder)
        dirs = []
        files = []
        for name in entries:
            # Salta file/cartelle di sistema che non devono apparire nell'albero
            if name == "__init__.py":
                continue
            if name == "__pycache__":
                continue
            if name.endswith(".pyc"):
                continue
            if name == ".git":
                continue
            if name == ".venv":
                continue
            if name.startswith(".") and name not in (".", ".."):
                continue
            child_full = os.path.join(full_path, name)
            is_dir = os.path.isdir(child_full)
            if is_dir:
                dirs.append((name, child_full, is_dir))
            else:
                files.append((name, child_full, is_dir))
        if self._folders_first:
            ordered = dirs + files
        else:
            ordered = files + dirs
        # Cartella senza contenuti: mostra la riga "Cartella vuota"
        if not ordered:
            parent_item.appendRow(self._make_empty_marker())
            return
        # Aggiungi figli reali (4 colonne: vuoto, checkbox, icona, nome)
        for name, child_full, is_dir in ordered:
            empty, checkbox, icon_item, name_item = self._make_items(child_full, is_dir)
            parent_item.appendRow([empty, checkbox, icon_item, name_item])
            if is_dir:
                # UNA sola riga placeholder per il triangolino di espansione
                # (appesa all'item di colonna 0, vedi _populate_folder)
                placeholder = QStandardItem()
                placeholder.setEnabled(False)
                empty.appendRow([placeholder, QStandardItem(), QStandardItem(), QStandardItem()])

    def checked_paths(self):
        return set(self._checked_paths)

    def clear_checks(self):
        self._checked_paths.clear()

    def filePath(self, index):
        """Ritorna il path assoluto memorizzato in UserRole sull'item.

        Compatibile con QStandardItemModel (che non espone filePath come
        QFileSystemModel): il path viene letto dal ruolo UserRole impostato
        in _make_items / populate_on_expand.
        """
        if not index.isValid():
            return ""
        item = self.itemFromIndex(index)
        if item is None:
            return ""
        return item.data(Qt.ItemDataRole.UserRole) or ""

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        f = super().flags(index)
        if index.column() == 1:
            f |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
        return f

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.column() == 1 and role == Qt.ItemDataRole.CheckStateRole:
            item = self.itemFromIndex(index)
            if item is None:
                return False
            fp = item.data(Qt.ItemDataRole.UserRole)
            if value == Qt.CheckState.Checked:
                self._checked_paths.add(fp)
            else:
                self._checked_paths.discard(fp)
            result = super().setData(index, value, role)
            self.dataChanged.emit(index, index, [role])
            return result
        return super().setData(index, value, role)


class CheckableTreeView(QTreeView):
    """QTreeView che intercetta i click sulla checkbox (colonna 1)
    per gestire toggle + log senza dipendere da dataChanged."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drawer = None

    def set_drawer(self, drawer):
        self._drawer = drawer

    def mousePressEvent(self, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            index = self.indexAt(event.pos())
            if index.isValid() and index.column() == 1:
                item = self.model().itemFromIndex(index)
                if item is not None and item.isCheckable():
                    fp = item.data(Qt.ItemDataRole.UserRole)
                    current = item.checkState()
                    new_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
                    item.setCheckState(new_state)
                    # Log del click (import lazy per evitare import circolare)
                    try:
                        from GUI.control_center import _click_log
                        _click_log(
                            "filemanager",
                            "seleziona" if new_state == Qt.CheckState.Checked else "deseleziona",
                            self._drawer.main_win.get_current_project_path()
                            if self._drawer and self._drawer.main_win else "",
                            fp,
                        )
                    except Exception:
                        pass
                    event.accept()
                    return
        super().mousePressEvent(event)


__all__ = ["FileSystemModel", "CheckableTreeView"]
