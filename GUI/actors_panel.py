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
import re
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
# Unica fonte in CORE/constants.py (usata anche da hardware_detector
# per il calcolo della capacità): qui solo alias per compatibilità.
from CORE.constants import (  # noqa: E402
    ACTOR_WEIGHT_DEFAULT_MODELS as WEIGHT_DEFAULT_MODELS,
    weight_default_model,
)
from CORE.gui_worker import BaseWorker  # noqa: E402
from CORE import model_knowledge as _mk  # noqa: E402


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
        # 🆕 Modalità diretta (senza tool): se True, TUTTI i worker dei task
        # usano run_direct (skill + verifica host) invece del loop ReAct.
        # Override master rispetto al flag no_tools per-modello in
        # config.toml [models.*].
        "no_tools": False,
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


def model_use_hint(name: str) -> str:
    """A cosa è meglio usare un modello (per la nota tra parentesi).

    🆕 Prima la CONOSCENZA (CONFIG/model_knowledge.json: utilizzo reale
    della voce, es. 'Coding Bilanciato'), poi l'euristica sul nome come
    fallback per i modelli fuori catalogo.
    """
    try:
        e = _mk.entry_for(name)
        if e is not None and e.get("utilizzo"):
            return str(e.get("utilizzo"))
    except Exception:
        pass  # fail-open → euristica
    n = (name or "").lower()
    if "coder" in n or "code" in n:
        return "codice"
    if "deepseek" in n:
        return "ragionamento/codice"
    if "phi" in n:
        return "ragionamento leggero"
    if "gemma" in n:
        return "generale leggero"
    if "mistral" in n:
        return "generale"
    if "llama" in n:
        return "generale"
    if "qwen" in n:
        return "generale"
    return "generale"


def sorted_model_choices(models) -> list:
    """[(etichetta decorata, nome reale)] — ordine ALFABETICO, poi grandezza.

    🆕 Etichetta: icona di collocazione (📌 locale / 🌍 cloud) davanti al
    nome e tag di capacità a fine nome (💻 coding, 🧠 ragionamento, …)
    dalla conoscenza; segue la nota d'uso tra parentesi. Il dato reale
    (nome senza decorazioni) resta in currentData per il salvataggio.
    """
    from CORE.hardware_detector import _estimate_model_size_gb
    installed = _mk.installed_names()
    uniq = sorted(set(models or []),
                  key=lambda m: (m.lower(), _estimate_model_size_gb(m)))
    out = []
    for m in uniq:
        try:
            e = _mk.entry_for(m)
        except Exception:
            e = None
        if e is not None:
            icon = _mk.place_icon(e, installed)
            tag = _mk.tag_for(e)
        else:
            # fuori catalogo: 🌍 se il nome dichiara il cloud, 📌 altrimenti
            icon = "🌍" if _mk.is_cloud_name(m) else "📌"
            tag = ""
        label = f"{icon} {m}"
        if tag:
            label += f" · {tag}"
        out.append((f"{label} ({model_use_hint(m)})", m))
    return out


def fill_model_combo(combo, models, with_default: bool = False) -> None:
    """Riempie un combo modelli con etichette annotate (data = nome reale)."""
    combo.clear()
    if with_default:
        combo.addItem("(default)", "(default)")
    for label, name in sorted_model_choices(models):
        combo.addItem(label, name)


def combo_current_model(combo) -> str:
    """Nome REALE del modello selezionato (data, o etichetta ripulita)."""
    d = combo.currentData()
    if d:
        return d
    txt = combo.currentText()
    # Fallback storico: etichette annotate 'nome (uso)'. Tolgo anche le
    # decorazioni nuove (icona di collocazione e tag di capacità).
    txt = re.sub(r"^(📌|🌍|⬇)\s*", "", txt)
    txt = txt.split(" (")[0]
    txt = re.sub(r"\s·\s\S.*$", "", txt)
    return txt.strip()


def _set_combo_text(combo, text: str) -> None:
    """Seleziona il modello `text` in un combo annotato (data = nome).
    Se assente lo aggiunge come 'nome (generale)' con data=nome."""
    text = (text or "").strip()
    if not text:
        return
    idx = combo.findData(text)
    if idx < 0:
        combo.addItem(f"{text} (generale)", text)
        idx = combo.findData(text)
    combo.setCurrentIndex(idx)


