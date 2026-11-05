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
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QThread, QObject, pyqtSignal as Signal
from PyQt6.QtGui import QDesktopServices

from GUI import settings_store
from GUI.theme.theme import set_prop as _theme_prop
from GUI.theme.theme import set_banner as _theme_banner

# ═══════════════════════════════════════════════════════════════
# Worker thread per l'audit (non blocca la GUI)
# ═══════════════════════════════════════════════════════════════

class AuditWorker(QThread):
    """Esegue l'audit mensile in background.

    Lancia tests/test_monthly_audit.py --json in un subprocess, parsifica
    il JSON risultante e emette segnali per aggiornare la GUI in tempo
    reale. Non blocca mai il thread principale della GUI.
    """
    progress = Signal(str)        # messaggio di stato (es. "Avvio audit...")
    finished_ok = Signal(dict)    # report dict (summary + findings)
    failed = Signal(str)          # messaggio di errore

    def __init__(self, root_dir: str, parent=None):
        super().__init__(parent)
        self.root_dir = root_dir
        self._proc: Optional[subprocess.Popen] = None

    def run(self):
        try:
            self.progress.emit("🔍 Avvio audit mensile in background...")
            import sys as _sys
            cmd = [_sys.executable, "tests/test_monthly_audit.py", "--json"]
            self._proc = subprocess.Popen(
                cmd,
                cwd=self.root_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = self._proc.communicate(timeout=120)
            if self._proc.returncode != 0 and not stdout.strip():
                self.failed.emit(f"Audit fallito (exit {self._proc.returncode}):\n{stderr[:500]}")
                return
            # Parse JSON
            import json
            try:
                report = json.loads(stdout)
            except json.JSONDecodeError as e:
                self.failed.emit(f"Risposta non valida dal test:\n{stdout[:300]}\n\nErrore: {e}")
                return
            self.progress.emit("✓ Audit completato")
            self.finished_ok.emit(report)
        except subprocess.TimeoutExpired:
            self.failed.emit("Audit timeout (>120s). Possibile loop infinito.")
        except FileNotFoundError:
            self.failed.emit("Python non trovato. Verifica l'installazione.")
        except Exception as e:
            self.failed.emit(f"Errore inatteso: {e}")

    def cancel(self):
        """Cancella l'audit (se in corso)."""
        if self._proc and self._proc.poll() is None:
            self._proc.kill()
        self.requestInterruption()

class SettingsPanel(QWidget):
    """Pannello impostazioni con tema, lingua e Git remotes."""

    # Segnale emesso quando il tema cambia (per applicazione live)
    theme_changed = pyqtSignal(str)  # "dark" | "light"

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

        _add_section("tema", self._build_theme_section())
        _add_section("lingua", self._build_language_section())
        _add_section("hardware", self._build_hardware_section())
        _add_section("git", self._build_git_section())
        _add_section("audit", self._build_audit_section())

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

        Match case-insensitive su:
          - nome interno della sezione (tema, lingua, hardware, git, audit)
          - titolo della QGroupBox (es. '🎨 Tema interfaccia')
          - tutto il testo contenuto: label, pulsanti, placeholder, tooltip
        """
        query = text.strip().lower()
        if not query:
            # Reset: mostra tutte
            for _name, section in self._sections:
                section.show()
            self._update_search_count(len(self._sections), len(self._sections))
            return

        visible = 0
        for name, section in self._sections:
            if self._section_matches(name, section, query):
                section.show()
                visible += 1
            else:
                section.hide()

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

    def _build_theme_section(self) -> QFrame:
        """Sezione per scegliere il tema (chiaro/scuro)."""
        box = QGroupBox("🎨 Tema interfaccia")

        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        self.theme_combo = QComboBox()
        from GUI.theme import theme as _T
        from PyQt6.QtCore import Qt as _Qt
        # Temi divisi in due gruppi (chiari / scuri) con intestazioni non
        # selezionabili. La classificazione è automatica dal .qss.
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
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("Tema:", self.theme_combo)

        hint = QLabel(
            "Il tema scuro è consigliato per i credits e per l'uso notturno.\n"
            "Il tema chiaro è più leggibile in ambienti luminosi."
        )
        hint.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(hint, "role", "muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return box

    def _build_language_section(self) -> QFrame:
        """Sezione per scegliere la lingua (it/en) — Work in progress."""
        box = QGroupBox("🌐 Lingua")

        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("🇮🇹 Italiano", "it")
        self.lang_combo.addItem("🇬🇧 English", "en")
        self.lang_combo.setToolTip("Work in progress")
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        form.addRow("Lingua:", self.lang_combo)

        wip = QLabel("⚠️ Work in progress — la lingua inglese sarà disponibile prossimamente.")
        wip.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(wip, "role", "wip")
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
        form.addRow("Strategia:", self.hw_combo)

        # Hint dinamico (descrizione della strategia selezionata)
        self.hw_hint = QLabel()
        self.hw_hint.setWordWrap(True)
        self.hw_hint.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(self.hw_hint, "role", "muted")
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
        strategy = self.hw_combo.currentData()
        settings_store.set_hardware_strategy(strategy, user_set=True)
        # Salva anche lo stato dell'auto-detect checkbox
        if hasattr(self, "hw_auto_detect"):
            s = settings_store.load_settings()
            s["detect_gpu_at_startup"] = self.hw_auto_detect.isChecked()
            s["user_set_hardware_strategy"] = True
            settings_store.save_settings(s)
        self._update_hw_hint()

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
        idx = 0
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == theme:
                idx = i
                break
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
