"""task_item_delegate.py — Delegate per le righe della lista "Lavori e Compiti".

Disegna direttamente (senza setItemWidget, che in QListWidget posiziona il
widget con geometrie sbagliate/schiacciate):
- checkbox di selezione 14px centrata a x=14  →  allineata col glifo ☑ del
  pulsante "seleziona tutto" (28px) nella barra sopra la lista;
- pallino/glyph di stato colorato (verde=fatto, giallo=in lavorazione,
  rosso=in attesa) letto da UserRole+2 (glyph) e UserRole+3 (colore);
- titolo (UserRole+1, fallback DisplayRole) con elide a destra.

Il toggle della checkbox avviene in ``editorEvent``: click nel rettangolo
della checkbox → ``model.setData(CheckStateRole)`` (emette itemChanged →
log/sync nel drawer). L'item NON ha il flag ItemIsUserCheckable: evita il
doppio toggle (Qt interno + delegate) e il click sul testo non tocca la ✓.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRect, QEvent
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication, QStyle, QStyleOptionButton, QStyleOptionViewItem,
    QStyledItemDelegate,
)

# Geometria condivisa paint/editorEvent (coordinate relative all'item)
CHECK_SIZE = 14
BTN_CENTER_X = 14    # centro del glifo ☑ nel pulsante 28px (primo della barra)
GLYPH_X = 27         # 21 + 6 di spacing
GLYPH_W = 18
TITLE_X = 51         # 27 + 18 + 6
TITLE_GAP = 6


class TaskItemDelegate(QStyledItemDelegate):
    """Delegate riga task: checkbox + pallino di stato colorato + titolo."""

    # ------------------------------------------------------------------
    # Disegno
    # ------------------------------------------------------------------

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        title = str(index.data(Qt.ItemDataRole.UserRole + 1)
                     or opt.text or "")
        glyph = str(index.data(Qt.ItemDataRole.UserRole + 2) or "○")
        color = str(index.data(Qt.ItemDataRole.UserRole + 3) or "#dc2626")
        checked = index.data(Qt.ItemDataRole.CheckStateRole)

        # Il testo nativo non va disegnato: gestiamo tutto noi.
        opt.text = ""

        style = (opt.widget.style() if opt.widget is not None
                 else QApplication.style())

        painter.save()
        # Sfondo: selezione / hover (stile nativo della vista)
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem,
                            opt, painter, opt.widget)

        rect = opt.rect
        # ── Checkbox □ / ☑ (allineata al ☑ del pulsante) ──
        check_rect = self._check_rect(rect, opt.widget)
        btn = QStyleOptionButton()
        btn.rect = check_rect
        btn.state = QStyle.StateFlag.State_Enabled
        if checked == Qt.CheckState.Checked.value or checked == Qt.CheckState.Checked:
            btn.state |= QStyle.StateFlag.State_On
        else:
            btn.state |= QStyle.StateFlag.State_Off
        if opt.state & QStyle.StateFlag.State_MouseOver:
            btn.state |= QStyle.StateFlag.State_MouseOver
        style.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorCheckBox,
                            btn, painter, opt.widget)

        # ── Pallino di stato colorato ──
        glyph_rect = QRect(rect.left() + GLYPH_X, rect.top(),
                           GLYPH_W, rect.height())
        glyph_font = opt.font
        glyph_font.setBold(True)
        painter.setFont(glyph_font)
        # Il glyph MANTIENE sempre il suo colore di stato (rosso/giallo/verde):
        # forzarlo bianco su selezione lo rendeva invisibile su sfondo chiaro.
        painter.setPen(QColor(color))
        painter.drawText(glyph_rect,
                         Qt.AlignmentFlag.AlignCenter, glyph)

        # ── Titolo (elide a destra) ──
        title_rect = QRect(rect.left() + TITLE_X, rect.top(),
                           rect.width() - TITLE_X - TITLE_GAP, rect.height())
        # Titolo in peso regolare (il tema mette la lista in bold; il
        # titolo task segue l'albero file che e' regolare).
        title_font = opt.font
        title_font.setBold(False)
        painter.setFont(title_font)
        # Sempre il colore testo del tema: su selezione (tinta chiara del
        # tema) resta leggibile; HighlightedText non rispecchia la qss.
        painter.setPen(opt.palette.color(QPalette.ColorRole.Text))
        elided = opt.fontMetrics.elidedText(
            title, Qt.TextElideMode.ElideRight, title_rect.width())
        painter.drawText(title_rect,
                         Qt.AlignmentFlag.AlignVCenter
                         | Qt.AlignmentFlag.AlignLeading, elided)
        painter.restore()

    # ------------------------------------------------------------------
    # Click sulla checkbox → toggle CheckStateRole
    # ------------------------------------------------------------------

    def editorEvent(self, event, model, option, index):
        # Solo release del tasto sinistro dentro il rettangolo della ✓
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        pos = event.position().toPoint() - option.rect.topLeft()
        if not self._check_rect(option.rect, option.widget).contains(pos):
            return False
        current = index.data(Qt.ItemDataRole.CheckStateRole)
        checked = (current == Qt.CheckState.Checked
                   or current == Qt.CheckState.Checked.value)
        nuovo = (Qt.CheckState.Unchecked if checked
                 else Qt.CheckState.Checked)
        model.setData(index, nuovo, Qt.ItemDataRole.CheckStateRole)
        return True

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _check_left(widget) -> int:
        """CHECK_X dinamico: allinea il centro della □ al centro del glifo
        ☑ del pulsante (x=14 nel widget lista), tenendo conto dell'offset
        del viewport (bordo+padding della qss del tema, di solito 5px).
        Senza questo la □ risultava ~5px piu' a destra del ☑."""
        off = 0
        if widget is not None:
            try:
                off = widget.viewport().pos().x()
            except Exception:
                off = 0
        # clamp >= 0: mai disegnare fuori dal viewport (verrebbe tagliata)
        return max(0, BTN_CENTER_X - CHECK_SIZE // 2 - off)

    @classmethod
    def _check_rect(cls, item_rect: QRect, widget=None) -> QRect:
        return QRect(item_rect.left() + cls._check_left(widget),
                     item_rect.top() + (item_rect.height() - CHECK_SIZE) // 2,
                     CHECK_SIZE, CHECK_SIZE)