def _human_size(n) -> str:
    """Byte → stringa leggibile (2.7 GB / 460 MB)."""
    try:
        n = float(n)
    except Exception:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return "?"


class ModelPullWorker(BaseWorker):
    """⬇ Scarica un modello Ollama in background via API ``/api/pull``.

    L'API in streaming restituisce righe JSON ({"status", "total",
    "completed"}, {"error"} alla fine se fallisce) — a differenza del
    CLI, che in ambienti non-TTY emette una progress bar ANSI
    illeggibile per il parsing. Stesso canale HTTP di ModelClient.
    """

    def __init__(self, model_name: str, parent=None):
        super().__init__(parent)
        self.model_name = model_name

    def _execute(self):
        import json as _json
        import urllib.request

        from CORE.constants import OLLAMA_HOST

        url = f"{OLLAMA_HOST}/api/pull"
        payload = _json.dumps(
            {"name": self.model_name, "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"})
        last_pct = -100
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                if self.is_cancelled():
                    raise RuntimeError("Download annullato")
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    obj = _json.loads(line)
                except Exception:
                    continue
                if "error" in obj:
                    raise RuntimeError(
                        f"ollama: {obj['error']} "
                        f"(modello inesistente o registry non raggiungibile?)")
                status = str(obj.get("status", ""))
                total, done = obj.get("total"), obj.get("completed")
                if (isinstance(total, int) and isinstance(done, int)
                        and total > 0):
                    pct = int(done * 100 / total)
                    if pct - last_pct >= 5 or pct == 100:
                        self.progress.emit(
                            f"⬇ {self.model_name}: {pct}% "
                            f"({_human_size(done)} / {_human_size(total)})")
                        last_pct = pct
                elif status:
                    self.progress.emit(f"⬇ {self.model_name}: {status}")
        self.finished_ok.emit(self.model_name)


