"""
GUI/chat_panel.py — Pannello Chat per testare i modelli (trasparente e veloce).

Sorgenti:
- **Ollama** (locale/cloud): stessi nomi decorati del pannello Modelli
  (📌 locale / 🌍 cloud / ⬇ scaricabile, tag 💻 coding, 🧠 ragionamento…).
- **Provider cloud gratuiti** (Groq / Google AI Studio / OpenRouter): API
  OpenAI-compatibile, solo per test manuali. La chiave si salva con 🔑 in
  ``state/cloud_api.json`` (0600, gitignored).
"""

import json
import subprocess
import time
import urllib.error
import urllib.request

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from CORE import cloud_client as cc

SOURCE_OLLAMA = "ollama"


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


def _source_choices() -> list[tuple[str, str]]:
    out = [("🖥️ Ollama (locale/cloud)", SOURCE_OLLAMA)]
    for key, info in cc.PROVIDERS.items():
        out.append((f"{info['icon']} {info['label']} (gratis)", key))
    return out


class _ChatWorker(QThread):
    """Thread per la chiamata Ollama (non blocca la GUI)."""
    finished = pyqtSignal(str, float)
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
            self.finished.emit(content, time.time() - t0)
        except urllib.error.HTTPError as e:
            self.error.emit(_http_error_text(e))
        except Exception as e:
            self.error.emit(str(e))


class _CloudChatWorker(QThread):
    """Thread per la chiamata a un provider cloud gratuito."""
    finished = pyqtSignal(str, float)
    error = pyqtSignal(str)

    def __init__(self, provider: str, model: str, prompt: str,
                 system: str = ""):
        super().__init__()
        self.provider = provider
        self.model = model
        self.prompt = prompt
        self.system = system

    def run(self):
        try:
            messages = []
            if self.system:
                messages.append({"role": "system", "content": self.system})
            messages.append({"role": "user", "content": self.prompt})
            res = cc.chat(self.provider, self.model, messages)
            self.finished.emit(res["content"], res["elapsed"])
        except Exception as e:
            self.error.emit(str(e))


class _ModelsWorker(QThread):
    """Carica in background l'elenco modelli di un provider cloud."""
    done = pyqtSignal(str, list)
    failed = pyqtSignal(str, str)

    def __init__(self, provider: str):
        super().__init__()
        self.provider = provider

    def run(self):
        try:
            self.done.emit(self.provider, cc.list_models(self.provider))
        except Exception as e:
            self.failed.emit(self.provider, str(e))


def _http_error_text(e: urllib.error.HTTPError) -> str:
    """Estrae il messaggio 'error' dal body JSON di Ollama."""
    try:
        raw = e.read().decode("utf-8", "replace")
        detail = json.loads(raw).get("error", raw)
    except Exception:
        detail = str(e)
    return f"HTTP {e.code}: {detail}"


