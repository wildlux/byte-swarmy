"""
GUI/hf_weights_worker.py — Worker thread per download pesi HF e weight-space harness.

Estratto da GUI/settings_panel.py per ridurre il monolite.

Contiene:
- WeightsDownloadWorker: scarica pesi GGUF da Hugging Face e li registra su Ollama
- WeightspaceProveWorker: esegue l'harness di weight-space programming
"""

from __future__ import annotations

import time as _t

from PyQt6.QtCore import pyqtSignal as Signal

from CORE.gui_worker import BaseWorker


class WeightsDownloadWorker(BaseWorker):
    """Scarica i pesi GGUF da un link Hugging Face e li registra su Ollama.

    Emette: progress (messaggi), percent (0..100 download), found
    (descrizione file scelto), finished_ok (nome modello ollama), failed.
    """

    percent = Signal(int)
    found = Signal(str)
    finished_ok = Signal(dict)

    def __init__(self, link: str, force_filename: str = "", parent=None):
        super().__init__(parent)
        self.link = link
        self.force_filename = force_filename

    def _execute(self):
        from CORE import hf_weights as hw

        self.progress.emit(f"🔗 Analisi del link: {self.link[:120]}")
        info = hw.parse_hf_link(self.link)
        if self.force_filename:
            info["filename"] = self.force_filename
        files = hw.list_repo_files(info["repo_id"], info["revision"] or "main")
        resolved = hw.resolve_download(info, files=files)
        size = resolved.get("size", 0)
        self.found.emit(f"📦 Pesi scelti: {resolved['filename']} ({hw.human_size(size)})")

        def _cb(stage, val):
            if self.is_cancelled():
                return
            if stage == "download" and isinstance(val, float) and 0 <= val <= 1:
                self.percent.emit(int(val * 100))
            elif stage == "bytes":
                self.progress.emit(f"⬇ scaricati {hw.human_size(val)}…")

        gguf = hw.download_file(
            resolved["url"], hw.WEIGHT_SPACE_DIR,
            progress_cb=_cb, should_cancel=lambda: self.is_cancelled(),
        )
        if self.is_cancelled():
            self.failed.emit("Download annullato.")
            return
        self.progress.emit("🧬 Letta l'intestazione dei pesi (GGUF header)…")
        meta = hw.gguf_meta(gguf)
        name = hw.sanitized_model_name(info["repo_id"], resolved["filename"])
        self.progress.emit(f"⚙️ Registrazione su Ollama come '{name}'…")
        if self.is_cancelled():
            self.failed.emit("Annullato prima della registrazione.")
            return
        reg = hw.register_with_ollama(gguf, name)
        entry = {
            "name": name, "repo_id": info["repo_id"],
            "revision": info["revision"], "filename": resolved["filename"],
            "size": size, "gguf": reg["gguf"], "modelfile": reg["modelfile"],
            "ts": _t.strftime("%Y-%m-%dT%H:%M:%S"), "meta": meta,
        }
        hw.add_to_registry(entry)
        self.progress.emit(f"✓ Modello pesi pronto: {name}")
        self.finished_ok.emit(entry)


class WeightspaceProveWorker(BaseWorker):
    """Esegue l'harness di weight-space programming sul modello scaricato.

    Non blocca la GUI: emette progress (problema in corso), finished_ok
    (report dict), failed (messaggio).
    """

    finished_ok = Signal(dict)

    def __init__(self, model_name: str, parent=None):
        super().__init__(parent)
        self.model_name = model_name

    def _execute(self):
        from CORE import weight_space_harness as h
        self.progress.emit("🧪 Valutazione dei pesi su problemi da programmatore…")
        report = h.run_harness(
            self.model_name,
            progress_cb=lambda msg: (self.progress.emit(msg)),
            should_cancel=lambda: self.is_cancelled(),
        )
        self.finished_ok.emit(report)
