"""Pannello Impostazioni interattivo per BYTE-SWARMY.

Sostituisce la vecchia schermata di testo statica "Configurazione
BYTE-SWARMY: ..." con un pannello vero che permette di:

- scegliere il tema (chiaro / scuro) — applicato ai credits e all'app
- scegliere la lingua (italiano / inglese) — Work in progress
- configurare i remote Git (GitHub, GitLab, Git) con token e URL,
  usati dal pulsante floppy 💾 per il push automatico su tutti i remote
- eseguire l'audit mensile del software (variabili inutilizzate, codice
  morto, porte esposte, reverse proxy) con report HTML in logs/audit/
"""
import os
import subprocess
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QLineEdit, QMessageBox, QInputDialog, QScrollArea,
    QSizePolicy, QGroupBox, QFormLayout, QCheckBox, QPlainTextEdit,
    QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QThread, QObject, pyqtSignal as Signal
from PyQt6.QtGui import QDesktopServices

from GUI import settings_store
from GUI.theme.theme import set_prop as _theme_prop
from GUI.theme.theme import set_banner as _theme_banner
from GUI.audit_worker import AuditWorker
from GUI.hf_weights_worker import WeightsDownloadWorker, WeightspaceProveWorker
from GUI.settings_sections import (
    DebugSection, HardwareSection, LanguageSection, ThemeSection,
)
from CORE.gui_worker import BaseWorker