class ChatPanel(QWidget):
    """Pannello Chat: testa modelli Ollama o provider cloud gratuiti."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_panel")
        self._worker = None
        self._models_worker = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        self._build_source_row(outer)
        self._build_model_row(outer)
        self.model_info = QLabel("")
        self.model_info.setObjectName("chat_model_info")
        self.model_info.setWordWrap(True)
        outer.addWidget(self.model_info)
        self._build_chat_area(outer)
        self._reload_models()

    def _build_source_row(self, outer):
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Sorgente:"))
        self.source_combo = QComboBox()
        for label, key in _source_choices():
            self.source_combo.addItem(label, key)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        row.addWidget(self.source_combo, stretch=1)
        self.key_btn = QPushButton("🔑 Chiave")
        self.key_btn.clicked.connect(self._set_key)
        row.addWidget(self.key_btn)
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setToolTip("Ricarica l'elenco modelli")
        self.refresh_btn.clicked.connect(self._reload_models)
        row.addWidget(self.refresh_btn)
        outer.addLayout(row)

    def _build_model_row(self, outer):
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Modello:"))
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self._update_model_info)
        row.addWidget(self.model_combo, stretch=1)
        self.clear_btn = QPushButton("🧹 Pulisci")
        self.clear_btn.clicked.connect(self._clear)
        row.addWidget(self.clear_btn)
        outer.addLayout(row)

    def _build_chat_area(self, outer):
        self.system_input = QLineEdit()
        self.system_input.setPlaceholderText("System prompt (opzionale)")
        outer.addWidget(self.system_input)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("La conversazione apparirà qui...")
        outer.addWidget(self.output, stretch=1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(
            "Scrivi un prompt e premi Invia (o Enter)")
        self.input_field.returnPressed.connect(self._send)
        row.addWidget(self.input_field, stretch=1)
        self.send_btn = QPushButton("📤 Invia")
        self.send_btn.setObjectName("primary_btn")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)
        outer.addLayout(row)

    # ── sorgente / modelli ───────────────────────────────────────────

    def _provider(self) -> str:
        return self.source_combo.currentData() or SOURCE_OLLAMA

    def _on_source_changed(self, _index: int) -> None:
        self.key_btn.setEnabled(self._provider() != SOURCE_OLLAMA)
        self._reload_models()

    def _reload_models(self) -> None:
        """Ricarica il combo modelli per la sorgente selezionata."""
        provider = self._provider()
        self.key_btn.setEnabled(provider != SOURCE_OLLAMA)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.blockSignals(False)
        if provider == SOURCE_OLLAMA:
            self._fill_ollama_models()
        elif not cc.has_api_key(provider):
            info = cc.provider_info(provider)
            self.model_combo.addItem(
                f"(serve chiave — ottienila su {info['signup']})", "")
        else:
            self.model_combo.addItem("⏳ carico modelli...", "")
            worker = _ModelsWorker(provider)
            worker.done.connect(self._on_models_loaded)
            worker.failed.connect(self._on_models_failed)
            self._models_worker = worker
            worker.start()
        self._update_model_info()

    def _fill_ollama_models(self) -> None:
        try:
            from GUI.actors_panel import OLLAMA_MODELS, sorted_model_choices
        except Exception:
            for name in _list_ollama_models():
                self.model_combo.addItem(name, name)
            return
        models = _list_ollama_models() or OLLAMA_MODELS
        for label, name in sorted_model_choices(models):
            self.model_combo.addItem(label, name)
            idx = self.model_combo.count() - 1
            self.model_combo.setItemData(
                idx, _model_tooltip(name), Qt.ItemDataRole.ToolTipRole)

    def _on_models_loaded(self, provider: str, models: list) -> None:
        if provider != self._provider():
            return  # risposta di una sorgente precedente
        self.model_combo.clear()
        for name in models:
            self.model_combo.addItem(name, name)
            idx = self.model_combo.count() - 1
            self.model_combo.setItemData(
                idx, f"{name}\ntier gratuito", Qt.ItemDataRole.ToolTipRole)
        default = cc.pick_default_model(provider, models)
        if default:
            pos = self.model_combo.findData(default)
            if pos >= 0:
                self.model_combo.setCurrentIndex(pos)
        self._update_model_info()

    def _on_models_failed(self, provider: str, err: str) -> None:
        if provider != self._provider():
            return
        self.model_combo.clear()
        self.model_combo.addItem("(errore — vedi sotto)", "")
        self.model_info.setText(f"❌ {err}")

    def _update_model_info(self) -> None:
        provider = self._provider()
        name = self.model_combo.currentData()
        if not name:
            self.model_info.setText("")
            return
        if provider == SOURCE_OLLAMA:
            self.model_info.setText(_model_tooltip(name))
            return
        info = cc.provider_info(provider)
        key_state = "chiave ok" if cc.has_api_key(provider) else "no chiave"
        self.model_info.setText(
            f"{info['icon']} {info['label']} · tier gratuito · "
            f"{key_state} · modello: {name}")

    def _set_key(self) -> None:
        provider = self._provider()
        if provider == SOURCE_OLLAMA:
            return
        info = cc.provider_info(provider)
        key, ok = QInputDialog.getText(
            self, f"Chiave API — {info['label']}",
            f"Incolla la chiave API (gratis da {info['signup']}):",
            QLineEdit.EchoMode.Password)
        if ok and key.strip():
            cc.save_api_key(provider, key.strip())
            self.output.append(
                f"🔑 Chiave salvata per {info['label']} "
                f"(state/cloud_api.json, 0600).")
            self._reload_models()

    # ── invio ────────────────────────────────────────────────────────

    def _send(self):
        prompt = self.input_field.text().strip()
        if not prompt:
            return
        provider = self._provider()
        model = self.model_combo.currentData()
        if not model:
            self.output.append("⚠️ Nessun modello disponibile.")
            return
        label = self.model_combo.currentText()
        self.send_btn.setEnabled(False)
        self.input_field.clear()
        self.output.append(f"\n👤 [{label}] {prompt}")
        self.output.append("⏳ Generazione in corso...")
        system = self.system_input.text().strip()
        if provider == SOURCE_OLLAMA:
            worker = _ChatWorker(model, prompt, system)
        else:
            worker = _CloudChatWorker(provider, model, prompt, system)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        self._worker = worker
        worker.start()

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
        self._reload_models()
