"""Pannello Attori per BYTE-SWARMY.

Sostituisce il vecchio testo statico "Modelli Ollama caricati: ..." con
una configurazione interattiva dei 3 attori del sistema:

  1. 🤖 **LLM** — modello principale (es. qwen2.5:1.5b)
  2. 🧠 **Decision Model** — modello decisionale che decide quale task
     eseguire e quando, sulla base dei segnali del Timestral
  3. 🌡️ **Timestral** — controller termico adattivo: monitora la
     temperatura/CPU/tok/s e decide se scattare o no un controllo
     (pausa termica, riduzione contesto, switch modello).

Le impostazioni sono salvate in CONFIG/actors.json.
"""
import json
import os
from typing import Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QGroupBox,
    QFormLayout, QScrollArea, QCheckBox, QMessageBox, QSizePolicy,
    QPlainTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal

# Path del file configurazione attori
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTORS_FILE = os.path.join(_BASE, "CONFIG", "actors.json")

# Modelli Ollama suggeriti (placeholder)
OLLAMA_MODELS = [
    "qwen2.5:1.5b",
    "qwen2.5-coder:1.5b",
    "qwen2.5:3b",
    "qwen2.5-coder:3b",
    "llama3:8b",
    "mistral:7b",
    "phi3:mini",
    "gemma2:2b",
    "deepseek-coder:1.3b",
]

# H3: Pesi modelli per ogni attore (light/medium/heavy).
# L'utente sceglie il "peso" per ogni attore; il sistema propone un modello
# di default appropriato per quel peso. Il Timestral ha solo "light" perché
# DEVE restare leggero (gira in RAM su CPU, mai su GPU).
ACTOR_WEIGHTS = ("light", "medium", "heavy")

# Mapping peso → modello consigliato (per ogni attore)
WEIGHT_DEFAULT_MODELS = {
    "llm": {
        "light":  "qwen2.5:1.5b",       # ~1GB RAM, per task semplici
        "medium": "qwen2.5:3b",         # ~2GB RAM, bilanciato
        "heavy":  "llama3:8b",         # ~5GB VRAM, per task complessi
    },
    "decision_model": {
        "light":  "qwen2.5:1.5b",       # veloce, per decisioni semplici
        "medium": "qwen2.5:3b",        # bilanciato, ragionamento medio
        "heavy":  "qwen2.5:7b",        # ragionamento complesso
    },
    "timestral": {
        # Timestral: SOLO light — gatekeeper in RAM su CPU (H4)
        "light":  "qwen2.5:0.5b",      # ~500MB RAM, polling leggero
        "medium": "qwen2.5:0.5b",      # forzato a light
        "heavy":  "qwen2.5:0.5b",      # forzato a light
    },
}


def weight_default_model(actor: str, weight: str) -> str:
    """Ritorna il modello di default per (actor, weight)."""
    return WEIGHT_DEFAULT_MODELS.get(actor, {}).get(weight, "qwen2.5:1.5b")


