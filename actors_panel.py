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
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 0, 0, 0)

        # Spiegazione iniziale
        expl = QLabel(
            "Configura qui i 3 attori del sistema. Il <b>Timestral</b> "
            "monitora termica/CPU/tok/s e decide se scattare un controllo "
            "(pausa termica, riduzione contesto). Il <b>Decision Model</b> "
            "esegue poi i task pianificati usando l'<b>LLM</b> principale."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet(
            "background:#f0f9ff; border:1px solid #bae6fd; border-radius:8px; "
            "padding:10px; font-size:11px; color:#0c4a6e;"
        )
        lay.addWidget(expl)

        # Sezioni
        lay.addWidget(self._build_llm_section())
        lay.addWidget(self._build_decision_section())
        lay.addWidget(self._build_timestral_section())

        # Pulsante Salva in fondo
        save_btn = QPushButton("💾 Salva configurazione attori")
        save_btn.setStyleSheet(
            "QPushButton { background:#16a34a; color:#ffffff; border:none; "
            "padding:10px 24px; border-radius:6px; font-weight:bold; font-size:13px; }"
            "QPushButton:hover { background:#15803d; }"
        )
        save_btn.clicked.connect(self._on_save)
        lay.addWidget(save_btn)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _build_llm_section(self) -> QGroupBox:
        box = QGroupBox("🤖 LLM — modello principale")
        box.setStyleSheet(self._group_style())
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
        self.llm_weight.setStyleSheet(self._combo_style())
        form.addRow("Peso:", self.llm_weight)

        self.llm_model = QComboBox()
        self.llm_model.setEditable(True)
        # T2.4: prima i modelli installati (ollama list), fallback a lista statica
        installed = ollama_list_models() or OLLAMA_MODELS
        self.llm_model.addItems(installed)
        self.llm_model.setStyleSheet(self._combo_style())
        form.addRow("Modello:", self.llm_model)

        self.llm_temp = QDoubleSpinBox()
        self.llm_temp.setRange(0.0, 2.0)
        self.llm_temp.setSingleStep(0.1)
        self.llm_temp.setDecimals(2)
        self.llm_temp.setStyleSheet(self._spin_style())
        form.addRow("Temperature:", self.llm_temp)

        self.llm_ctx = QSpinBox()
        self.llm_ctx.setRange(512, 32768)
        self.llm_ctx.setSingleStep(512)
        self.llm_ctx.setStyleSheet(self._spin_style())
        form.addRow("num_ctx (token contesto):", self.llm_ctx)

        self.llm_predict = QSpinBox()
        self.llm_predict.setRange(64, 8192)
        self.llm_predict.setSingleStep(64)
        self.llm_predict.setStyleSheet(self._spin_style())
        form.addRow("num_predict (token max output):", self.llm_predict)

        return box

    def _build_decision_section(self) -> QGroupBox:
        box = QGroupBox("🧠 Decision Model — pianificatore")
        box.setStyleSheet(self._group_style())
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
        self.dec_weight.setStyleSheet(self._combo_style())
        form.addRow("Peso:", self.dec_weight)

        self.dec_model = QComboBox()
        self.dec_model.setEditable(True)
        self.dec_model.addItems(ollama_list_models() or OLLAMA_MODELS)
        self.dec_model.setStyleSheet(self._combo_style())
        form.addRow("Modello:", self.dec_model)

        self.dec_temp = QDoubleSpinBox()
        self.dec_temp.setRange(0.0, 2.0)
        self.dec_temp.setSingleStep(0.1)
        self.dec_temp.setDecimals(2)
        self.dec_temp.setStyleSheet(self._spin_style())
        form.addRow("Temperature:", self.dec_temp)

        self.dec_ctx = QSpinBox()
        self.dec_ctx.setRange(512, 32768)
        self.dec_ctx.setSingleStep(512)
        self.dec_ctx.setStyleSheet(self._spin_style())
        form.addRow("num_ctx:", self.dec_ctx)

        self.dec_predict = QSpinBox()
        self.dec_predict.setRange(64, 8192)
        self.dec_predict.setSingleStep(64)
        self.dec_predict.setStyleSheet(self._spin_style())
        form.addRow("num_predict:", self.dec_predict)

        hint = QLabel(
            "Il Decision Model riceve lo stato del sistema dal Timestral e "
            "decide quale task eseguire, in quale ordine, e con quale modello."
        )
        hint.setStyleSheet("color:#666; font-size:10px; font-style:italic;")
        hint.setWordWrap(True)
        form.addRow("", hint)

        return box

    def _build_timestral_section(self) -> QGroupBox:
        box = QGroupBox("🌡️ Timestral — controller termico adattivo")
        box.setStyleSheet(self._group_style())
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
        ts_note.setStyleSheet(
            "background:#f0f9ff; border:1px solid #bae6fd; border-radius:6px; "
            "padding:8px; font-size:10px; color:#0c4a6e;"
        )
        outer.addWidget(ts_note)

        form = QFormLayout()
        form.setSpacing(8)

        self.ts_cpu_threshold = QSpinBox()
        self.ts_cpu_threshold.setRange(40, 100)
        self.ts_cpu_threshold.setSuffix(" °C")
        self.ts_cpu_threshold.setStyleSheet(self._spin_style())
        self.ts_cpu_threshold.setToolTip(
            "Soglia temperatura CPU: se superata, scatta la pausa termica"
        )
        form.addRow("Soglia CPU (pausa termica):", self.ts_cpu_threshold)

        self.ts_gpu_threshold = QSpinBox()
        self.ts_gpu_threshold.setRange(40, 100)
        self.ts_gpu_threshold.setSuffix(" °C")
        self.ts_gpu_threshold.setStyleSheet(self._spin_style())
        self.ts_gpu_threshold.setToolTip(
            "Soglia temperatura GPU: se superata, scatta la pausa termica"
        )
        form.addRow("Soglia GPU (pausa termica):", self.ts_gpu_threshold)

        # A1: soglia di ripresa — il gate si riapre solo sotto questa temperatura.
        # Deve essere <= Soglia CPU per evitare oscillazioni (isteresi).
        self.ts_resume_threshold = QSpinBox()
        self.ts_resume_threshold.setRange(30, 95)
        self.ts_resume_threshold.setSuffix(" °C")
        self.ts_resume_threshold.setStyleSheet(self._spin_style())
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
        self.ts_min_tps.setStyleSheet(self._spin_style())
        self.ts_min_tps.setToolTip(
            "Sotto questa velocità, il Timestral riduce contesto o switcha modello"
        )
        form.addRow("Soglia tok/s minima:", self.ts_min_tps)

        self.ts_pause_sec = QSpinBox()
        self.ts_pause_sec.setRange(5, 600)
        self.ts_pause_sec.setSuffix(" s")
        self.ts_pause_sec.setStyleSheet(self._spin_style())
        self.ts_pause_sec.setToolTip(
            "Per quanti secondi mettere in pausa dopo aver superato la soglia"
        )
        form.addRow("Durata pausa termica:", self.ts_pause_sec)

        self.ts_interval = QSpinBox()
        self.ts_interval.setRange(5, 600)
        self.ts_interval.setSuffix(" s")
        self.ts_interval.setStyleSheet(self._spin_style())
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
        hint.setStyleSheet("color:#666; font-size:10px; font-style:italic;")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        return box

    # ──────────────────────────────────────────────────────────────────
    # Stili (riutilizzo gli stessi del SettingsPanel)
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
            "font-size:12px; min-width:200px; }"
            "QComboBox:hover { border-color:#16a34a; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#1a1a1a; "
            "selection-background-color:#f0f9ff; }"
        )

    def _spin_style(self) -> str:
        return (
            "QSpinBox, QDoubleSpinBox { background:#ffffff; color:#1a1a1a; "
            "border:1px solid #d0d0d0; padding:6px 10px; border-radius:6px; "
            "font-size:12px; min-width:120px; }"
            "QSpinBox:hover, QDoubleSpinBox:hover { border-color:#16a34a; }"
        )

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
        self.llm_model.setEditText(a["llm"]["model"])
        self.llm_temp.setValue(a["llm"]["temperature"])
        self.llm_ctx.setValue(a["llm"]["num_ctx"])
        self.llm_predict.setValue(a["llm"]["num_predict"])
        # Decision
        dec_w = a["decision_model"].get("weight", "light")
        for i in range(self.dec_weight.count()):
            if self.dec_weight.itemData(i) == dec_w:
                self.dec_weight.setCurrentIndex(i)
                break
        self.dec_model.setEditText(a["decision_model"]["model"])
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
                    self.llm_model.setEditText(weight_default_model("llm", weight))
                    return
            # Se l'utente aveva un modello custom, non toccare — solo hint
        elif actor == "decision_model":
            current_model = self.dec_model.currentText()
            for w in ACTOR_WEIGHTS:
                if current_model == weight_default_model("decision_model", w):
                    self.dec_model.setEditText(weight_default_model("decision_model", weight))
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
        if ok:
            QMessageBox.information(
                self, "Salvato",
                "Configurazione attori salvata in CONFIG/actors.json.\n\n"
                "Riavvia l'orchestratore per applicare le modifiche."
            )
        else:
            QMessageBox.critical(self, "Errore", "Salvataggio fallito (vedi console).")

    def _back_to_main(self):
        """Torna alla plancia di controllo principale."""
        parent = self.parent()
        while parent and not hasattr(parent, "back_to_main"):
            parent = parent.parent()
        if parent and hasattr(parent, "back_to_main"):
            parent.back_to_main()
