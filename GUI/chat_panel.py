"""
GUI/chat_panel.py — Pannello Chat per testare i modelli (trasparente e veloce).

Permette di inviare un prompt a un modello Ollama e vedere la risposta,
con trasparenza: modello usato, prompt inviato, risposta ricevuta, tempi.

I nomi nel combo seguono la stessa impostazione del pannello Modelli:
icona di collocazione (📌 locale / 🌍 cloud / ⬇ scaricabile), tag di
capacità (💻 coding, 🧠 ragionamento, …) e nota d'uso tra parentesi.
Il nome REALE del modello è salvato in ``currentData``.
"""

import json
import subprocess
import time
import urllib.error
import urllib.request

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)


def _list_ollama_models() -> list[str]:
    """Restituisce i modelli installati via 'ollama list'."""
    try:
        r = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return []
        models = []
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []


def _model_tooltip(name: str) -> str:
    """Tooltip con collocazione, capacità, VRAM e uso del modello."""
    try:
        from CORE import model_knowledge as _mk
        entry = _mk.entry_for(name)
        if not entry:
            icon = "🌍" if _mk.is_cloud_name(name) else "📌"
            where = "cloud" if icon == "🌍" else "locale"
            return f"{icon} {where} · fuori catalogo"
        parts = [
            f"{_mk.place_icon(entry)} "
            f"{'cloud' if entry.get('vram_ok') == 'Cloud' else 'locale'}",
        ]
        tag = _mk.tag_for(entry)
        if tag:
            parts.append(tag)
        vram = entry.get("vram_ok")
        if vram == "Cloud":
            parts.append("☁ cloud (API)")
        elif vram is True:
            parts.append("✅ entro 4GB")
        if entry.get("utilizzo"):
            parts.append(f"uso: {entry['utilizzo']}")
        return " · ".join(parts)
    except Exception:
        return name


class _ChatWorker(QThread):
    """Thread per la chiamata Ollama (non blocca la GUI)."""
    finished = pyqtSignal(str, float)  # (response, elapsed_sec)
    error = pyqtSignal(str)

    def __init__(self, model: str, prompt: str, system: str = ""):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.system = system

    def run(self):
        t0 = time.time()
        try:
            messages = []
            if self.system:
                messages.append({"role": "system", "content": self.system})
            messages.append({"role": "user", "content": self.prompt})
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body.get("message", {}).get("content", "").strip()
            elapsed = time.time() - t0
            self.finished.emit(content, elapsed)
        except urllib.error.HTTPError as e:
            # Mostra il messaggio del server (es. 402 crediti, 410 ritirato).
            try:
                raw = e.read().decode("utf-8", "replace")
                detail = json.loads(raw).get("error", raw)
            except Exception:
                detail = str(e)
            self.error.emit(f"HTTP {e.code}: {detail}")
        except Exception as e:
            self.error.emit(str(e))


class ChatPanel(QWidget):
    """Pannello Chat: testa i modelli in modo trasparente e veloce."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_panel")
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Riga modello + azioni
        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        model_row.addWidget(QLabel("Modello:"))
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self._update_model_info)
        model_row.addWidget(self.model_combo, stretch=1)
        self.clear_btn = QPushButton("🧹 Pulisci")
        self.clear_btn.clicked.connect(self._clear)
        model_row.addWidget(self.clear_btn)
        outer.addLayout(model_row)

        # Riga info modello (stessa impostazione del pannello Modelli)
        self.model_info = QLabel("")
        self.model_info.setObjectName("chat_model_info")
        self.model_info.setWordWrap(True)
        outer.addWidget(self.model_info)

        self._fill_models()

        # System prompt (opzionale)
        self.system_input = QLineEdit()
        self.system_input.setPlaceholderText("System prompt (opzionale)")
        outer.addWidget(self.system_input)

        # Area output (trasparente: mostra prompt + risposta + tempi)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("La conversazione apparirà qui...")
        outer.addWidget(self.output, stretch=1)

        # Riga input + invio
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(
            "Scrivi un prompt e premi Invia (o Enter)")
        self.input_field.returnPressed.connect(self._send)
        input_row.addWidget(self.input_field, stretch=1)
        self.send_btn = QPushButton("📤 Invia")
        self.send_btn.setObjectName("primary_btn")
        self.send_btn.clicked.connect(self._send)
        input_row.addWidget(self.send_btn)
        outer.addLayout(input_row)

    def _fill_models(self) -> None:
        """Popola il combo con etichette decorate (icone + tag), come Modelli."""
        self.model_combo.clear()
        try:
            from GUI.actors_panel import (
                OLLAMA_MODELS, sorted_model_choices)
        except Exception:
            models = _list_ollama_models()
            for name in models:
                self.model_combo.addItem(name, name)
            if not models:
                self.model_combo.addItem(
                    "(nessun modello — ollama list)", "")
            return
        models = _list_ollama_models() or OLLAMA_MODELS
        for label, name in sorted_model_choices(models):
            self.model_combo.addItem(label, name)
            idx = self.model_combo.count() - 1
            self.model_combo.setItemData(
                idx, _model_tooltip(name), Qt.ItemDataRole.ToolTipRole)
        if not models:
            self.model_combo.addItem("(nessun modello — ollama list)", "")
        self._update_model_info()

    def _update_model_info(self) -> None:
        """Mostra la riga informativa del modello selezionato."""
        name = self.model_combo.currentData()
        if not name:
            self.model_info.setText("")
            return
        self.model_info.setText(_model_tooltip(name))

    def _send(self):
        prompt = self.input_field.text().strip()
        if not prompt:
            return
        model = self.model_combo.currentData() or self.model_combo.currentText()
        if not model:
            self.output.append("⚠️ Nessun modello disponibile.")
            return
        label = self.model_combo.currentText()
        self.send_btn.setEnabled(False)
        self.input_field.clear()
        self.output.append(f"\n👤 [{label}] {prompt}")
        self.output.append("⏳ Generazione in corso...")

        self._worker = _ChatWorker(
            model, prompt, self.system_input.text().strip())
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, response: str, elapsed: float):
        self.send_btn.setEnabled(True)
        self.output.append(f"🤖 {response}")
        self.output.append(f"⏱️ {elapsed:.2f}s")
        self.output.append("─" * 40)

    def _on_error(self, err: str):
        self.send_btn.setEnabled(True)
        self.output.append(f"❌ Errore: {err}")

    def _clear(self):
        self.output.clear()

    def refresh_models(self) -> None:
        """Ricarica l'elenco modelli (utile dopo un 'ollama pull')."""
        self._fill_models()
