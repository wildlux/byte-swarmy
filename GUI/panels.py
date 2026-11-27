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


def build_skills_page():
    """Costruisce il pannello Skill → SkillsPanel (elenco skill operative)."""
    from GUI.skills_panel import SkillsPanel
    return SkillsPanel()


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


PLANCIA_CATEGORIES = [
    {
        "key": "operativita",
        "title": "Operatività & AI",
        "icon": "🚀",
        "expanded": True,
        "subcategories": [
            ("Pianificazione", [
                ("coda", "📋 Code Task",
                 "Schedula compiti a orari previsti: one-shot, ricorrenti o giornalieri",
                 "Scheduler", "#f59e0b"),
            ]),
            ("Agenti", [
                ("modelli", "🤖 Modelli → Attori",
                 "Imposta i 3 attori: LLM, Decision Model e Timestral (soglie termiche)",
                 "3 attori", "#2563eb"),
            ]),
            ("Capacità", [
                ("skills", "🎓 Skill",
                 "Le skill operative del sistema: ricerca, report, calcoli, SQL, "
                 "diagrammi SVG — tutte mostrate nella Plancia",
                 "Skills", "#db2777"),
            ]),
        ],
    },
    {
        "key": "sviluppo",
        "title": "Sviluppo & Qualità",
        "icon": "🛠️",
        "expanded": False,
        "subcategories": [
            ("Pipeline & test", [
                ("cicd", "🔄 CI/CD",
                 "Pipeline di integrazione e delivery: build, test, deploy automatici",
                 "Pipeline", "#dc2626"),
                ("test", "🧪 Test Suite",
                 "Esegue la suite di test: runner per-file con timeout, esito salvato",
                 "Tests", "#ea580c"),
            ]),
            ("Qualità del codice", [
                ("clean_code", "✨ Clean & Architecture Code",
                 "Verifica qualità codice: lint, complexity, duplicazione, architettura",
                 "Quality", "#7c3aed"),
                ("audit_project", "🔍 Audit Progetto",
                 "Quality gate su un progetto target: porte esposte, tunnel, codice morto",
                 "Gate", "#9333ea"),
            ]),
            ("Debito tecnico", [
                ("debt_ledger", "🏛️ Registro del debito",
                 "Coda di rifattorizzazioni e ottimizzazioni: stato, priorità e "
                 "verifica anti-stantio (SQLite, pianificazione fredda)",
                 "Debt", "#b45309"),
            ]),
        ],
    },
    {
        "key": "analisi",
        "title": "Analisi & Report",
        "icon": "🔍",
        "expanded": False,
        "subcategories": [
            ("Esplorazione", [
                ("code_explorer", "🎮 Navigatore di codice",
                 "Esplora classi, funzioni e variabili del progetto con grafo interattivo",
                 "Explorer", "#0891b2"),
            ]),
            ("Cronologia", [
                ("logs", "📜 Log — Diario di Bordo",
                 "Cronologia eventi del sistema: info, debug, success ed errori",
                 "Logs", "#ca8a04"),
                ("backup_logs", "💾 Backup Code — Git Logs",
                 "Log dei push su GitHub, GitLab e Git generici con stato pipeline CI",
                 "Backup", "#475569"),
            ]),
            ("Report", [
                ("miglioramenti", "📈 Miglioramenti",
                 "Grafico dei miglioramenti implementati: audit, meccanismi di "
                 "robustezza, crescita dei test",
                 "Docs", "#059669"),
            ]),
        ],
    },
    {
        "key": "sicurezza",
        "title": "Sicurezza & Integrità",
        "icon": "🛡️",
        "expanded": False,
        "subcategories": [
            ("Hardening", [
                ("security", "🛡️ Sicurezza & anti-manomissione",
                 "Scansioni di sicurezza, rilevamento manomissioni e hardening",
                 "Security", "#b91c1c"),
            ]),
            ("Verifiche", [
                ("integrity", "🧪 Test di integrità",
                 "Verifica checksum e integrità dei file critici del software",
                 "Tests", "#0d9488"),
            ]),
        ],
    },
    {
        "key": "sistema",
        "title": "Hardware & Sistema",
        "icon": "🖥️",
        "expanded": False,
        "subcategories": [
            ("Hardware", [
                ("hardware", "🖥️ Hardware & Modelli",
                 "Rilevamento GPU/memoria: strategia auto-suggerita per Worker e modelli",
                 "Hardware", "#0891b2"),
                ("fan_control", "🌀 Ventole",
                 "Controllo ventole notebook HP via nbfc + pkexec (MAX/AUTO/OFF) — "
                 "prerequisito dei run LLM (limite termico 60°C)",
                 "Fan", "#0ea5e9"),
            ]),
            ("Sistema", [
                ("config", "⚙️ Configurazione",
                 "Scegli la tua configurazione GUI, Git e lingua",
                 "Settings", "#16a34a"),
            ]),
        ],
    },
]


def build_plancia_categories(open_panel_callback):
    """Costruisce le categorie arrotolabili della Plancia di controllo.

    Ogni categoria è una ``CollapsibleSection`` con eventuali sottocategorie;
    le card restano cliccabili e aprono il pannello corrispondente.

    Ritorna:
        (sections, cards, card_categories)
        - sections: dict category_key -> CollapsibleSection
        - cards: dict panel_key -> PlanciaCard
        - card_categories: dict panel_key -> category_key
    """
    from GUI.collapsible_section import CollapsibleSection
    from GUI.control_center import PlanciaCard

    sections = {}
    cards = {}
    card_categories = {}

    for cat in PLANCIA_CATEGORIES:
        section = CollapsibleSection(cat["title"], icon=cat["icon"])

        for sub_title, items in cat["subcategories"]:
            sub_lbl = QLabel(sub_title.upper())
            sub_lbl.setStyleSheet(
                "font-size:10px; font-weight:bold; letter-spacing:1px; "
                "padding:10px 2px 2px 2px; color:#64748b;"
            )
            section.add_widget(sub_lbl)

            grid = QGridLayout()
            grid.setSpacing(12)
            grid.setContentsMargins(0, 0, 0, 0)
            for col in range(3):
                grid.setColumnStretch(col, 1)

            for idx, (key, title, subtitle, badge, color) in enumerate(items):
                card = PlanciaCard(title, subtitle, badge=badge, badge_color=color)
                card.clicked.connect(lambda k=key: open_panel_callback(k))
                cards[key] = card
                card_categories[key] = cat["key"]
                grid.addWidget(card, idx // 3, idx % 3)

            container = QWidget()
            container.setLayout(grid)
            container.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            section.add_widget(container)

        if not cat.get("expanded", False):
            section.set_expanded(False)
        sections[cat["key"]] = section

    return sections, cards, card_categories

__all__ = [
    "wrap_in_panel_page",
    "build_actors_page",
    "build_cicd_page",
    "build_clean_code_page",
    "build_config_page",
    "build_skills_page",
    "build_scheduler_page",
    "build_plancia_categories",
    "PLANCIA_CATEGORIES",
]

