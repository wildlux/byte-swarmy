"""
GUI/panels.py — Widget e helper per le aree della plancia di controllo.

Estrae da GUI/control_center.py i componenti della plancia per rendere il
codice più modulare e manutenibile (obiettivo CU6: spezzare control_center.py).
"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def wrap_in_panel_page(
    title: str,
    widget: QWidget,
    back_callback,
) -> QWidget:
    """Avvolge un widget in una pagina con header "← Indietro" + titolo.

    Pattern comune per tutti i pannelli del detail_stack: header con
    pulsante Indietro + titolo, poi il widget content che riempie lo
    spazio restante.

    Args:
        title: Titolo della pagina (es. "Configurazione").
        widget: Widget contenuto da avvolgere.
        back_callback: Callable chiamato quando si clicca "Indietro".

    Ritorna:
        QWidget con il layout completo della pagina.
    """
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(14)

    # Header: pulsante Indietro + titolo
    head = QHBoxLayout()
    head.setSpacing(10)
    back = QPushButton("← Indietro alla Plancia (Backspace)")
    back.setObjectName("back_btn")
    back.clicked.connect(back_callback)
    head.addWidget(back)
    head.addStretch()
    title_lbl = QLabel(f"<b style='font-size:18px;'>{title}</b>")
    head.addWidget(title_lbl)
    head.addStretch()
    lay.addLayout(head)

    # Content: il widget vero e proprio.
    widget.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
    lay.addWidget(widget, stretch=1)
    return page


# ══════════════════════════════════════════════════════════════════════
# Costruttori pagine (estratti da CenterArea._build_*_page)
# ══════════════════════════════════════════════════════════════════════

def build_actors_page():
    """Costruisce il pannello Modelli → Attori."""
    from GUI.actors_panel import ActorsPanel
    return ActorsPanel()


def build_cicd_page():
    """Costruisce il pannello CI/CD → CICDPipelinePanel."""
    from GUI.control_center import CICDPipelinePanel
    return CICDPipelinePanel()


def build_clean_code_page():
    """Costruisce il pannello Clean & Architecture Code → CleanCodePanel."""
    from GUI.control_center import CleanCodePanel
    return CleanCodePanel()


__all__ = ["wrap_in_panel_page", "build_actors_page", "build_cicd_page", "build_clean_code_page"]