class ActorsPanel(QWidget):
    """Pannello per configurare i 3 attori: LLM, Decision Model, Timestral."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("actors_panel")
        # 🆕 Righe "Consigliati (conoscenza)" per attore + worker download
        self._knowledge: dict = {}
        self._pull_worker: ModelPullWorker | None = None
        self._pull_actor: str | None = None
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
        lay.addWidget(self._build_models_direct_section())
        lay.addWidget(self._build_decision_section())
        lay.addWidget(self._build_timestral_section())
        # Spostato dal "Log - Diario di Bordo": sezione Ollama status per
        # verificare che Ollama sia installato e funzionante sul PC.
        lay.addWidget(self._build_ollama_status_section())
        # 🆕 Tutti gli altri modelli della conoscenza non installati (⬇)
        lay.addWidget(self._build_missing_models_section())

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
        # T2.4: prima i modelli installati (ollama list), fallback a lista
        # statica. Ordinati alfabeticamente (+ grandezza) con nota d'uso.
        installed = ollama_list_models() or OLLAMA_MODELS
        fill_model_combo(self.llm_model, installed)
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

        # 🆕 Generazione diretta (senza tool): per modelli piccoli che non
        # seguono il formato JSON dei tool. Override master per i worker.
        self.llm_no_tools = QCheckBox()
        self.llm_no_tools.setToolTip(
            "Modalità diretta (senza tool) per TUTTI i worker dei task:\n"
            "• il modello risponde con UN blocco di codice (niente JSON)\n"
            "• l'host estrae il codice, scrive il file e verifica con "
            "py_compile\n"
            "• in caso di errore: correction prompt (con la skill "
            "re-iniettata) fino a 3 tentativi\n"
            "Consigliata per modelli piccoli che sbagliano il formato "
            "dei tool.\nOverride del flag per-modello nel pannello "
            "Configurazione → Modelli LLM.")
        form.addRow("Generazione diretta (senza tool):", self.llm_no_tools)

        # 🆕 Conoscenza modelli: consigli per questo attore + download ⬇
        self._add_knowledge_row(form, self.llm_model, "llm")

        reset_llm = QPushButton("↺ Ripristina valori predefiniti")
        reset_llm.setToolTip(
            "Reimposta temperature, num_ctx e num_predict della sezione "
            "Worker ai valori predefiniti del sistema.")
        reset_llm.clicked.connect(self._reset_llm_params)
        form.addRow("", reset_llm)

        return box

    def _build_models_direct_section(self) -> QGroupBox:
        """🆕 Flag 'Modalità diretta (senza tool)' per SINGOLO modello worker.

        Scrive no_tools in CONFIG/config.toml [models.worker_*]. È il
        livello per-modello: il checkbox dell'attore LLM (sopra) è il
        master override che vince su questi.
        """
        box = QGroupBox("🧩 Modalità diretta per modello (worker)")
        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)

        tip = (
            "Per modello: se spuntato, SOLO quel worker usa la generazione\n"
            "diretta (skill + verifica host) invece del loop ReAct JSON.\n"
            "Il flag dell'attore LLM (sezione sopra) vale per TUTTI i\n"
            "worker e vince su questi.")
        self.mf_no_tools = QCheckBox()
        self.mf_no_tools.setToolTip(tip)
        form.addRow("Worker Coder (task di codice):", self.mf_no_tools)

        self.mg_no_tools = QCheckBox()
        self.mg_no_tools.setToolTip(tip)
        form.addRow("Worker General (task generici):", self.mg_no_tools)

        return box

    # ── Conoscenza modelli: consigli + download ──────────────────────
    def _add_knowledge_row(self, form: QFormLayout,
                           model_combo: QComboBox, actor_key: str) -> None:
        """🆕 Riga 'Consigliati (conoscenza)' per una sezione attore.

        Combo con i modelli consigliati da CONFIG/model_knowledge.json
        (✓ = installato, ⬇ = da scaricare) + pulsante di download
        (``ollama pull`` in background, progresso nel log del pannello).
        Scegliere un consiglio imposta anche il combo Modello dell'attore.
        """
        combo = QComboBox()
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(combo, stretch=1)
        btn = QPushButton("⬇ Scarica")
        btn.setToolTip(
            "Scarica il modello consigliato con 'ollama pull'.\n"
            "Il progresso appare nel log in fondo al pannello.")
        btn.clicked.connect(lambda: self._start_pull(actor_key))
        row.addWidget(btn)
        wrap = QWidget()
        wrap.setLayout(row)
        form.addRow("Consigliati (conoscenza):", wrap)

        combo.currentIndexChanged.connect(
            lambda _i, mc=model_combo, ak=actor_key:
            self._on_suggestion_picked(mc, ak))
        # activated scatta anche quando l'utente conferma l'indice già
        # corrente (currentIndexChanged non cambia → nessun segnale)
        combo.activated.connect(
            lambda _i, mc=model_combo, ak=actor_key:
            self._on_suggestion_picked(mc, ak))
        self._knowledge[actor_key] = {
            "combo": combo, "btn": btn, "model_combo": model_combo,
        }

    def _reload_knowledge(self) -> None:
        """Ricarica i consigli per ogni attore (installazione reale)."""
        installed = _mk.installed_names()
        for actor_key, info in self._knowledge.items():
            combo = info["combo"]
            combo.blockSignals(True)
            combo.clear()
            if actor_key == "_all":
                # Pseudo-attore: TUTTI i modelli conosciti non installati —
                # scaricabili (⬇) e cloud (🌍: si usano via API, non pull).
                for entry in _mk.absent_entries(installed)[:12]:
                    icon = _mk.place_icon(entry, installed)
                    tag = _mk.tag_for(entry)
                    tail = f" · {tag}" if tag else ""
                    combo.addItem(
                        f"{icon} {entry.get('nome', '?')} — "
                        f"{entry.get('categoria', '')} · "
                        f"{entry.get('utilizzo', '')}{tail}",
                        entry.get("nome", ""))
                box = getattr(self, "_missing_box", None)
                if box is not None:
                    box.setVisible(combo.count() > 0)
            else:
                for entry in _mk.suggest_for_actor(actor_key, installed):
                    combo.addItem(_mk.suggestion_label(entry, installed),
                                  entry.get("nome", ""))
            combo.blockSignals(False)
            self._update_pull_btn(actor_key)

    def _build_missing_models_section(self) -> QGroupBox:
        """🆕 Tutti gli altri modelli della conoscenza non ancora installati.

        Copre il caso "lo voglio scaricare io": qualsiasi voce della
        categorizzazione mancante (sicurezza, sysadmin, visione, …) è
        scaricabile con lo stesso meccanismo degli attori.
        """
        box = QGroupBox("🌐 Altri modelli della conoscenza (non installati)")
        form = QFormLayout(box)
        form.setSpacing(10)
        form.setContentsMargins(14, 14, 14, 14)
        combo = QComboBox()
        combo.setToolTip(
            "Modelli presenti nella conoscenza (CONFIG/model_knowledge.json)\n"
            "non ancora installati: ⬇ scaricabili con ollama pull,\n"
            "🌍 cloud (si usano via API, non scaricabili). Seleziona e premi\n"
            "Scarica: il download usa 'ollama pull' con progresso qui sotto.")
        btn = QPushButton("⬇ Scarica")
        btn.clicked.connect(lambda: self._start_pull("_all"))
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(combo, stretch=1)
        row.addWidget(btn)
        wrap = QWidget()
        wrap.setLayout(row)
        form.addRow("Da scaricare:", wrap)
        combo.currentIndexChanged.connect(
            lambda _i: self._update_pull_btn("_all"))
        self._knowledge["_all"] = {"combo": combo, "btn": btn,
                                   "model_combo": None}
        self._missing_box = box
        return box

    def _update_pull_btn(self, actor_key: str) -> None:
        """Abilita ⬇ solo per modelli mancanti e scaricabili (non Cloud)."""
        info = self._knowledge.get(actor_key)
        if not info:
            return
        combo, btn = info["combo"], info["btn"]
        name = combo.currentData()
        entry = _mk.entry_for(name) if name else None
        can = bool(entry) and _mk.installable(entry) \
            and not _mk.is_installed(name) and self._pull_worker is None
        btn.setEnabled(can)
        if entry is None:
            return
        if entry.get("vram_ok") == "Cloud":
            btn.setToolTip("Modello Cloud: si usa via API, NON si scarica.")
        elif _mk.is_installed(name):
            btn.setToolTip("Già installato: selezionalo dal combo Modello.")

    def _on_suggestion_picked(self, model_combo: QComboBox,
                              actor_key: str) -> None:
        """Il consiglio scelto diventa anche il modello dell'attore."""
        combo = self._knowledge.get(actor_key, {}).get("combo")
        name = combo.currentData() if combo else None
        if name:
            _set_combo_text(model_combo, name)
        self._update_pull_btn(actor_key)

    def _start_pull(self, actor_key: str) -> None:
        """Avvia ollama pull per il consiglio selezionato (uno per volta)."""
        import time as _t
        if self._pull_worker is not None:
            self.actors_log.appendPlainText(
                f"[{_t.strftime('%H:%M:%S')}] Download già in corso: "
                f"attendere il termine.")
            return
        info = self._knowledge.get(actor_key)
        if not info:
            return
        name = info["combo"].currentData()
        if not name:
            return
        self._pull_actor = actor_key
        self._pull_worker = ModelPullWorker(name)
        self._pull_worker.progress.connect(self.actors_log.appendPlainText)
        self._pull_worker.finished_ok.connect(self._on_pull_done)
        self._pull_worker.failed.connect(self._on_pull_failed)
        self._pull_worker.start()
        self.actors_log.appendPlainText(
            f"[{_t.strftime('%H:%M:%S')}] ⬇ Download avviato: {name}")
        self._update_pull_btn(actor_key)  # disabilita (worker attivo)

    def _on_pull_done(self, model_name: object) -> None:
        import time as _t
        self.actors_log.appendPlainText(
            f"[{_t.strftime('%H:%M:%S')}] ✓ {model_name} scaricato e "
            f"disponibile in Ollama.")
        self._pull_worker = None
        self._pull_actor = None
        self._refresh_installed_models()
        self._reload_knowledge()

    def _on_pull_failed(self, err: str) -> None:
        import time as _t
        self.actors_log.appendPlainText(
            f"[{_t.strftime('%H:%M:%S')}] ✗ Download fallito: {err}")
        self._pull_worker = None
        self._pull_actor = None
        self._reload_knowledge()

    def _refresh_installed_models(self) -> None:
        """Riempie i combo Modello con i modelli ora installati, mantenendo
        la selezione corrente."""
        installed = _mk.installed_names() or OLLAMA_MODELS
        for combo in (self.llm_model, self.dec_model):
            current = combo_current_model(combo)
            fill_model_combo(combo, installed)
            _set_combo_text(combo, current)

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
        fill_model_combo(self.dec_model, ollama_list_models() or OLLAMA_MODELS)
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

        # 🆕 Conoscenza modelli: consigli per questo attore + download ⬇
        self._add_knowledge_row(form, self.dec_model, "decision_model")

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
        # 🆕 Generazione diretta (fallback a False per actors.json vecchi)
        self.llm_no_tools.setChecked(bool(a["llm"].get("no_tools", False)))
        # 🆕 Flag per-modello da CONFIG/config.toml [models.worker_*]
        try:
            from GUI.gui_backend import load_config
            models = load_config().get("models", {})
            self.mf_no_tools.setChecked(bool(
                models.get("worker_coder", {}).get("no_tools", False)))
            self.mg_no_tools.setChecked(bool(
                models.get("worker_general", {}).get("no_tools", False)))
        except Exception:
            pass
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
        # 🆕 Consigli dalla conoscenza modelli + stato pulsanti ⬇
        self._reload_knowledge()

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
            current_model = combo_current_model(self.llm_model)
            # Se il modello attuale è uno dei default di un altro peso,
            # sostituiscilo con il default del nuovo peso
            for w in ACTOR_WEIGHTS:
                if current_model == weight_default_model("llm", w):
                    _set_combo_text(self.llm_model, weight_default_model("llm", weight))
                    return
            # Se l'utente aveva un modello custom, non toccare — solo hint
        elif actor == "decision_model":
            current_model = combo_current_model(self.dec_model)
            for w in ACTOR_WEIGHTS:
                if current_model == weight_default_model("decision_model", w):
                    _set_combo_text(self.dec_model, weight_default_model("decision_model", weight))
                    return

    def _on_save(self):
        a = {
            "llm": {
                "model": combo_current_model(self.llm_model),
                "weight": self.llm_weight.currentData(),
                "temperature": self.llm_temp.value(),
                "num_ctx": self.llm_ctx.value(),
                "num_predict": self.llm_predict.value(),
                "no_tools": self.llm_no_tools.isChecked(),
            },
            "decision_model": {
                "model": combo_current_model(self.dec_model),
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
        # 🆕 Persist anche i flag no_tools per-modello in CONFIG/config.toml
        cfg_saved = False
        try:
            import shutil
            import tomli_w
            from GUI.gui_backend import load_config
            cfg = load_config()
            models = cfg.setdefault("models", {})
            models.setdefault("worker_coder", {})["no_tools"] = \
                self.mf_no_tools.isChecked()
            models.setdefault("worker_general", {})["no_tools"] = \
                self.mg_no_tools.isChecked()
            path = "CONFIG/config.toml"
            try:
                shutil.copy2(path, path + ".bak")
            except Exception:
                pass
            with open(path, "wb") as f:
                tomli_w.dump(cfg, f)
            cfg_saved = True
        except Exception as e:
            self.actors_log.appendPlainText(
                f"[{_t.strftime('%H:%M:%S')}] ATTENZIONE: flag per-modello "
                f"non salvati in config.toml: {e}")
        if ok:
            self.actors_log.appendPlainText(
                f"[{_t.strftime('%H:%M:%S')}] Configurazione salvata OK "
                f"(LLM: {a['llm']['model']}, Decision: {a['decision_model']['model']}"
                + (", flag per-modello in config.toml OK" if cfg_saved
                   else ", flag per-modello NON salvati") + ")"
            )
            QMessageBox.information(
                self, "Salvato",
                "Configurazione attori salvata in CONFIG/actors.json.\n"
                + ("Flag per-modello salvati in CONFIG/config.toml.\n\n"
                   if cfg_saved else "\n")
                + "Riavvia l'orchestratore per applicare le modifiche."
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