# ═══════════════════════════════════════════════════════════════
class SettingsPanel(QWidget):
    """Pannello impostazioni con tema, lingua e Git remotes."""

    # Segnale emesso quando il tema cambia (per applicazione live)
    theme_changed = pyqtSignal(str)  # "dark" | "light"
    # Segnale emesso quando il debug GUI viene attivato/disattivato
    gui_debug_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settings_panel")
        self._audit_worker: Optional[AuditWorker] = None
        self._build_ui()
        self._reload_from_store()

    # ──────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header con pulsante Indietro + titolo
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>⚙️ Impostazioni</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        # ── Barra di ricerca impostazioni ─────────────────────────────
        # Filtra le sezioni in tempo reale mentre l'utente digita.
        # Matcha su titolo della sezione + tutto il testo contenuto
        # (label, pulsanti, placeholder, descrizioni).
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "🔍 Cerca nelle impostazioni…  (es. \"tema\", \"git\", \"audit\", \"gpu\")"
        )
        self.search_input.setToolTip(
            "Cerca nelle impostazioni: titolo sezione + contenuto"
        )
        # Campo ricerca minimo ~30 caratteri (non collassa sotto quella soglia)
        self.search_input.setMinimumWidth(400)
        self.search_input.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_input, stretch=1)

        self.search_clear_btn = QPushButton("✕")
        self.search_clear_btn.setFixedSize(36, 36)
        self.search_clear_btn.setToolTip("Cancella ricerca")
        self.search_clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(self.search_clear_btn)
        outer.addLayout(search_row)

        # Contatore risultati (es. "4 di 5 sezioni visibili")
        self.search_count = QLabel("")
        self.search_count.setStyleSheet("font-size:11px; padding:0 4px;")
        _theme_prop(self.search_count, "role", "muted")
        outer.addWidget(self.search_count)

        # Scroll area per il contenuto (in caso di molti remote)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        content = QWidget()
        content.setObjectName("panelScrollContent")
        # NB: stylesheet con SELETTORE (non declaration-only), altrimenti
        # il "background: transparent" trasuda su tutti i figli e azzera
        # i bottoni role="start"/"danger" del tema app-level.
        content.setStyleSheet("QWidget#panelScrollContent { background: transparent; }")
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Sezioni impostazioni ──────────────────────────────────────
        # Ogni sezione viene registrata in self._sections per consentire
        # il filtraggio tramite la barra di ricerca.
        self._sections: list[tuple[str, QGroupBox]] = []

        def _add_section(name: str, widget: QGroupBox):
            lay.addWidget(widget)
            self._sections.append((name, widget))

        self.theme_section = ThemeSection(self._on_theme_changed)
        self.language_section = LanguageSection(self._on_lang_changed)
        self.debug_section = DebugSection(self._on_gui_debug_changed)
        self.hardware_section = HardwareSection(self._on_hw_changed)
        _add_section("tema", self.theme_section)
        _add_section("lingua", self.language_section)
        _add_section("debug", self.debug_section)
        _add_section("hardware", self.hardware_section)
        _add_section("git", self._build_git_section())
        _add_section("audit", self._build_audit_section())
        _add_section("pesi huggingface", self._build_weightspace_section())

        # Le sezioni riempiono lo spazio disponibile (niente stretch finale
        # che lasciava area vuota): l'audit_output usa il posto in più.

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # Stato iniziale: tutte le sezioni visibili
        self._update_search_count(len(self._sections), len(self._sections))

    # ──────────────────────────────────────────────────────────────────
    # Ricerca nelle impostazioni
    # ──────────────────────────────────────────────────────────────────
    def _on_search(self, text: str):
        """Filtra le sezioni in base al testo cercato.

        Non nasconde nulla: tutte le sezioni restano visibili per preservare
        la memoria visiva. Quelle che matchano vengono evidenziate (bordo
        accent + sfondo leggero), le altre restano in opacità ridotta.
        """
        query = text.strip().lower()
        if not query:
            for _name, section in self._sections:
                if hasattr(section, "_search_orig_style"):
                    section.setStyleSheet(section._search_orig_style)
                else:
                    section.setStyleSheet("")
            self._update_search_count(len(self._sections), len(self._sections))
            return

        visible = 0
        for name, section in self._sections:
            if not hasattr(section, "_search_orig_style"):
                section._search_orig_style = section.styleSheet()
            if self._section_matches(name, section, query):
                section.setStyleSheet(
                    "QGroupBox { border: 2px solid #2563eb; border-radius: 8px; "
                    "background: rgba(37,99,235,0.06); }"
                )
                visible += 1
            else:
                section.setStyleSheet(
                    "QGroupBox { border: 1px solid #555; opacity: 0.65; }"
                )

        self._update_search_count(visible, len(self._sections))

    def _section_matches(self, name: str, section: QGroupBox, query: str) -> bool:
        """True se la sezione contiene il termine cercato."""
        # 1. Match sul nome interno
        if query in name.lower():
            return True
        # 2. Match sul titolo della QGroupBox
        if query in section.title().lower():
            return True
        # 3. Match su tutto il testo contenuto nei child widget
        haystack_parts: list[str] = [name.lower(), section.title().lower()]
        from PyQt6.QtWidgets import QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox
        for child in section.findChildren(QObject):
            # Cerca in tutti i widget che hanno proprietà testuali
            if isinstance(child, QLabel):
                haystack_parts.append(child.text().lower())
            elif isinstance(child, QPushButton):
                haystack_parts.append(child.text().lower())
                tip = child.toolTip()
                if tip:
                    haystack_parts.append(tip.lower())
            elif isinstance(child, QLineEdit):
                ph = child.placeholderText()
                if ph:
                    haystack_parts.append(ph.lower())
            elif isinstance(child, QComboBox):
                for i in range(child.count()):
                    haystack_parts.append(child.itemText(i).lower())
            elif isinstance(child, QCheckBox):
                haystack_parts.append(child.text().lower())
        haystack = " ".join(haystack_parts)
        return query in haystack

    def _clear_search(self):
        """Cancella la ricerca e mostra tutte le sezioni."""
        self.search_input.clear()
        self.search_input.setFocus()

    def _update_search_count(self, visible: int, total: int):
        """Aggiorna l'etichetta del contatore risultati."""
        if visible == total:
            self.search_count.setText(f"{total} sezioni")
        else:
            self.search_count.setText(
                f"<b style='color:#2563eb;'>{visible}</b> di {total} sezioni visibili"
            )

    def _update_hw_hint(self):
        """Aggiorna il testo descrittivo sotto la combo hardware."""
        if hasattr(self, "hardware_section"):
            self.hardware_section.update_hw_hint()

    def _on_hw_changed(self, _idx: int):
        """H1: quando cambia strategia hardware, salva + aggiorna hint."""
        if hasattr(self, "hardware_section"):
            strategy = self.hardware_section.current_strategy()
            settings_store.set_hardware_strategy(strategy, user_set=True)
            # Salva anche lo stato dell'auto-detect checkbox
            s = settings_store.load_settings()
            s["detect_gpu_at_startup"] = self.hardware_section.auto_detect_checked()
            s["user_set_hardware_strategy"] = True
            settings_store.save_settings(s)
            self.hardware_section.update_hw_hint()

    def _build_git_section(self) -> QFrame:
        """Sezione per configurare i remote Git (GitHub/GitLab/Git) + token."""
        box = QGroupBox("💾 Remote Git — push automatico")

        outer = QVBoxLayout(box)
        outer.setSpacing(8)
        outer.setContentsMargins(14, 14, 14, 14)

        # Spiegazione
        expl = QLabel(
            "Configura qui i remote Git (GitHub, GitLab o generici). "
            "Salvando, il pulsante 💾 in alto a destra (floppy disk) "
            "farà il <b>push automatico</b> su tutti i remote configurati, "
            "usando il token per l'autenticazione."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet("font-size:11px;")
        _theme_prop(expl, "role", "muted")
        outer.addWidget(expl)

        # Form per aggiungere un remote
        form_row = QFormLayout()
        form_row.setSpacing(6)

        self.git_name_edit = QLineEdit()
        self.git_name_edit.setPlaceholderText("origin")
        form_row.addRow("Nome remote:", self.git_name_edit)

        self.git_url_edit = QLineEdit()
        self.git_url_edit.setPlaceholderText("https://github.com/wildlux/byte-swarmy.git")
        form_row.addRow("URL repo:", self.git_url_edit)

        self.git_token_edit = QLineEdit()
        self.git_token_edit.setPlaceholderText("ghp_xxx (GitHub PAT) o gitlab-xxx")
        self.git_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_row.addRow("Token:", self.git_token_edit)

        self.git_type_combo = QComboBox()
        self.git_type_combo.addItem("GitHub", "github")
        self.git_type_combo.addItem("GitLab", "gitlab")
        self.git_type_combo.addItem("Git generico", "git")
        form_row.addRow("Tipo:", self.git_type_combo)

        outer.addLayout(form_row)

        # Pulsanti Aggiungi / Salva token
        btns_row = QHBoxLayout()
        btns_row.setSpacing(8)

        add_btn = QPushButton("➕ Aggiungi / Aggiorna remote")
        _theme_prop(add_btn, "role", "start")
        add_btn.clicked.connect(self._on_add_git_remote)
        btns_row.addWidget(add_btn)

        test_btn = QPushButton("🔌 Test connessione")
        test_btn.clicked.connect(self._on_test_git)
        btns_row.addWidget(test_btn)

        btns_row.addStretch()
        outer.addLayout(btns_row)

        # Lista dei remote già configurati
        outer.addWidget(QLabel("<b>Remote salvati:</b>"))
        self.git_list_container = QVBoxLayout()
        self.git_list_container.setSpacing(4)
        outer.addLayout(self.git_list_container)

        return box

    def _build_audit_section(self) -> QFrame:
        """Sezione per eseguire l'audit mensile del software.

        Pulsante 'Esegui audit ora' lancia tests/test_monthly_audit.py in
        background (QThread, non blocca la GUI). Mostra i risultati in
        un area di testo + summary con critical/warning/total. Pulsante
        'Apri report HTML' apre il browser su logs/audit/latest.html.
        """
        box = QGroupBox("🔍 Audit del software")

        outer = QVBoxLayout(box)
        outer.setSpacing(8)
        outer.setContentsMargins(14, 14, 14, 14)

        # Spiegazione
        expl = QLabel(
            "Esegue l'audit mensile del software: variabili inutilizzate, "
            "codice morto, porte/endpoint esposti, superficie reverse proxy "
            "(ngrok, cloudflared, ssh -R, docker -p, ecc.), import banditi "
            "e integrità dei file critici. Il report HTML viene salvato in "
            "<code>logs/audit/</code>."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet("font-size:11px;")
        _theme_prop(expl, "role", "muted")
        outer.addWidget(expl)

        # Riga pulsanti
        btns_row = QHBoxLayout()
        btns_row.setSpacing(8)

        self.audit_run_btn = QPushButton("🔍 Esegui audit ora")
        _theme_prop(self.audit_run_btn, "role", "start")
        self.audit_run_btn.clicked.connect(self._on_run_audit)
        btns_row.addWidget(self.audit_run_btn)

        self.audit_open_btn = QPushButton("📂 Apri report HTML")
        self.audit_open_btn.clicked.connect(self._on_open_audit_report)
        btns_row.addWidget(self.audit_open_btn)

        btns_row.addStretch()
        outer.addLayout(btns_row)

        # Status label (cambia durante l'esecuzione)
        self.audit_status = QLabel("Pronto. Clicca 'Esegui audit ora' per iniziare.")
        self.audit_status.setStyleSheet("font-size:11px; font-style:italic;")
        _theme_prop(self.audit_status, "role", "muted")
        self.audit_status.setWordWrap(True)
        outer.addWidget(self.audit_status)

        # Summary cards (Critical / Warning / Total) — stile dal tema
        self.audit_summary = QLabel("")
        self.audit_summary.setStyleSheet("padding:10px; font-size:12px;")
        _theme_prop(self.audit_summary, "role", "muted")
        self.audit_summary.setWordWrap(True)
        outer.addWidget(self.audit_summary)

        # Area risultati dettagliati (ultimi 20 finding)
        self.audit_output = QPlainTextEdit()
        self.audit_output.setReadOnly(True)
        self.audit_output.setMaximumHeight(180)
        # font inline only — bg/bordri/colore dal tema (QPlainTextEdit)
        self.audit_output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; font-size:11px;"
        )
        self.audit_output.setPlaceholderText(
            "I risultati dettagliati dell'audit appariranno qui dopo l'esecuzione..."
        )
        outer.addWidget(self.audit_output)

        return box

    # ──────────────────────────────────────────────────────────────────
    # Weights-Space / Hugging Face (sviluppo estremamente beta)
    # ──────────────────────────────────────────────────────────────────
    def _build_weightspace_section(self) -> QFrame:
        """Sezione beta: scaricamento pesi GGUF da un link Hugging Face
        e prova del modello su problemi comuni da programmatore (incluse
        le ripetizioni/loop), seguendo l'idea del paper "Sparks of
        Weight-Space Programming" (MIT CSAIL, nov. 2026).
        """
        from CORE import hf_weights as hw

        box = QGroupBox("🧬 Pesi da Hugging Face — ⚠️ SVILUPPO ESTREMAMENTE BETA")

        outer = QVBoxLayout(box)
        outer.setSpacing(8)
        outer.setContentsMargins(14, 14, 14, 14)

        badge = QLabel(
            "⚠️ Funzione di sviluppo non consigliata per l'uso quotidiano. "
            "Scarica i pesi GGUF da un modello HF e li registra su Ollama "
            "(un solo modello in RAM: attenzione alle dimensioni)."
        )
        badge.setWordWrap(True)
        badge.setStyleSheet("font-size:11px; color:#d97706; font-style:italic;")
        outer.addWidget(badge)

        # Riga link + analyze
        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        self.ws_link_input = QLineEdit()
        self.ws_link_input.setPlaceholderText(
            "https://huggingface.co/OWNER/REPO  (o …/blob/main/model.gguf, o OWNER/REPO)"
        )
        self.ws_link_input.setToolTip(
            "Link diretto alla pagina del modello Hugging Face. Per macchine "
            "4GB si sceglie automaticamente la quantizzazione Q4 più piccola."
        )
        link_row.addWidget(self.ws_link_input, stretch=1)
        self.ws_analyze_btn = QPushButton("🔍 Analizza link")
        _theme_prop(self.ws_analyze_btn, "role", "start")
        self.ws_analyze_btn.clicked.connect(self._on_ws_analyze)
        link_row.addWidget(self.ws_analyze_btn)
        outer.addLayout(link_row)

        # Riga scelta variante + download
        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)
        self.ws_variant_combo = QComboBox()
        self.ws_variant_combo.setToolTip("File di pesi GGUF disponibili nella repo")
        self.ws_variant_combo.setMinimumWidth(260)
        pick_row.addWidget(self.ws_variant_combo, stretch=1)
        self.ws_download_btn = QPushButton("⬇ Scarica e registra su Ollama")
        _theme_prop(self.ws_download_btn, "role", "start")
        self.ws_download_btn.setEnabled(False)
        self.ws_download_btn.clicked.connect(self._on_ws_download)
        pick_row.addWidget(self.ws_download_btn)
        self.ws_cancel_btn = QPushButton("✕ Annulla")
        _theme_prop(self.ws_cancel_btn, "role", "danger")
        self.ws_cancel_btn.setEnabled(False)
        self.ws_cancel_btn.clicked.connect(self._on_ws_cancel)
        pick_row.addWidget(self.ws_cancel_btn)
        outer.addLayout(pick_row)

        # Progresso download
        self.ws_progress = QProgressBar()
        self.ws_progress.setRange(0, 100)
        self.ws_progress.setValue(0)
        self.ws_progress.setVisible(False)
        outer.addWidget(self.ws_progress)

        self.ws_status = QLabel("Pronto. Incolla il link di un modello HF e clicca 'Analizza link'.")
        self.ws_status.setWordWrap(True)
        self.ws_status.setStyleSheet("font-size:11px; font-style:italic;")
        _theme_prop(self.ws_status, "role", "muted")
        outer.addWidget(self.ws_status)

        # Models già scaricati + prova harness
        prov_row = QHBoxLayout()
        prov_row.setSpacing(8)
        prov_lbl = QLabel("Modelli pesi scaricati:")
        prov_lbl.setStyleSheet("font-size:11px;")
        _theme_prop(prov_lbl, "role", "muted")
        prov_row.addWidget(prov_lbl)
        self.ws_model_combo = QComboBox()
        prov_row.addWidget(self.ws_model_combo, stretch=1)
        self.ws_prove_btn = QPushButton("🧪 Prova il modello (problemi da programmatore)")
        _theme_prop(self.ws_prove_btn, "role", "start")
        self.ws_prove_btn.setToolTip(
            "Esegue l'harness di weight-space programming: somma con loop, "
            "FizzBuzz, conteggio, inversione, fix di loop infiniti e "
            "off-by-one + metrica di ripetizione/loop (Esperimento 8 del paper)."
        )
        self.ws_prove_btn.clicked.connect(self._on_ws_prove)
        prov_row.addWidget(self.ws_prove_btn)
        outer.addLayout(prov_row)
        self._ws_reload_model_combo()

        # Output
        self.ws_output = QPlainTextEdit()
        self.ws_output.setReadOnly(True)
        self.ws_output.setMaximumHeight(190)
        self.ws_output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; font-size:11px;"
        )
        self.ws_output.setPlaceholderText(
            "Qui appaiono: analisi del link, header dei pesi (GGUF), avanzamento "
            "download e report dell'harness di weight-space programming…"
        )
        outer.addWidget(self.ws_output)

        return box

    # ──────────────────────────────────────────────────────────────────
    # Weights-Space handlers
    # ──────────────────────────────────────────────────────────────────
    def _ws_reload_model_combo(self):
        from CORE import hf_weights as hw
        self.ws_model_combo.clear()
        models = hw.load_registry()
        if not models:
            self.ws_model_combo.addItem("— nessun modello scaricato —")
            self.ws_prove_btn.setEnabled(False)
            return
        self.ws_prove_btn.setEnabled(True)
        for m in models:
            label = f"{m.get('name')} · {hw.human_size(m.get('size') or 0)} · {m.get('repo_id', '')}"
            self.ws_model_combo.addItem(label)
        self.ws_model_combo.setCurrentIndex(0)

    def _on_ws_analyze(self):
        """Analizza il link: elenca i GGUF della repo e popola il combo."""
        from CORE import hf_weights as hw
        link = self.ws_link_input.text().strip()
        if not link:
            QMessageBox.information(self, "Weights beta", "Incolla prima il link del modello HF.")
            return
        try:
            info = hw.parse_hf_link(link)
            files = hw.list_repo_files(info["repo_id"], info["revision"] or "main")
        except ValueError as e:
            QMessageBox.warning(self, "Weights beta", f"Link non valido\n\n{e}")
            return
        except Exception as e:
            QMessageBox.warning(self, "Weights beta", f"Errore di rete su Hugging Face:\n{e}")
            return
        self.ws_output.setPlainText(
            f"REPO: {info['repo_id']} (rev: {info['revision']})\n"
            f"file: {len(files)}\n" +
            "\n".join(f"  - {f['path']} ({hw.human_size(f['size'])})"
                      for f in files[:25])
        )
        self.ws_variant_combo.clear()
        for f in files:
            if str(f["path"]).lower().endswith(".gguf"):
                self.ws_variant_combo.addItem(
                    f"{f['path']} ({hw.human_size(f['size'])})",
                    userData=f["path"],
                )
        if self.ws_variant_combo.count() == 0:
            QMessageBox.warning(
                self, "Weights beta",
                "Questa repo non contiene file GGUF (solo pesi quantizzati "
                "possono girare su Ollama). Prova un altro modello."
            )
            self.ws_download_btn.setEnabled(False)
            return
        # seleziona di default la variante più friendly per 4GB
        preferred = hw.pick_gguf(files)
        if preferred:
            idx = self.ws_variant_combo.findText(
                f"{preferred['path']} ({hw.human_size(preferred['size'])})")
            if idx >= 0:
                self.ws_variant_combo.setCurrentIndex(idx)
        self.ws_download_btn.setEnabled(True)
        chosen = self.ws_variant_combo.currentData()
        self.ws_status.setText(
            f"Pesi trovati: {chosen} — clicca '⬇ Scarica e registra su Ollama'."
        )

    def _on_ws_download(self):
        """Scarica il file di pesi selezionato e registra il modello."""
        from CORE import hf_weights as hw
        link = self.ws_link_input.text().strip()
        filename = self.ws_variant_combo.currentData() or ""
        if not link or not filename:
            QMessageBox.information(self, "Weights beta", "Prima analizza il link.")
            return
        try:
            info = hw.parse_hf_link(link)
        except ValueError as e:
            QMessageBox.warning(self, "Weights beta", f"Link non valido\n\n{e}")
            return
        if not filename:
            QMessageBox.warning(self, "Weights beta", "Nessun file GGUF selezionato.")
            return
        info["filename"] = filename  # usa la variante scelta dall'utente
        self.ws_download_btn.setEnabled(False)
        self.ws_analyze_btn.setEnabled(False)
        self.ws_cancel_btn.setEnabled(True)
        self.ws_progress.setVisible(True)
        self.ws_progress.setValue(0)
        self.ws_status.setText("⬇ Download dei pesi in corso…")
        self._ws_download_worker = WeightsDownloadWorker(
            link, force_filename=filename, parent=self)
        try:
            self._ws_download_worker.finished_ok.connect(self._on_ws_download_done)
            self._ws_download_worker.failed.connect(self._on_ws_failed)
            self._ws_download_worker.progress.connect(
                lambda msg: self.ws_output.appendPlainText(msg))
            self._ws_download_worker.percent.connect(self.ws_progress.setValue)
            self._ws_download_worker.found.connect(
                lambda msg: self.ws_output.appendPlainText(msg))
            self._ws_download_worker.start()
        except Exception as e:
            self._reset_ws_buttons()
            QMessageBox.warning(self, "Weights beta", f"Avvio download fallito:\n{e}")

    def _on_ws_download_done(self, entry: dict):
        self._reset_ws_buttons()
        self.ws_progress.setValue(100)
        meta = entry.get("meta") or {}
        meta_txt = "\n".join(f"  {k} = {v}" for k, v in list(meta.items())[:8]) or "  (n/d)"
        self.ws_output.appendPlainText(
            "\n✓ PESI REGISTRATI SU OLLAMA\n"
            f"  nome:    {entry['name']}\n"
            f"  pesi:    {entry['gguf']}\n"
            f"  header : \n{meta_txt}\n\n"
            "Ora puoi: 🧪 'Prova il modello' (harness weight-space) oppure "
            "usarlo via orchestrator/benchmark."
        )
        self.ws_status.setText(f"✓ Modello pronto: {entry['name']}")
        self._ws_reload_model_combo()

    def _on_ws_failed(self, msg: str):
        self._reset_ws_buttons()
        self.ws_progress.setVisible(False)
        self.ws_status.setText("⚠️ Operazione non completata.")
        self.ws_output.appendPlainText(f"\n✗ ERRORE: {msg}")

    def _on_ws_cancel(self):
        if getattr(self, "_ws_download_worker", None):
            self._ws_download_worker.cancel()
        if getattr(self, "_ws_prove_worker", None):
            self._ws_prove_worker.cancel()
        self.ws_status.setText("Annullamento richiesto…")

    def _reset_ws_buttons(self):
        self.ws_download_btn.setEnabled(self.ws_variant_combo.count() > 0)
        self.ws_analyze_btn.setEnabled(True)
        self.ws_cancel_btn.setEnabled(False)
        self.ws_progress.setVisible(False)

    def _on_ws_prove(self):
        """Lancia l'harness weight-space sul modello selezionato."""
        model = self.ws_model_combo.currentText()
        if not model or model.startswith("—"):
            QMessageBox.information(
                self, "Weights beta", "Nessun modello pesi in elenco: scaricalo prima.")
            return
        # il combo mostra "name · size · repo": estrai la prima parte
        model_name = model.split(" · ")[0]
        self.ws_prove_btn.setEnabled(False)
        self.ws_cancel_btn.setEnabled(True)
        self.ws_status.setText(f"🧪 Harness in esecuzione su '{model_name}' (attendere…)")
        self._ws_prove_worker = WeightspaceProveWorker(model_name, parent=self)
        self._ws_prove_worker.finished_ok.connect(self._on_ws_prove_done)
        self._ws_prove_worker.failed.connect(self._on_ws_failed)
        self._ws_prove_worker.progress.connect(
            lambda msg: self.ws_output.appendPlainText("  " + msg))
        self._ws_prove_worker.start()

    def _on_ws_prove_done(self, report: dict):
        self._reset_ws_buttons()
        from CORE import weight_space_harness as h
        self.ws_output.appendPlainText("\n" + "=" * 60 + "\n" + h.format_report(report))
        self.ws_status.setText(
            f"Punteggio: {report['passed']}/{report['total']}"
            + (" — ⚠️ Loop rilevati" if report.get("loops_detected") else "")
        )

    # ──────────────────────────────────────────────────────────────────
    # Audit handlers
    # ──────────────────────────────────────────────────────────────────
    def _on_run_audit(self):
        """Lancia l'audit in background (QThread, non blocca la GUI)."""
        if self._audit_worker and self._audit_worker.isRunning():
            QMessageBox.information(self, "Audit in corso",
                                    "Un audit è già in esecuzione. Attendi il completamento.")
            return
        # Determina la root del progetto (2 livelli sopra GUI/)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.isfile(os.path.join(base, "tests", "test_monthly_audit.py")):
            QMessageBox.warning(self, "File mancante",
                                "tests/test_monthly_audit.py non trovato. "
                                "Verifica che il file esista nel repo.")
            return
        # Disabilita il pulsante e resetta l'output
        self.audit_run_btn.setEnabled(False)
        self.audit_run_btn.setText("⏳ Audit in corso...")
        self.audit_status.setText("Avvio audit in background...")
        self.audit_status.setStyleSheet("font-size:11px; font-weight:bold;")
        _theme_banner(self.audit_status, "info")
        self.audit_output.clear()

        # Crea e connetta il worker
        self._audit_worker = AuditWorker(base, parent=self)
        self._audit_worker.progress.connect(self._on_audit_progress)
        self._audit_worker.finished_ok.connect(self._on_audit_finished)
        self._audit_worker.failed.connect(self._on_audit_failed)
        self._audit_worker.start()

    def _on_audit_progress(self, msg: str):
        """Aggiorna lo status durante l'esecuzione."""
        self.audit_status.setText(msg)

    def _on_audit_finished(self, report: dict):
        """Mostra i risultati quando l'audit finisce con successo."""
        self.audit_run_btn.setEnabled(True)
        self.audit_run_btn.setText("🔍 Esegui audit ora")

        s = report.get("summary", {})
        total = s.get("total", 0)
        critical = s.get("critical", 0)
        warning = s.get("warning", 0)
        info = s.get("info", 0)
        passed = s.get("passed", False)

        # Status
        if passed:
            self.audit_status.setText("✓ AUDIT PASS — 0 problemi critical")
            self.audit_status.setStyleSheet("font-size:12px; font-weight:bold;")
            _theme_banner(self.audit_status, "ok")
        else:
            self.audit_status.setText(f"✗ AUDIT FAIL — {critical} problemi critical")
            self.audit_status.setStyleSheet("font-size:12px; font-weight:bold;")
            _theme_banner(self.audit_status, "error")

        # Summary con badge colorati
        crit_color = "#dc2626" if critical else "#16a34a"
        self.audit_summary.setText(
            f"<table cellpadding='4' style='font-size:13px;'>"
            f"<tr><td><b>Totale finding:</b></td><td>{total}</td></tr>"
            f"<tr><td><b style='color:{crit_color};'>Critical:</b></td>"
            f"<td style='color:{crit_color}; font-weight:bold;'>{critical}</td></tr>"
            f"<tr><td><b style='color:#f59e0b;'>Warning:</b></td>"
            f"<td style='color:#f59e0b;'>{warning}</td></tr>"
            f"<tr><td><b style='color:#3b82f6;'>Info:</b></td>"
            f"<td style='color:#3b82f6;'>{info}</td></tr>"
            f"</table>"
        )

        # Output dettagliato: primi 20 finding
        findings = report.get("findings", [])
        lines = []
        for f in findings[:20]:
            sev = f.get("severity", "info").upper()
            loc = f"{f.get('file', '?')}:{f.get('line', 0)}"
            msg = f.get("message", "")[:120]
            lines.append(f"[{sev:8s}] {loc:50s} {msg}")
        if len(findings) > 20:
            lines.append(f"... e altri {len(findings) - 20} finding (vedi report HTML)")
        self.audit_output.setPlainText("\n".join(lines) if lines else "(nessun finding)")

        # Salva il report HTML su disco (così 'Apri report' funziona)
        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            audit_dir = os.path.join(base, "logs", "audit")
            os.makedirs(audit_dir, exist_ok=True)
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d")
            html_path = os.path.join(audit_dir, f"{ts}_audit.html")
            # Genera anche l'HTML: richiama il modulo con --html
            import sys as _sys
            subprocess.run(
                [_sys.executable, "tests/test_monthly_audit.py", "--html", html_path, "--no-text"],
                cwd=base, capture_output=True, timeout=30
            )
            # Aggiorna symlink latest.html
            latest = os.path.join(audit_dir, "latest.html")
            try:
                if os.path.islink(latest) or os.path.exists(latest):
                    os.remove(latest)
                os.symlink(os.path.basename(html_path), latest)
            except OSError:
                pass  # su alcuni FS i symlink non funzionano
            self.audit_status.setText(
                self.audit_status.text() + f"  |  Report: {html_path}"
            )
        except Exception as e:
            # Non bloccare se la generazione HTML fallisce
            pass

    def _on_audit_failed(self, msg: str):
        """Mostra l'errore se l'audit fallisce."""
        self.audit_run_btn.setEnabled(True)
        self.audit_run_btn.setText("🔍 Esegui audit ora")
        self.audit_status.setText("✗ Audit fallito")
        self.audit_status.setStyleSheet("font-size:12px; font-weight:bold;")
        _theme_banner(self.audit_status, "error")
        self.audit_output.setPlainText(msg)

    def _on_open_audit_report(self):
        """Apre il browser sul report HTML più recente."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        latest = os.path.join(base, "logs", "audit", "latest.html")
        if not os.path.exists(latest):
            QMessageBox.information(self, "Nessun report",
                                    "Nessun report HTML trovato. Esegui prima un audit.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(latest))

    # ──────────────────────────────────────────────────────────────────
    # Stili
    # ──────────────────────────────────────────────────────────────────
    # Stili inline (group/combo/input/bottoni) RIMOSSI: ora arrivano dal
    # tema app-level (GUI/theme/*.qss): QGroupBox, QLineEdit, QComboBox,
    # QPushButton[role=…]. Colori hardcoded light-only erano rotti nel
    # tema scuro e non sincronizzati con il toggle live.

    # ──────────────────────────────────────────────────────────────────
    # Carica / ricarica dal settings store
    # ──────────────────────────────────────────────────────────────────
    def _reload_from_store(self):
        s = settings_store.load_settings()
        # Tema
        theme = s.get("theme", "dark")
        self.theme_section.theme_combo.setCurrentIndex(
            self.theme_section.theme_combo.findData(theme)
        )
        # Lingua
        lang = s.get("language", "it")
        self.language_section.lang_combo.setCurrentIndex(
            0 if lang == "it" else 1
        )
        # Debug GUI
        self.debug_section.gui_debug_cb.setChecked(
            settings_store.get_gui_debug()
        )
        # H1: Strategia hardware
        hw = s.get("hardware_strategy", "cpu_only")
        # Trova l'index della strategia nella combo
        for i in range(self.hardware_section.hw_combo.count()):
            if self.hardware_section.hw_combo.itemData(i) == hw:
                # Solo se l'item è abilitato (GPU può essere disabilitata)
                item = self.hardware_section.hw_combo.model().item(i)
                if item.isEnabled():
                    self.hardware_section.hw_combo.setCurrentIndex(i)
                break
        # H1: auto-detect checkbox
        self.hardware_section.hw_auto_detect.setChecked(
            s.get("detect_gpu_at_startup", True)
        )
        self._update_hw_hint()
        # Git remotes
        self._refresh_git_list()

    def _refresh_git_list(self):
        """Ricostruisce la lista visiva dei remote salvati."""
        # Pulisci
        while self.git_list_container.count():
            item = self.git_list_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        remotes = settings_store.get_git_remotes()
        if not remotes:
            empty = QLabel("Nessun remote configurato. Aggiungine uno sopra. ↑")
            empty.setStyleSheet("font-style:italic; padding:8px;")
            _theme_prop(empty, "role", "muted")
            self.git_list_container.addWidget(empty)
            return

        for r in remotes:
            row = QFrame()
            # cartolina "card" dal tema (QFrame#card nei .qss)
            row.setObjectName("card")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 4, 8, 4)
            rl.setSpacing(8)

            icon = {"github": "🐙", "gitlab": "🦊", "git": "📂"}.get(r.get("type", "git"), "📂")
            name = r.get("name", "?")
            url = r.get("url", "")
            has_token = "✓ token" if r.get("token") else "✗ token"
            lbl = QLabel(f"{icon} <b>{name}</b> — {url} <i>({has_token})</i>")
            lbl.setStyleSheet("font-size:11px;")
            _theme_prop(lbl, "role", "muted")
            rl.addWidget(lbl, stretch=1)

            del_btn = QPushButton("🗑")
            del_btn.setToolTip("Rimuovi questo remote")
            _theme_prop(del_btn, "role", "danger")
            del_btn.setFixedWidth(32)
            del_btn.clicked.connect(lambda _, n=name: self._on_remove_git(n))
            rl.addWidget(del_btn)

            self.git_list_container.addWidget(row)

    # ──────────────────────────────────────────────────────────────────
    # Handler
    # ──────────────────────────────────────────────────────────────────
    def _on_theme_changed(self, _idx: int):
        theme = self.theme_section.theme_combo.currentData()
        settings_store.set_theme(theme)
        # Emette segnale per applicazione live
        self.theme_changed.emit(theme)

    def _on_lang_changed(self, _idx: int):
        lang = self.language_section.lang_combo.currentData()
        settings_store.set_language(lang)
        # Work in progress — non applichiamo realmente la lingua ora

    def _on_gui_debug_changed(self, state):
        enabled = state == Qt.CheckState.Checked.value
        settings_store.set_gui_debug(enabled)
        self.gui_debug_changed.emit(enabled)

    def _on_add_git_remote(self):
        name = self.git_name_edit.text().strip()
        url = self.git_url_edit.text().strip()
        token = self.git_token_edit.text().strip()
        rtype = self.git_type_combo.currentData()

        if not name or not url:
            QMessageBox.warning(
                self, "Dati mancanti",
                "Inserisci almeno il nome del remote e l'URL del repository."
            )
            return

        # Valida URL (http/https only)
        if not (url.startswith("https://") or url.startswith("http://")):
            QMessageBox.warning(
                self, "URL non valido",
                "L'URL deve iniziare con http:// o https:// (no SSH)."
            )
            return

        ok = settings_store.add_git_remote(name, url, token, rtype)
        if ok:
            # Pulisci i campi
            self.git_name_edit.clear()
            self.git_url_edit.clear()
            self.git_token_edit.clear()
            self._refresh_git_list()
            QMessageBox.information(
                self, "Remote salvato",
                f"Remote '{name}' ({rtype}) salvato in CONFIG/settings.json.\n\n"
                f"Il pulsante 💾 ora farà il push su questo remote."
            )
        else:
            QMessageBox.critical(
                self, "Errore", "Impossibile salvare il remote (vedi console)."
            )

    def _on_remove_git(self, name: str):
        reply = QMessageBox.question(
            self, "Conferma",
            f"Rimuovere il remote '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            settings_store.remove_git_remote(name)
            self._refresh_git_list()

    def _on_test_git(self):
        """Testa la connessione al remote (git ls-remote) usando il token."""
        url = self.git_url_edit.text().strip()
        token = self.git_token_edit.text().strip()
        if not url:
            QMessageBox.information(self, "Test", "Inserisci prima un URL.")
            return
        # Inietta il token nell'URL (se https e token presente)
        test_url = url
        if token and url.startswith("https://"):
            # https://<token>@github.com/...
            test_url = url.replace("https://", f"https://oauth2:{token}@")
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", test_url],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                QMessageBox.information(
                    self, "Test OK ✓",
                    f"Connessione riuscita a:\n{url}\n\n"
                    f"Branch trovati:\n{result.stdout[:500]}"
                )
            else:
                QMessageBox.warning(
                    self, "Test fallito ✗",
                    f"Impossibile contattare il remote:\n{url}\n\n"
                    f"Errore:\n{result.stderr[:500]}"
                )
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "Timeout", "git ls-remote timeout (15s).")
        except FileNotFoundError:
            QMessageBox.warning(self, "Git mancante", "Eseguibile 'git' non trovato.")
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Errore inatteso: {e}")

    def _back_to_main(self):
        """Torna alla plancia di controllo principale."""
        # Risale il parent fino a trovare CenterArea con back_to_main()
        parent = self.parent()
        while parent and not hasattr(parent, "back_to_main"):
            parent = parent.parent()
        if parent and hasattr(parent, "back_to_main"):
            parent.back_to_main()
