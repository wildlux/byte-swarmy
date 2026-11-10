"""
GUI/settings_sections.py — Sezioni di UI per il pannello Impostazioni.

Estratto da GUI/settings_panel.py per ridurre il monolite.

Ogni sezione è un QFrame autonomo che accetta i callback di SettingsPanel
come argomenti del costruttore, così non c'è accoppiamento forte.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt as _Qt
from PyQt6.QtWidgets import (
    QComboBox, QCheckBox, QFormLayout, QFrame, QGroupBox, QLabel,
)
from GUI import settings_store
from GUI.theme import theme as _T
from GUI.theme.theme import set_prop as _theme_prop


# ═══════════════════════════════════════════════════════════════════
# Tema interfaccia
# ═══════════════════════════════════════════════════════════════════


class ThemeSection(QFrame):
    """Sezione per scegliere il tema (chiaro/scuro)."""

    def __init__(self, on_theme_changed, parent=None):
        super().__init__(parent)
        box = QGroupBox("🎨 Tema interfaccia")
        self.setLayout(QFormLayout())
        layout = self.layout()
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        self.theme_combo = QComboBox()
        groups = {"light": [], "dark": []}
        for _name in _T.available_themes():
            groups[_T.theme_kind(_name)].append(_name)
        for label, kind in (("— Temi chiari —", "light"),
                            ("— Temi scuri —", "dark")):
            if not groups[kind]:
                continue
            if self.theme_combo.count():
                self.theme_combo.insertSeparator(self.theme_combo.count())
            self.theme_combo.addItem(label)
            idx = self.theme_combo.count() - 1
            item = self.theme_combo.model().item(idx)
            item.setFlags(item.flags() & ~_Qt.ItemFlag.ItemIsEnabled)
            for _name in groups[kind]:
                self.theme_combo.addItem(_T.theme_display_name(_name), _name)
        # Preseleziona il tema salvato (non il primo della lista)
        cur = settings_store.get_theme()
        pos = self.theme_combo.findData(cur)
        if pos >= 0:
            self.theme_combo.setCurrentIndex(pos)
        self.theme_combo.currentIndexChanged.connect(on_theme_changed)
        layout.addRow("Tema:", self.theme_combo)

        hint = QLabel(
            "Il tema scuro è consigliato per i credits e per l'uso notturno.\n"
            "Il tema chiaro è più leggibile in ambienti luminosi."
        )
        hint.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(hint, "role", "muted")
        hint.setWordWrap(True)
        layout.addRow("", hint)


# ═══════════════════════════════════════════════════════════════════
# Lingua
# ═══════════════════════════════════════════════════════════════════


class LanguageSection(QFrame):
    """Sezione per scegliere la lingua (it/en) — Work in progress."""

    def __init__(self, on_lang_changed, parent=None):
        super().__init__(parent)
        box = QGroupBox("🌐 Lingua")
        self.setLayout(QFormLayout())
        layout = self.layout()
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("🇮🇹 Italiano", "it")
        self.lang_combo.addItem("🇬🇧 English", "en")
        self.lang_combo.setToolTip("Work in progress")
        self.lang_combo.currentIndexChanged.connect(on_lang_changed)
        layout.addRow("Lingua:", self.lang_combo)

        wip = QLabel(
            "⚠️ Work in progress — la lingua inglese sarà disponibile prossimamente."
        )
        wip.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(wip, "role", "wip")
        wip.setWordWrap(True)
        layout.addRow("", wip)


# ═══════════════════════════════════════════════════════════════════
# Debug GUI
# ═══════════════════════════════════════════════════════════════════


class DebugSection(QFrame):
    """Sezione Debug GUI: abilita la barra info-widget sotto il mouse."""

    def __init__(self, on_gui_debug_changed, parent=None):
        super().__init__(parent)
        box = QGroupBox("🐛 Debug GUI")
        self.setLayout(QFormLayout())
        layout = self.layout()
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        self.gui_debug_cb = QCheckBox(
            "Mostra info widget sotto il mouse nella barra in basso")
        self.gui_debug_cb.setToolTip(
            "Quando attivo, passa il mouse su qualsiasi bottone/campo/area: "
            "la barra in basso mostra classe, nome oggetto, gerarchia e "
            "stack delle chiamate (copiabile per segnalare allo sviluppatore)."
        )
        self.gui_debug_cb.setChecked(
            settings_store.get_gui_debug()
        )
        self.gui_debug_cb.stateChanged.connect(on_gui_debug_changed)
        layout.addRow("Debug widget:", self.gui_debug_cb)

        hint = QLabel(
            "Utile per individuare esattamente quale elemento GUI sta "
            "causando un comportamento inatteso, senza dover analizzare "
            "tutto il codice."
        )
        hint.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(hint, "role", "muted")
        hint.setWordWrap(True)
        layout.addRow("", hint)


# ═══════════════════════════════════════════════════════════════════
# Strategia Hardware
# ═══════════════════════════════════════════════════════════════════


class HardwareSection(QFrame):
    """H1: Sezione Strategia Hardware — bilanciamento CPU/GPU.

    4 modalità:
      - gpu+cpu: LLM su GPU, Decision+Timestral su CPU (potenza massima)
      - gpu_only: tutto su GPU
      - cpu_only: tutto su CPU
      - cpu_then_gpu: CPU default, fallback GPU se overload (archi vecchie)
    """

    def __init__(self, on_hw_changed, parent=None):
        super().__init__(parent)
        box = QGroupBox("⚡ Strategia Hardware")
        self.setLayout(QFormLayout())
        layout = self.layout()
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # Rileva GPU (status)
        from GUI.settings_store import is_gpu_available
        gpu_present = is_gpu_available()
        gpu_status_lbl = QLabel(
            f"{'✅ GPU rilevata' if gpu_present else '❌ GPU non rilevata (solo CPU disponibile)'}"
        )
        gpu_status_lbl.setStyleSheet(
            f"color:{'#16a34a' if gpu_present else '#dc2626'}; "
            f"font-weight:bold; font-size:11px;"
        )
        layout.addRow("Stato GPU:", gpu_status_lbl)

        # Combo strategia
        self.hw_combo = QComboBox()
        self.hw_combo.addItem("🚀 GPU+CPU — potenza massima (LLM su GPU, Decision su CPU)", "gpu+cpu")
        self.hw_combo.addItem("🎮 Solo GPU — tutto su GPU", "gpu_only")
        self.hw_combo.addItem("🖥️ Solo CPU — tutto su CPU", "cpu_only")
        self.hw_combo.addItem("🔄 CPU→GPU — default CPU, fallback GPU se overload", "cpu_then_gpu")
        # Disabilita opzioni GPU se non presente
        if not gpu_present:
            for i in range(self.hw_combo.count()):
                if self.hw_combo.itemData(i) in ("gpu+cpu", "gpu_only"):
                    item = self.hw_combo.model().item(i)
                    item.setEnabled(False)
                    item.setToolTip("GPU non rilevata — opzione non disponibile")
        self.hw_combo.currentIndexChanged.connect(on_hw_changed)
        layout.addRow("Strategia:", self.hw_combo)

        # Hint dinamico (descrizione della strategia selezionata)
        self.hw_hint = QLabel()
        self.hw_hint.setWordWrap(True)
        self.hw_hint.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(self.hw_hint, "role", "muted")
        self.update_hw_hint()
        layout.addRow("", self.hw_hint)

        # Checkbox auto-detect
        self.hw_auto_detect = QCheckBox(
            "Rileva GPU automaticamente all'avvio (sovrascrive se non scelta esplicita)"
        )
        self.hw_auto_detect.setStyleSheet("font-size:11px;")
        layout.addRow("", self.hw_auto_detect)

    # ------------------------------------------------------------------
    # Metodi di supporto (chiamati da SettingsPanel tramite i callback)
    # ------------------------------------------------------------------
    def current_strategy(self) -> str:
        """Ritorna la strategia hardware attualmente selezionata."""
        return self.hw_combo.currentData()

    def auto_detect_checked(self) -> bool:
        """Ritorna se l'auto-detect è spuntato."""
        return self.hw_auto_detect.isChecked()

    def update_hw_hint(self):
        """Aggiorna il testo descrittivo sotto la combo hardware."""
        from GUI.settings_store import get_effective_strategy_description
        strategy = self.hw_combo.currentData()
        self.hw_hint.setText(get_effective_strategy_description(strategy))