def ollama_list_models(timeout: float = 3.0) -> list:
    """T2.4 — Modelli Ollama INSTALLATI reali (prima colonna di `ollama
    list`). Fallback a [] se `ollama` non esiste o fallisce — il chiamante
    usa OLLAMA_MODELS come lista di backup."""
    import subprocess
    try:
        r = subprocess.run(["ollama", "list"],
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return []
        models = []
        for line in r.stdout.splitlines()[1:]:   # la 1a riga è l'header
            name = line.split()[0] if line.split() else ""
            if name:
                models.append(name)
        return models
    except Exception:
        return []

DEFAULTS = {
    "llm": {
        "model": "qwen2.5:1.5b",
        # H3: peso del modello (light/medium/heavy). Cambiando il peso,
        # il sistema propone un modello di default appropriato.
        "weight": "medium",
        "temperature": 0.1,
        "num_ctx": 2048,
        "num_predict": 256,
    },
    "decision_model": {
        "model": "qwen2.5:1.5b",
        # H3: peso del decision model (light per pianificazione semplice,
        # heavy per ragionamento complesso).
        "weight": "light",
        "temperature": 0.4,
        "num_ctx": 3072,
        "num_predict": 512,
    },
    "timestral": {
        "enabled": True,
        # H3+H4: peso del Timestral — SOLO "light" accettato, sempre in
        # RAM su CPU. Forzato dal sistema (gli altri pesi sono ignorati).
        "weight": "light",
        # H4: force_cpu=True — il Timestral NON usa mai la GPU. Sempre
        # in RAM su CPU per restare reattivo anche sotto sforzo.
        "force_cpu": True,
        # Soglia temperatura CPU oltre la quale scatta la pausa termica (°C)
        "cpu_temp_threshold": 80,
        # Soglia temperatura GPU
        "gpu_temp_threshold": 75,
        # A1: soglia di ripresa (°C) — il gate si riapre solo sotto questa
        # temperatura. Default 65; deve essere <= pause_cpu per evitare
        # oscillazioni. Cablato in TimestralGatekeeper.resume_temp.
        "resume_temp_threshold": 65,
        # Tok/s minimo: se sotto, riduci contesto o switch modello (A2)
        "min_tokens_per_sec": 5.0,
        # Secondi di pausa quando si supera la soglia termica
        "thermal_pause_seconds": 30,
        # Se True, scatta il controllo SOLO se GPU presente (A3)
        "check_only_if_gpu": False,
        # Se True, quando scatta la pausa termica anche il decision model
        # viene messo in pausa (altrimenti continua a pianificare) (A4)
        "pause_decision_model_too": True,
        # Intervallo di monitoraggio (secondi)
        "monitor_interval_sec": 30,
    },
}


def load_actors() -> Dict:
    """Carica gli attori da CONFIG/actors.json (con fallback ai default)."""
    if not os.path.exists(ACTORS_FILE):
        return {k: dict(v) for k, v in DEFAULTS.items()}
    try:
        with open(ACTORS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = {k: dict(v) for k, v in DEFAULTS.items()}
        for k in merged:
            if k in data:
                merged[k].update(data[k])
        return merged
    except (json.JSONDecodeError, OSError):
        return {k: dict(v) for k, v in DEFAULTS.items()}


def save_actors(actors: Dict) -> bool:
    try:
        os.makedirs(os.path.dirname(ACTORS_FILE), exist_ok=True)
        with open(ACTORS_FILE, "w", encoding="utf-8") as f:
            json.dump(actors, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f"Errore salvataggio actors: {e}")
        return False


from GUI.theme.theme import set_prop as _theme_prop
from GUI.theme.theme import set_banner as _theme_banner


def _set_combo_text(combo, text: str) -> None:
    """Imposta il testo di un QComboBox NON editabile: aggiunge l'elemento
    se mancante, poi lo seleziona. Evita setEditText (solo editabili)."""
    text = (text or "").strip()
    if not text:
        return
    if combo.findText(text) < 0:
        combo.addItem(text)
    combo.setCurrentText(text)


class ActorsPanel(QWidget):
    """Pannello per configurare i 3 attori: LLM, Decision Model, Timestral."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("actors_panel")
        self._build_ui()
        self._reload_from_store()

    # ──────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header con pulsante Indietro + titolo (stile dal tema)
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>🤖 Attori LLM</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        # Scroll area per il contenuto
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

        # Spiegazione iniziale (banner "info" dal tema)
        expl = QLabel(
            "Configura qui i 3 attori del sistema. Il <b>Timestral</b> "
            "monitora termica/CPU/tok/s e decide se scattare un controllo "
            "(pausa termica, riduzione contesto). Il <b>Decision Model</b> "
            "esegue poi i task pianificati usando l'<b>LLM</b> principale."
        )
        expl.setWordWrap(True)
        _theme_banner(expl, "info")
        lay.addWidget(expl)

        # Sezioni
        lay.addWidget(self._build_llm_section())
        lay.addWidget(self._build_decision_section())
        lay.addWidget(self._build_timestral_section())
        # Spostato dal "Log - Diario di Bordo": sezione Ollama status per
        # verificare che Ollama sia installato e funzionante sul PC.
        lay.addWidget(self._build_ollama_status_section())

        # Pulsante Salva in fondo (primary/start dal tema)
        save_btn = QPushButton("💾 Salva configurazione attori")
        _theme_prop(save_btn, "role", "start")
        save_btn.clicked.connect(self._on_save)
        lay.addWidget(save_btn)

        # Log configurazione (usa lo spazio vuoto per testo utile)
        self.actors_log = QPlainTextEdit()
        self.actors_log.setReadOnly(True)
        self.actors_log.setMaximumBlockCount(100)
        self.actors_log.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; font-size:10.5px;"
        )
        self.actors_log.setPlaceholderText(
            "Log delle operazioni (salvataggio, refresh Ollama, …)…"
        )
        lay.addWidget(self.actors_log, stretch=1)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _build_llm_section(self) -> QGroupBox:
        box = QGroupBox("🤖 LLM — modello principale")
        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        # H3: peso del modello (light/medium/heavy) — cambiandolo propone
        # un modello di default appropriato (via weight_default_model).
        self.llm_weight = QComboBox()
        self.llm_weight.addItem("🪶 Light — piccolo, veloce, poca RAM", "light")
        self.llm_weight.addItem("⚖️ Medium — bilanciato", "medium")
        self.llm_weight.addItem("🏋️ Heavy — potente, più VRAM/RAM", "heavy")
        self.llm_weight.currentIndexChanged.connect(
            lambda _: self._apply_weight("llm", self.llm_weight.currentData())
        )
        form.addRow("Peso:", self.llm_weight)

        self.llm_model = QComboBox()
        # T2.4: prima i modelli installati (ollama list), fallback a lista statica
        installed = ollama_list_models() or OLLAMA_MODELS
        self.llm_model.addItems(installed)
        form.addRow("Modello:", self.llm_model)

        self.llm_temp = QDoubleSpinBox()
        self.llm_temp.setRange(0.0, 2.0)
        self.llm_temp.setSingleStep(0.1)
        self.llm_temp.setDecimals(2)
        self.llm_temp.setToolTip(
            "Creatività delle risposte del modello:\n"
            "• 0.0–0.2 → deterministiche, ideali per codice e patch\n"
            "• 0.3–0.6 → bilanciate, per pianificazione e analisi\n"
            "• > 0.7   → creative, sconsigliate per un coding agent")
        form.addRow("Temperature:", self.llm_temp)

        self.llm_ctx = QSpinBox()
        self.llm_ctx.setRange(512, 32768)
        self.llm_ctx.setSingleStep(512)
        self.llm_ctx.setToolTip(
            "Token di contesto che il modello vede (prompt + codice + storico).\n"
            "Più contesto = più memoria di lavoro, ma più RAM e più lento.\n"
            "Suggerito: 2048 con modelli piccoli su CPU; 4096+ su GPU con\n"
            "4+ GB VRAM. Su GPU piccola (es. GTX 1050 4 GB) non superare 4096.")
        form.addRow("num_ctx (token contesto):", self.llm_ctx)

        self.llm_predict = QSpinBox()
        self.llm_predict.setRange(64, 8192)
        self.llm_predict.setSingleStep(64)
        self.llm_predict.setToolTip(
            "Numero massimo di token generati in output (lunghezza risposta).\n"
            "256–512 bastano per patch e correzioni; 1024+ per file interi.\n"
            "Valori alti allungano i tempi di generazione a parità di output.")
        form.addRow("num_predict (token max output):", self.llm_predict)

        reset_llm = QPushButton("↺ Ripristina valori predefiniti")
        reset_llm.setToolTip(
            "Reimposta temperature, num_ctx e num_predict della sezione "
            "Worker ai valori predefiniti del sistema.")
        reset_llm.clicked.connect(self._reset_llm_params)
        form.addRow("", reset_llm)

        return box

    def _build_decision_section(self) -> QGroupBox:
        box = QGroupBox("🧠 Decision Model — pianificatore")

        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        # H3: peso del Decision Model
        self.dec_weight = QComboBox()
        self.dec_weight.addItem("🪶 Light — decisioni semplici, veloce", "light")
        self.dec_weight.addItem("⚖️ Medium — ragionamento bilanciato", "medium")
        self.dec_weight.addItem("🏋️ Heavy — ragionamento complesso", "heavy")
        self.dec_weight.currentIndexChanged.connect(
            lambda _: self._apply_weight("decision_model", self.dec_weight.currentData())
        )
        form.addRow("Peso:", self.dec_weight)

        self.dec_model = QComboBox()
        self.dec_model.addItems(ollama_list_models() or OLLAMA_MODELS)
        form.addRow("Modello:", self.dec_model)

        self.dec_temp = QDoubleSpinBox()
        self.dec_temp.setRange(0.0, 2.0)
        self.dec_temp.setSingleStep(0.1)
        self.dec_temp.setDecimals(2)
        self.dec_temp.setToolTip(
            "Creatività del Decision Model (pianificatore):\n"
            "• 0.1–0.3 → scelte stabili e ripetibili (consigliato)\n"
            "• 0.4–0.6 → più flessibile, ma decisioni meno prevedibili\n"
            "• > 0.7   → sconsigliato: il planner deve essere deterministico")
        form.addRow("Temperature:", self.dec_temp)

        self.dec_ctx = QSpinBox()
        self.dec_ctx.setRange(512, 32768)
        self.dec_ctx.setSingleStep(512)
        self.dec_ctx.setToolTip(
            "Token di contesto del Decision Model (stato sistema + task).\n"
            "Suggerito: 3072–4096 per vedere più task in coda; di più non\n"
            "aiuta il planner e consuma RAM.")
        form.addRow("num_ctx:", self.dec_ctx)

        self.dec_predict = QSpinBox()
        self.dec_predict.setRange(64, 8192)
        self.dec_predict.setSingleStep(64)
        self.dec_predict.setToolTip(
            "Token massimi in output del Decision Model (JSON di decisione).\n"
            "512 basta per la pianificazione; valori più alti sprecano tempo.")
        form.addRow("num_predict:", self.dec_predict)

        reset_dec = QPushButton("↺ Ripristina valori predefiniti")
        reset_dec.setToolTip(
            "Reimposta temperature, num_ctx e num_predict della sezione "
            "Decision Model ai valori predefiniti del sistema.")
        reset_dec.clicked.connect(self._reset_dec_params)
        form.addRow("", reset_dec)

        hint = QLabel(
            "Il Decision Model riceve lo stato del sistema dal Timestral e "
            "decide quale task eseguire, in quale ordine, e con quale modello."
        )
        hint.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(hint, "role", "muted")
        hint.setWordWrap(True)
        form.addRow("", hint)

        return box

    def _build_timestral_section(self) -> QGroupBox:
        box = QGroupBox("🌡️ Timestral — controller termico adattivo")

        outer = QVBoxLayout(box)
        outer.setSpacing(10)
        outer.setContentsMargins(14, 14, 14, 14)

        # Abilitazione
        self.ts_enabled = QCheckBox("Abilita Timestral (monitoraggio termico attivo)")
        self.ts_enabled.setStyleSheet("font-size:12px; font-weight:bold;")
        outer.addWidget(self.ts_enabled)

        # H3+H4: nota sul Timestral — sempre light + force_cpu (RAM su CPU)
        ts_note = QLabel(
            "🔒 <b>Timestral sempre LIGHT</b> — gatekeeper in RAM su CPU, "
            "mai su GPU. Deve restare reattivo anche sotto sforzo, quindi "
            "non carichiamo modelli pesanti. Il peso è fisso a 'light' e "
            "<code>force_cpu=True</code> è bloccato (vedi CONFIG/actors.json)."
        )
        ts_note.setWordWrap(True)
        _theme_banner(ts_note, "info")
        outer.addWidget(ts_note)

        form = QFormLayout()
        form.setSpacing(8)

        self.ts_cpu_threshold = QSpinBox()
        self.ts_cpu_threshold.setRange(40, 100)
        self.ts_cpu_threshold.setSuffix(" °C")
        self.ts_cpu_threshold.setToolTip(
            "Soglia temperatura CPU: se superata, scatta la pausa termica"
        )
        form.addRow("Soglia CPU (pausa termica):", self.ts_cpu_threshold)

        self.ts_gpu_threshold = QSpinBox()
        self.ts_gpu_threshold.setRange(40, 100)
        self.ts_gpu_threshold.setSuffix(" °C")
        self.ts_gpu_threshold.setToolTip(
            "Soglia temperatura GPU: se superata, scatta la pausa termica"
        )
        form.addRow("Soglia GPU (pausa termica):", self.ts_gpu_threshold)

        # A1: soglia di ripresa — il gate si riapre solo sotto questa temperatura.
        # Deve essere <= Soglia CPU per evitare oscillazioni (isteresi).
        self.ts_resume_threshold = QSpinBox()
        self.ts_resume_threshold.setRange(30, 95)
        self.ts_resume_threshold.setSuffix(" °C")
        self.ts_resume_threshold.setToolTip(
            "Soglia di RIPRESA: il gate si riapre solo quando la temperatura "
            "scende sotto questo valore. Deve essere <= Soglia CPU (isteresi)."
        )
        form.addRow("Soglia RIPRESA (isteresi):", self.ts_resume_threshold)

        self.ts_min_tps = QDoubleSpinBox()
        self.ts_min_tps.setRange(0.1, 100.0)
        self.ts_min_tps.setSingleStep(0.5)
        self.ts_min_tps.setDecimals(1)
        self.ts_min_tps.setSuffix(" t/s")
        self.ts_min_tps.setToolTip(
            "Sotto questa velocità, il Timestral riduce contesto o switcha modello"
        )
        form.addRow("Soglia tok/s minima:", self.ts_min_tps)

        self.ts_pause_sec = QSpinBox()
        self.ts_pause_sec.setRange(5, 600)
        self.ts_pause_sec.setSuffix(" s")
        self.ts_pause_sec.setToolTip(
            "Per quanti secondi mettere in pausa dopo aver superato la soglia"
        )
        form.addRow("Durata pausa termica:", self.ts_pause_sec)

        self.ts_interval = QSpinBox()
        self.ts_interval.setRange(5, 600)
        self.ts_interval.setSuffix(" s")
        self.ts_interval.setToolTip("Ogni quanto monitorare (polling)")
        form.addRow("Intervallo monitoraggio:", self.ts_interval)

        self.ts_check_only_if_gpu = QCheckBox(
            "Scatta controlli SOLO se GPU presente"
        )
        self.ts_check_only_if_gpu.setToolTip(
            "Se flaggato, i controlli termici scattano solo quando c'è una GPU attiva"
        )
        form.addRow("", self.ts_check_only_if_gpu)

        self.ts_pause_decision_too = QCheckBox(
            "Metti in pausa anche il Decision Model (oltre ai worker)"
        )
        self.ts_pause_decision_too.setToolTip(
            "Se flaggato, durante la pausa termica anche il decision model viene fermato; "
            "altrimenti continua a pianificare"
        )
        form.addRow("", self.ts_pause_decision_too)

        outer.addLayout(form)

        hint = QLabel(
            "Il Timestral monitora ogni N secondi: se le metriche superano le "
            "soglie, scatta una pausa termica (worker fermati per N secondi). "
            "Se i tok/s scendono sotto il minimo, riduce il contesto o switcha modello."
        )
        hint.setStyleSheet("font-size:10px; font-style:italic;")
        _theme_prop(hint, "role", "muted")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        return box

    def _build_ollama_status_section(self) -> QGroupBox:
        """Sezione '🦙 Ollama status' — verificare se Ollama è installato e
        funzionante sul PC. Spostato dal 'Log - Diario di Bordo' (che ora
        contiene solo il diario ByteSwarm).

        Mostra:
          - Stato installazione (✓ trovato / ✗ mancante)
          - Versione di Ollama
          - Modelli installati (numero)
          - Pulsante "🔄 Aggiorna" per rieseguire il check
          - Pulsante "🦙 Apri cartella Ollama" (se trovato)
        """
        import shutil, subprocess

        box = QGroupBox("🦙 Ollama — stato del runtime")

        outer = QVBoxLayout(box)
        outer.setSpacing(8)
        outer.setContentsMargins(14, 14, 14, 14)

        # Riga stato + pulsanti
        head = QHBoxLayout()
        head.setSpacing(8)

        # Stato Ollama
        ollama_path = shutil.which("ollama")
        self._ollama_status_label = QLabel()
        self._ollama_status_label.setStyleSheet(
            "font-size:11px; font-weight:bold; padding:6px 12px; border-radius:6px;"
        )
        head.addWidget(self._ollama_status_label)
        head.addStretch()

        # Pulsante refresh (primario dal tema)
        refresh_btn = QPushButton("🔄 Aggiorna")
        _theme_prop(refresh_btn, "role", "primary")
        refresh_btn.clicked.connect(self._refresh_ollama_status)
        head.addWidget(refresh_btn)

        # Pulsante apri cartella Ollama (solo se trovato) — stile default
        self._open_ollama_btn = QPushButton("📂 Apri cartella Ollama")
        self._open_ollama_btn.clicked.connect(self._open_ollama_folder)
        head.addWidget(self._open_ollama_btn)
        outer.addLayout(head)

        # Dettagli (versione + numero modelli + primo modello) — colore tema
        self._ollama_details = QLabel()
        self._ollama_details.setStyleSheet("font-size:11px; padding:4px 8px;")
        _theme_prop(self._ollama_details, "role", "muted")
        self._ollama_details.setWordWrap(True)
        outer.addWidget(self._ollama_details)

        # Esegui check iniziale
        self._refresh_ollama_status()

        return box

    def _refresh_ollama_status(self):
        """Esegue il check di Ollama: esiste? versione? modelli installati?"""
        import shutil, subprocess

        ollama_path = shutil.which("ollama")
        if not ollama_path:
            self._ollama_status_label.setText("❌ Ollama NON installato")
            _theme_banner(self._ollama_status_label, "error")
            self._ollama_status_label.setStyleSheet(
                "font-size:11px; font-weight:bold; padding:6px 12px;"
            )
            self._ollama_details.setText(
                "Installa Ollama da https://ollama.com/download per usare i "
                "modelli LLM locali. Senza Ollama, gli attori LLM e Decision "
                "Model non funzioneranno."
            )
            self._open_ollama_btn.setVisible(False)
            return

        # Ollama trovato: recupera versione + modelli
        try:
            r_ver = subprocess.run(
                [ollama_path, "--version"],
                capture_output=True, text=True, timeout=3,
            )
            version = r_ver.stdout.strip() or r_ver.stderr.strip() or "?"
            # Spesso la versione è in stderr ("ollama version is 0.5.7")
            if "version" in version.lower():
                # Estrai la parte dopo "version is"
                import re
                m = re.search(r"version is\s+([\d.]+)", version, re.I)
                if m:
                    version = m.group(1)
        except Exception:
            version = "?"

        try:
            models = ollama_list_models(timeout=3)
        except Exception:
            models = []

        self._ollama_status_label.setText(f"✅ Ollama installato (v{version})")
        _theme_banner(self._ollama_status_label, "ok")
        self._ollama_status_label.setStyleSheet(
            "font-size:11px; font-weight:bold; padding:6px 12px;"
        )
        if models:
            self._ollama_details.setText(
                f"Modelli installati: {len(models)}\n"
                f"Primi: {', '.join(models[:5])}"
            )
        else:
            self._ollama_details.setText(
                "Nessun modello installato. Esegui: ollama pull qwen2.5:1.5b "
                "per scaricare un modello leggero."
            )

        # Determina cartella Ollama (default ~/.ollama)
        home = os.path.expanduser("~")
        ollama_dir = os.path.join(home, ".ollama")
        self._open_ollama_btn.setVisible(os.path.isdir(ollama_dir))
        self._ollama_dir = ollama_dir

    def _open_ollama_folder(self):
        """Apre la cartella ~/.ollama nel file manager del sistema."""
        import subprocess, shutil
        ollama_dir = getattr(self, "_ollama_dir", None)
        if not ollama_dir or not os.path.isdir(ollama_dir):
            return
        try:
            # Linux: xdg-open; macOS: open; Windows: explorer
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", ollama_dir])
            elif shutil.which("open"):
                subprocess.Popen(["open", ollama_dir])
            else:
                # Fallback: stampa il path
                self._ollama_details.setText(
                    f"Cartella Ollama: {ollama_dir}\n"
                    f"(apri manualmente con il tuo file manager)"
                )
        except Exception as e:
            self._ollama_details.setText(f"Errore apertura cartella: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Stili: rimossi gli inline hardcodati (white/#1a1a1a) — lo stile di
    # QGroupBox/QComboBox/QSpinBox ora arriva dal tema app-level (.qss),
    # quindi segue il tema live. NB: se serviva min-width, va rimpiazzato
    # con QSize hint sul singolo widget, non con colore inline.
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # Carica / salva
    # ──────────────────────────────────────────────────────────────────
    def _reload_from_store(self):
        a = load_actors()
        # LLM
        # H3: weight combo (con fallback a "medium" se mancante)
        llm_w = a["llm"].get("weight", "medium")
        for i in range(self.llm_weight.count()):
            if self.llm_weight.itemData(i) == llm_w:
                self.llm_weight.setCurrentIndex(i)
                break
        _set_combo_text(self.llm_model, a["llm"]["model"])
        self.llm_temp.setValue(a["llm"]["temperature"])
        self.llm_ctx.setValue(a["llm"]["num_ctx"])
        self.llm_predict.setValue(a["llm"]["num_predict"])
        # Decision
        dec_w = a["decision_model"].get("weight", "light")
        for i in range(self.dec_weight.count()):
            if self.dec_weight.itemData(i) == dec_w:
                self.dec_weight.setCurrentIndex(i)
                break
        _set_combo_text(self.dec_model, a["decision_model"]["model"])
        self.dec_temp.setValue(a["decision_model"]["temperature"])
        self.dec_ctx.setValue(a["decision_model"]["num_ctx"])
        self.dec_predict.setValue(a["decision_model"]["num_predict"])
        # Timestral
        t = a["timestral"]
        self.ts_enabled.setChecked(t["enabled"])
        self.ts_cpu_threshold.setValue(t["cpu_temp_threshold"])
        self.ts_gpu_threshold.setValue(t["gpu_temp_threshold"])
        # A1: resume_temp_threshold (con fallback a 65 se mancante in file vecchi)
        self.ts_resume_threshold.setValue(t.get("resume_temp_threshold", 65))
        self.ts_min_tps.setValue(t["min_tokens_per_sec"])
        self.ts_pause_sec.setValue(t["thermal_pause_seconds"])
        self.ts_interval.setValue(t["monitor_interval_sec"])
        self.ts_check_only_if_gpu.setChecked(t["check_only_if_gpu"])
        self.ts_pause_decision_too.setChecked(t["pause_decision_model_too"])

    # ── Reset parametri ai valori predefiniti ────────────────────────
    # Reimpostano SOLO i parametri di tuning (temperature/num_ctx/
    # num_predict): modello e peso scelte dall'utente restano invariati.

    def _reset_llm_params(self) -> None:
        d = DEFAULTS["llm"]
        self.llm_temp.setValue(d["temperature"])
        self.llm_ctx.setValue(d["num_ctx"])
        self.llm_predict.setValue(d["num_predict"])

    def _reset_dec_params(self) -> None:
        d = DEFAULTS["decision_model"]
        self.dec_temp.setValue(d["temperature"])
        self.dec_ctx.setValue(d["num_ctx"])
        self.dec_predict.setValue(d["num_predict"])

    def _apply_weight(self, actor: str, weight: str):
        """H3: quando l'utente cambia il peso di un attore, propone il
        modello di default appropriato (se il modello attuale è il default
        del vecchio peso, lo sostituisce; altrimenti lascia stare).

        Timestral: forzato a "light" (H4) — ignorato se l'utente prova a
        cambiarlo da UI (non c'è combo).
        """
        if weight not in ACTOR_WEIGHTS:
            return
        # Per il Timestral non c'è UI di peso — è sempre light
        if actor == "llm":
            current_model = self.llm_model.currentText()
            # Se il modello attuale è uno dei default di un altro peso,
            # sostituiscilo con il default del nuovo peso
            for w in ACTOR_WEIGHTS:
                if current_model == weight_default_model("llm", w):
                    _set_combo_text(self.llm_model, weight_default_model("llm", weight))
                    return
            # Se l'utente aveva un modello custom, non toccare — solo hint
        elif actor == "decision_model":
            current_model = self.dec_model.currentText()
            for w in ACTOR_WEIGHTS:
                if current_model == weight_default_model("decision_model", w):
                    _set_combo_text(self.dec_model, weight_default_model("decision_model", weight))
                    return

    def _on_save(self):
        a = {
            "llm": {
                "model": self.llm_model.currentText(),
                "weight": self.llm_weight.currentData(),
                "temperature": self.llm_temp.value(),
                "num_ctx": self.llm_ctx.value(),
                "num_predict": self.llm_predict.value(),
            },
            "decision_model": {
                "model": self.dec_model.currentText(),
                "weight": self.dec_weight.currentData(),
                "temperature": self.dec_temp.value(),
                "num_ctx": self.dec_ctx.value(),
                "num_predict": self.dec_predict.value(),
            },
            "timestral": {
                "enabled": self.ts_enabled.isChecked(),
                # H3+H4: Timestral sempre light + force_cpu (cablato)
                "weight": "light",
                "force_cpu": True,
                "cpu_temp_threshold": self.ts_cpu_threshold.value(),
                "gpu_temp_threshold": self.ts_gpu_threshold.value(),
                "resume_temp_threshold": self.ts_resume_threshold.value(),
                "min_tokens_per_sec": self.ts_min_tps.value(),
                "thermal_pause_seconds": self.ts_pause_sec.value(),
                "check_only_if_gpu": self.ts_check_only_if_gpu.isChecked(),
                "pause_decision_model_too": self.ts_pause_decision_too.isChecked(),
                "monitor_interval_sec": self.ts_interval.value(),
            },
        }
        ok = save_actors(a)
        import time as _t
        if ok:
            self.actors_log.appendPlainText(
                f"[{_t.strftime('%H:%M:%S')}] Configurazione salvata OK "
                f"(LLM: {a['llm']['model']}, Decision: {a['decision_model']['model']})"
            )
            QMessageBox.information(
                self, "Salvato",
                "Configurazione attori salvata in CONFIG/actors.json.\n\n"
                "Riavvia l'orchestratore per applicare le modifiche."
            )
        else:
            self.actors_log.appendPlainText(
                f"[{_t.strftime('%H:%M:%S')}] ERRORE salvataggio"
            )
            QMessageBox.critical(self, "Errore", "Salvataggio fallito (vedi console).")

    def _back_to_main(self):
        """Torna alla plancia di controllo principale."""
        parent = self.parent()
        while parent and not hasattr(parent, "back_to_main"):
            parent = parent.parent()
        if parent and hasattr(parent, "back_to_main"):
            parent.back_to_main()
