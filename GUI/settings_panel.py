"""Pannello Impostazioni interattivo per BYTE-SWARMY.

Sostituisce la vecchia schermata di testo statica "Configurazione
BYTE-SWARMY: ..." con un pannello vero che permette di:

- scegliere il tema (chiaro / scuro) — applicato ai credits e all'app
- scegliere la lingua (italiano / inglese) — Work in progress
- configurare i remote Git (GitHub, GitLab, Git) con token e URL,
  usati dal pulsante floppy 💾 per il push automatico su tutti i remote
"""
import os
import subprocess
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QLineEdit, QMessageBox, QInputDialog, QScrollArea,
    QSizePolicy, QGroupBox, QFormLayout, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from GUI import settings_store


class SettingsPanel(QWidget):
    """Pannello impostazioni con tema, lingua e Git remotes."""

    # Segnale emesso quando il tema cambia (per applicazione live)
    theme_changed = pyqtSignal(str)  # "dark" | "light"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settings_panel")
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
        back = QPushButton("← Indietro alla Plancia")
        back.setObjectName("back_btn")
        back.setStyleSheet(
            "QPushButton#back_btn { background:#e8e8ec; color:#1a1a1a; "
            "border:none; padding:8px 16px; border-radius:6px; font-size:12px; }"
            "QPushButton#back_btn:hover { background:#d0d0d0; }"
        )
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>⚙️ Impostazioni</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        # Scroll area per il contenuto (in caso di molti remote)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Sezione Tema ──────────────────────────────────────────────
        lay.addWidget(self._build_theme_section())
        # ── Sezione Lingua ─────────────────────────────────────────────
        lay.addWidget(self._build_language_section())
        # ── Sezione Strategia Hardware (H1) ────────────────────────────
        lay.addWidget(self._build_hardware_section())
        # ── Sezione Git remotes ───────────────────────────────────────
        lay.addWidget(self._build_git_section())

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _build_theme_section(self) -> QFrame:
        """Sezione per scegliere il tema (chiaro/scuro)."""
        box = QGroupBox("🎨 Tema interfaccia")
        box.setStyleSheet(self._group_style())
        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("🌙 Scuro", "dark")
        self.theme_combo.addItem("☀️ Chiaro", "light")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.theme_combo.setStyleSheet(self._combo_style())
        form.addRow("Tema:", self.theme_combo)

        hint = QLabel(
            "Il tema scuro è consigliato per i credits e per l'uso notturno.\n"
            "Il tema chiaro è più leggibile in ambienti luminosi."
        )
        hint.setStyleSheet("color:#666; font-size:10px; font-style:italic;")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return box

    def _build_language_section(self) -> QFrame:
        """Sezione per scegliere la lingua (it/en) — Work in progress."""
        box = QGroupBox("🌐 Lingua")
        box.setStyleSheet(self._group_style())
        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("🇮🇹 Italiano", "it")
        self.lang_combo.addItem("🇬🇧 English", "en")
        self.lang_combo.setToolTip("Work in progress")
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        self.lang_combo.setStyleSheet(self._combo_style())
        form.addRow("Lingua:", self.lang_combo)

        wip = QLabel("⚠️ Work in progress — la lingua inglese sarà disponibile prossimamente.")
        wip.setStyleSheet("color:#f59e0b; font-size:10px; font-style:italic;")
        wip.setWordWrap(True)
        form.addRow("", wip)
        return box

    def _build_hardware_section(self) -> QFrame:
        """H1: Sezione Strategia Hardware — bilanciamento CPU/GPU.

        4 modalità:
          - gpu+cpu: LLM su GPU, Decision+Timestral su CPU (potenza massima)
          - gpu_only: tutto su GPU
          - cpu_only: tutto su CPU
          - cpu_then_gpu: CPU default, fallback GPU se overload (archi vecchie)
        """
        box = QGroupBox("⚡ Strategia Hardware")
        box.setStyleSheet(self._group_style())
        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        # Rileva GPU (status)
        from GUI.settings_store import is_gpu_available, get_effective_strategy_description
        gpu_present = is_gpu_available()
        gpu_status_lbl = QLabel(
            f"{'✅ GPU rilevata' if gpu_present else '❌ GPU non rilevata (solo CPU disponibile)'}"
        )
        gpu_status_lbl.setStyleSheet(
            f"color:{'#16a34a' if gpu_present else '#dc2626'}; "
            f"font-weight:bold; font-size:11px;"
        )
        form.addRow("Stato GPU:", gpu_status_lbl)

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
        self.hw_combo.currentIndexChanged.connect(self._on_hw_changed)
        self.hw_combo.setStyleSheet(self._combo_style())
        form.addRow("Strategia:", self.hw_combo)

        # Hint dinamico (descrizione della strategia selezionata)
        self.hw_hint = QLabel()
        self.hw_hint.setWordWrap(True)
        self.hw_hint.setStyleSheet("color:#666; font-size:10px; font-style:italic;")
        self._update_hw_hint()
        form.addRow("", self.hw_hint)

        # Checkbox auto-detect
        self.hw_auto_detect = QCheckBox(
            "Rileva GPU automaticamente all'avvio (sovrascrive se non scelta esplicita)"
        )
        self.hw_auto_detect.setStyleSheet("font-size:11px;")
        form.addRow("", self.hw_auto_detect)

        return box

    def _update_hw_hint(self):
        """Aggiorna il testo descrittivo sotto la combo hardware."""
        from GUI.settings_store import get_effective_strategy_description
        if hasattr(self, "hw_combo"):
            strategy = self.hw_combo.currentData()
            self.hw_hint.setText(get_effective_strategy_description(strategy))

    def _on_hw_changed(self, _idx: int):
        """H1: quando cambia strategia hardware, salva + aggiorna hint."""
        from GUI import settings_store as ss
        strategy = self.hw_combo.currentData()
        ss.set_hardware_strategy(strategy, user_set=True)
        # Salva anche lo stato dell'auto-detect checkbox
        if hasattr(self, "hw_auto_detect"):
            s = ss.load_settings()
            s["detect_gpu_at_startup"] = self.hw_auto_detect.isChecked()
            s["user_set_hardware_strategy"] = True
            ss.save_settings(s)
        self._update_hw_hint()

    def _build_git_section(self) -> QFrame:
        """Sezione per configurare i remote Git (GitHub/GitLab/Git) + token."""
        box = QGroupBox("💾 Remote Git — push automatico")
        box.setStyleSheet(self._group_style())
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
        expl.setStyleSheet("color:#555; font-size:11px;")
        outer.addWidget(expl)

        # Form per aggiungere un remote
        form_row = QFormLayout()
        form_row.setSpacing(6)

        self.git_name_edit = QLineEdit()
        self.git_name_edit.setPlaceholderText("origin")
        self.git_name_edit.setStyleSheet(self._input_style())
        form_row.addRow("Nome remote:", self.git_name_edit)

        self.git_url_edit = QLineEdit()
        self.git_url_edit.setPlaceholderText("https://github.com/wildlux/byte-swarmy.git")
        self.git_url_edit.setStyleSheet(self._input_style())
        form_row.addRow("URL repo:", self.git_url_edit)

        self.git_token_edit = QLineEdit()
        self.git_token_edit.setPlaceholderText("ghp_xxx (GitHub PAT) o gitlab-xxx")
        self.git_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.git_token_edit.setStyleSheet(self._input_style())
        form_row.addRow("Token:", self.git_token_edit)

        self.git_type_combo = QComboBox()
        self.git_type_combo.addItem("GitHub", "github")
        self.git_type_combo.addItem("GitLab", "gitlab")
        self.git_type_combo.addItem("Git generico", "git")
        self.git_type_combo.setStyleSheet(self._combo_style())
        form_row.addRow("Tipo:", self.git_type_combo)

        outer.addLayout(form_row)

        # Pulsanti Aggiungi / Salva token
        btns_row = QHBoxLayout()
        btns_row.setSpacing(8)

        add_btn = QPushButton("➕ Aggiungi / Aggiorna remote")
        add_btn.setStyleSheet(self._primary_btn_style())
        add_btn.clicked.connect(self._on_add_git_remote)
        btns_row.addWidget(add_btn)

        test_btn = QPushButton("🔌 Test connessione")
        test_btn.setStyleSheet(self._secondary_btn_style())
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

    # ──────────────────────────────────────────────────────────────────
    # Stili
    # ──────────────────────────────────────────────────────────────────
    def _group_style(self) -> str:
        return (
            "QGroupBox {"
            "  background:#ffffff; border:1px solid #e0e0e0; border-radius:8px;"
            "  margin-top:14px; padding-top:8px;"
            "  font-weight:bold; color:#1a1a1a;"
            "}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin; left:14px; padding:0 6px;"
            "  background:#ffffff;"
            "}"
        )

    def _combo_style(self) -> str:
        return (
            "QComboBox { background:#ffffff; color:#1a1a1a; "
            "border:1px solid #d0d0d0; padding:6px 10px; border-radius:6px; "
            "font-size:12px; min-width:160px; }"
            "QComboBox:hover { border-color:#16a34a; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#1a1a1a; "
            "selection-background-color:#f0f9ff; }"
        )

    def _input_style(self) -> str:
        return (
            "QLineEdit { background:#ffffff; color:#1a1a1a; "
            "border:1px solid #d0d0d0; padding:6px 10px; border-radius:6px; "
            "font-size:12px; }"
            "QLineEdit:focus { border-color:#16a34a; }"
        )

    def _primary_btn_style(self) -> str:
        return (
            "QPushButton { background:#16a34a; color:#ffffff; border:none; "
            "padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#15803d; }"
        )

    def _secondary_btn_style(self) -> str:
        return (
            "QPushButton { background:#e8e8ec; color:#1a1a1a; border:none; "
            "padding:8px 14px; border-radius:6px; font-size:11px; }"
            "QPushButton:hover { background:#d0d0d0; }"
        )

    def _danger_btn_style(self) -> str:
        return (
            "QPushButton { background:#dc2626; color:#ffffff; border:none; "
            "padding:4px 10px; border-radius:4px; font-size:10px; }"
            "QPushButton:hover { background:#b91c1c; }"
        )

    # ──────────────────────────────────────────────────────────────────
    # Carica / ricarica dal settings store
    # ──────────────────────────────────────────────────────────────────
    def _reload_from_store(self):
        s = settings_store.load_settings()
        # Tema
        theme = s.get("theme", "dark")
        idx = 0 if theme == "dark" else 1
        self.theme_combo.setCurrentIndex(idx)
        # Lingua
        lang = s.get("language", "it")
        idx = 0 if lang == "it" else 1
        self.lang_combo.setCurrentIndex(idx)
        # H1: Strategia hardware
        hw = s.get("hardware_strategy", "cpu_only")
        # Trova l'index della strategia nella combo
        for i in range(self.hw_combo.count()):
            if self.hw_combo.itemData(i) == hw:
                # Solo se l'item è abilitato (GPU può essere disabilitata)
                item = self.hw_combo.model().item(i)
                if item.isEnabled():
                    self.hw_combo.setCurrentIndex(i)
                break
        # H1: auto-detect checkbox
        self.hw_auto_detect.setChecked(s.get("detect_gpu_at_startup", True))
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
            empty.setStyleSheet("color:#888; font-style:italic; padding:8px;")
            self.git_list_container.addWidget(empty)
            return

        for r in remotes:
            row = QFrame()
            row.setStyleSheet(
                "QFrame { background:#f8f9fa; border:1px solid #e0e0e0; "
                "border-radius:6px; padding:6px 10px; }"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 4, 8, 4)
            rl.setSpacing(8)

            icon = {"github": "🐙", "gitlab": "🦊", "git": "📂"}.get(r.get("type", "git"), "📂")
            name = r.get("name", "?")
            url = r.get("url", "")
            has_token = "✓ token" if r.get("token") else "✗ token"
            lbl = QLabel(f"{icon} <b>{name}</b> — {url} <i>({has_token})</i>")
            lbl.setStyleSheet("font-size:11px; color:#333;")
            rl.addWidget(lbl, stretch=1)

            del_btn = QPushButton("🗑")
            del_btn.setToolTip("Rimuovi questo remote")
            del_btn.setStyleSheet(self._danger_btn_style())
            del_btn.setFixedWidth(32)
            del_btn.clicked.connect(lambda _, n=name: self._on_remove_git(n))
            rl.addWidget(del_btn)

            self.git_list_container.addWidget(row)

    # ──────────────────────────────────────────────────────────────────
    # Handler
    # ──────────────────────────────────────────────────────────────────
    def _on_theme_changed(self, _idx: int):
        theme = self.theme_combo.currentData()
        settings_store.set_theme(theme)
        # Emette segnale per applicazione live
        self.theme_changed.emit(theme)

    def _on_lang_changed(self, _idx: int):
        lang = self.lang_combo.currentData()
        settings_store.set_language(lang)
        # Work in progress — non applichiamo realmente la lingua ora

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
