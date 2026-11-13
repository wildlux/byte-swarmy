"""
GUI/panels.py — Widget e helper per le aree della plancia di controllo.

Estrae da GUI/control_center.py i componenti della plancia per rendere il
codice più modulare e manutenibile (obiettivo CU6: spezzare control_center.py).
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    QSizePolicy,
)


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


def build_config_page(theme_changed_callback, gui_debug_changed_callback):
    """Costruisce il pannello Impostazioni interattivo."""
    from GUI.settings_panel import SettingsPanel
    page = SettingsPanel()
    page.theme_changed.connect(theme_changed_callback)
    page.gui_debug_changed.connect(gui_debug_changed_callback)
    return page


def build_scheduler_page(get_project_path_callback):
    """Costruisce il pannello 'Coda Task' → TaskSchedulerPanel."""
    from GUI.task_scheduler_panel import TaskSchedulerPanel
    return TaskSchedulerPanel(get_project_path=get_project_path_callback)


def build_plancia_cards(open_panel_callback):
    """Costruisce la griglia di card della plancia (Code Task, Modelli, Config, CI/CD, Clean Code).

    Restituisce (cards_container_widget, cards_dict).
    """
    from GUI.control_center import PlanciaCard

    cards_grid = QGridLayout()
    cards_grid.setSpacing(12)
    cards_grid.setContentsMargins(0, 0, 0, 0)
    cards_grid.setColumnStretch(0, 1)
    cards_grid.setColumnStretch(1, 1)
    cards_grid.setColumnStretch(2, 1)
    cards_grid.setRowStretch(0, 0)
    cards_grid.setRowStretch(1, 0)

    cards = {}
    card_configs = [
        ("coda", "📋 Code Task",
         "Schedula compiti a orari previsti: uno-shot, ricorrenti o giornalieri",
         "Scheduler", "#f59e0b", 0, 0),
        ("modelli", "🤖 Modelli → Attori",
         "Imposta i 3 attori: LLM, Decision Model e Timestral (soglie termiche)",
         "3 attori", "#2563eb", 0, 1),
        ("config", "⚙️ Configurazione",
         "Scegli la tua configurazione GUI, Git e lingua",
         "Settings", "#16a34a", 0, 2),
        ("cicd", "🔄 CI/CD",
         "Pipeline di integrazione e delivery: build, test, deploy automatici",
         "Pipeline", "#dc2626", 1, 0),
        ("clean_code", "✨ Clean & Architecture Code",
         "Verifica qualità codice: lint, complexity, duplicazione, architettura",
         "Quality", "#7c3aed", 1, 1),
        ("test", "🧪 Test Suite",
         "Esegue la suite di test: runner per-file con timeout, esito salvato",
         "Tests", "#ea580c", 1, 2),
    ]

    for key, title, subtitle, badge, badge_color, row, col in card_configs:
        card = PlanciaCard(title, subtitle, badge=badge, badge_color=badge_color)
        card.clicked.connect(lambda k=key: open_panel_callback(k))
        cards[key] = card
        cards_grid.addWidget(card, row, col)

    cards_container = QWidget()
    cards_container.setLayout(cards_grid)
    cards_container.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    return cards_container, cards


def build_tools_cards(open_panel_callback, log_viewer, code_explorer, backup_logs,
                      integrity_panel, security_panel):
    """Costruisce la griglia di card degli strumenti di analisi.

    Restituisce (tools_container_widget, tools_cards_dict).
    """
    from GUI.control_center import PlanciaCard

    tools_grid = QGridLayout()
    tools_grid.setSpacing(12)
    tools_grid.setContentsMargins(0, 0, 0, 0)
    tools_grid.setColumnStretch(0, 1)
    tools_grid.setColumnStretch(1, 1)
    tools_grid.setColumnStretch(2, 1)
    tools_grid.setRowStretch(0, 0)
    tools_grid.setRowStretch(1, 0)
    tools_grid.setRowStretch(2, 0)

    tools_cards = {}
    tool_card_configs = [
        ("code_explorer", "🎮 Navigatore di codice",
         "Esplora classi, funzioni e variabili del progetto con grafo interattivo",
         "Explorer", "#0891b2", 0, 0),
        ("backup_logs", "💾 Backup Code — Git Logs",
         "Log dei push su GitHub, GitLab e Git generici con stato pipeline CI",
         "Backup", "#475569", 0, 1),
        ("logs", "📜 Log — Diario di Bordo",
         "Cronologia eventi del sistema: info, debug, success ed errori",
         "Logs", "#ca8a04", 0, 2),
        ("integrity", "🧪 Test di integrità",
         "Verifica checksum e integrità dei file critici del software",
         "Tests", "#0d9488", 1, 0),
        ("security", "🛡️ Sicurezza & anti-manomissione",
         "Scansioni di sicurezza, rilevamento manomissioni e hardening",
         "Security", "#b91c1c", 1, 1),
        ("audit_project", "🔍 Audit Progetto",
         "Quality gate su un progetto target: porte esposte, tunnel, codice morto",
         "Gate", "#9333ea", 1, 2),
        ("hardware", "🖥️ Hardware & Modelli",
         "Rilevamento GPU/memoria: strategia auto-suggerita per Worker e modelli",
         "Hardware", "#0891b2", 2, 0),
    ]

    for key, title, subtitle, badge, badge_color, row, col in tool_card_configs:
        card = PlanciaCard(title, subtitle, badge=badge, badge_color=badge_color)
        card.clicked.connect(lambda k=key: open_panel_callback(k))
        tools_cards[key] = card
        tools_grid.addWidget(card, row, col)

    tools_container = QWidget()
    tools_container.setLayout(tools_grid)
    tools_container.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    return tools_container, tools_cards


__all__ = [
    "wrap_in_panel_page",
    "build_actors_page",
    "build_cicd_page",
    "build_clean_code_page",
    "build_config_page",
    "build_scheduler_page",
    "build_plancia_cards",
    "build_tools_cards",
]

