#!/usr/bin/env python3
"""
add_metrics.py — Aggiunge metriche token/sec + KV cache alla GUI.

Patch:
1. ollama_client.py: estrae metriche dalla response e le salva in state/last_metrics.json
2. ollama_metrics.py (nuovo): helper per leggere metriche + /api/ps
3. gui.py: aggiunge riga metriche al LiveActivityPanel (se presente)
"""
import re
import shutil
import json
from pathlib import Path

ORCH_FILE = Path("ollama_client.py")
ORCH_BACKUP = Path("ollama_client.py.bak.metrics")
GUI_FILE = Path("gui.py")
GUI_BACKUP = Path("gui.py.bak.metrics")
METRICS_HELPER = Path("ollama_metrics.py")


# ====================================================================
# 1. Patch ollama_client.py: estrai e salva metriche
# ====================================================================

OLLAMA_OLD = '''        response = self._post("/api/chat", payload)
        return response.get("message", {}).get("content", "").strip()'''

OLLAMA_NEW = '''        response = self._post("/api/chat", payload)
        content = response.get("message", {}).get("content", "").strip()
        self._save_call_metrics(model_key, model_name, response)
        return content

    def _save_call_metrics(self, model_key: str, model_name: str,
                           response: dict) -> None:
        """Estrae metriche dalla response Ollama e le salva su file.
        Ollama include nei campi finali: eval_count, eval_duration,
        prompt_eval_count, load_duration, total_duration.
        """
        try:
            import time as _time
            metrics = {
                "timestamp": _time.time(),
                "model": model_name,
                "model_key": model_key,
                "tokens_in": response.get("prompt_eval_count", 0),
                "tokens_out": response.get("eval_count", 0),
                "ttft_ms": (
                    response.get("load_duration", 0)
                    + response.get("prompt_eval_duration", 0)
                ) / 1e6,
                "total_ms": response.get("total_duration", 0) / 1e6,
                "tokens_per_sec": 0.0,
                "context_used": 0,
            }
            eval_dur_s = response.get("eval_duration", 0) / 1e9
            if eval_dur_s > 0 and metrics["tokens_out"] > 0:
                metrics["tokens_per_sec"] = round(
                    metrics["tokens_out"] / eval_dur_s, 1
                )
            metrics["context_used"] = (
                metrics["tokens_in"] + metrics["tokens_out"]
            )
            mfile = Path("state/last_metrics.json")
            mfile.parent.mkdir(parents=True, exist_ok=True)
            mfile.write_text(json.dumps(metrics, indent=2))
        except Exception as e:
            self.log.debug(f"metrics save failed: {e}")'''


# ====================================================================
# 2. Crea ollama_metrics.py (helper per GUI)
# ====================================================================

METRICS_HELPER_CONTENT = '''"""
ollama_metrics.py — Helper per leggere metriche Ollama dalla GUI.

Fonti:
- state/last_metrics.json (scritto da ollama_client.py dopo ogni call)
- /api/ps di Ollama (modelli caricati con size_vram)
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Optional

METRICS_FILE = Path("state/last_metrics.json")


def get_last_call_metrics() -> Optional[dict]:
    """Legge le metriche dell'ultima call al modello."""
    if not METRICS_FILE.exists():
        return None
    try:
        return json.loads(METRICS_FILE.read_text())
    except Exception:
        return None


def get_loaded_models(ollama_host: str = "http://localhost:11434") -> list:
    """Query /api/ps per i modelli attualmente caricati in RAM/VRAM."""
    try:
        host = ollama_host.rstrip("/")
        data = json.loads(
            urllib.request.urlopen(f"{host}/api/ps", timeout=3).read()
        )
        return data.get("models", [])
    except Exception:
        return []


def estimate_kv_cache_mb(context_tokens: int, model_name: str = "") -> float:
    """Stima approssimativa della KV cache in MB basata sul contesto.

    Formula: 2 * n_layers * n_kv_heads * head_dim * 2 bytes (fp16) * tokens

    Stime per modelli comuni (Qwen2.5, Llama, ecc.):
    - 0.5B-1.5B: ~4-8 KB/token
    - 3B-7B: ~30-60 KB/token
    - 13B+: ~80-150 KB/token
    """
    name_lower = model_name.lower()
    # Stima bytes per token in base alla dimensione del modello
    if any(s in name_lower for s in ["0.5b", "1b", "1.5b"]):
        bytes_per_token = 6 * 1024
    elif any(s in name_lower for s in ["3b", "4b", "teven", "tev1"]):
        bytes_per_token = 25 * 1024
    elif any(s in name_lower for s in ["7b", "8b", "llama3", "qwen2.5"]):
        bytes_per_token = 56 * 1024
    elif any(s in name_lower for s in ["13b", "14b", "phi3"]):
        bytes_per_token = 90 * 1024
    else:
        bytes_per_token = 50 * 1024  # default conservative
    return round(context_tokens * bytes_per_token / (1024 * 1024), 1)


def format_metrics_line() -> str:
    """Restituisce una stringa formattata per la GUI."""
    m = get_last_call_metrics()
    if not m:
        return "Nessuna metrica disponibile"

    tps = m.get("tokens_per_sec", 0)
    tok_in = m.get("tokens_in", 0)
    tok_out = m.get("tokens_out", 0)
    ttft = m.get("ttft_ms", 0)
    ctx = m.get("context_used", 0)
    model = m.get("model", "?")

    kv_mb = estimate_kv_cache_mb(ctx, model)

    return (
        f"🔢 {tps} tok/s | "
        f"📥 {tok_in} tok | 📤 {tok_out} tok | "
        f"⏱ TTFT {ttft:.0f}ms | "
        f"💾 KV~{kv_mb}MB ({ctx} ctx)"
    )


def format_vram_line(ollama_host: str = "http://localhost:11434") -> str:
    """Restituisce info VRAM dai modelli caricati."""
    models = get_loaded_models(ollama_host)
    if not models:
        return "○ Nessun modello caricato"
    parts = []
    for m in models:
        name = m.get("name", "?")
        size_vram = m.get("size_vram", 0)
        size_total = m.get("size", 0)
        vram_gb = size_vram / 1e9
        total_gb = size_total / 1e9
        parts.append(f"{name}: {vram_gb:.1f}GB VRAM / {total_gb:.1f}GB total")
    return " | ".join(parts)
'''


# ====================================================================
# 3. Patch gui.py: aggiungi metriche al LiveActivityPanel
# ====================================================================

# Trova il punto dove aggiungere la riga metriche nel LiveActivityPanel
GUI_SEARCH = '''        self.thought_label.setWordWrap(True)
        gl.addWidget(self.thought_label)

        layout.addWidget(group)'''

GUI_REPLACE = '''        self.thought_label.setWordWrap(True)
        gl.addWidget(self.thought_label)

        # 🆕 Riga metriche (token/sec, KV cache, VRAM)
        self.metrics_label = QLabel("📊 Metriche: in attesa prima call...")
        self.metrics_label.setStyleSheet(
            "color: #ffb86c; font-family: monospace; font-size: 9pt; "
            "padding: 2px 0; background: #2a2a2a; border-radius: 2px;"
        )
        self.metrics_label.setWordWrap(True)
        gl.addWidget(self.metrics_label)

        # 🆕 Riga VRAM (modelli caricati)
        self.vram_label = QLabel("💾 VRAM: ...")
        self.vram_label.setStyleSheet(
            "color: #50fa7b; font-family: monospace; font-size: 9pt; "
            "padding: 2px 0;"
        )
        self.vram_label.setWordWrap(True)
        gl.addWidget(self.vram_label)

        layout.addWidget(group)'''

# Aggiorna _refresh per popolare le metriche
GUI_REFRESH_SEARCH = '''        # Avvia spinner
        if not self.spinner_timer.isActive():
            self.spinner_timer.start(120)'''

GUI_REFRESH_REPLACE = '''        # 🆕 Aggiorna metriche
        try:
            from ollama_metrics import format_metrics_line, format_vram_line
            self.metrics_label.setText(f"📊 {format_metrics_line()}")
            self.vram_label.setText(f"💾 {format_vram_line()}")
        except ImportError:
            pass

        # Avvia spinner
        if not self.spinner_timer.isActive():
            self.spinner_timer.start(120)'''

# Aggiorna _show_idle per pulire metriche
GUI_IDLE_SEARCH = '''    def _show_idle(self) -> None:
        self._start_time = None
        self._last_task_id = None
        self.status_label.setText("○ In attesa")'''

GUI_IDLE_REPLACE = '''    def _show_idle(self) -> None:
        self._start_time = None
        self._last_task_id = None
        # 🆕 Aggiorna comunque metriche anche quando idle
        try:
            from ollama_metrics import format_metrics_line, format_vram_line
            if hasattr(self, 'metrics_label'):
                self.metrics_label.setText(f"📊 {format_metrics_line()}")
            if hasattr(self, 'vram_label'):
                self.vram_label.setText(f"💾 {format_vram_line()}")
        except ImportError:
            pass
        self.status_label.setText("○ In attesa")'''


# ====================================================================
# Esecuzione patch
# ====================================================================

def patch_ollama_client() -> bool:
    if not ORCH_FILE.exists():
        print(f"❌ {ORCH_FILE} non trovato")
        return False

    content = ORCH_FILE.read_text()

    if "_save_call_metrics" in content:
        print("ℹ  Patch ollama_client.py già applicata, skip")
        return True

    if OLLAMA_OLD not in content:
        print("❌ Pattern non trovato in ollama_client.py")
        print("   Cerca: response = self._post('/api/chat', payload)")
        return False

    if not ORCH_BACKUP.exists():
        shutil.copy2(ORCH_FILE, ORCH_BACKUP)
        print(f"✓ Backup: {ORCH_BACKUP}")

    content = content.replace(OLLAMA_OLD, OLLAMA_NEW, 1)
    ORCH_FILE.write_text(content)
    print("✓ ollama_client.py patchato: metriche salvate in state/last_metrics.json")
    return True


def create_metrics_helper() -> bool:
    if METRICS_HELPER.exists() and "_save_call_metrics" not in METRICS_HELPER.read_text():
        print(f"ℹ  {METRICS_HELPER} già esistente, skip")
        return True
    METRICS_HELPER.write_text(METRICS_HELPER_CONTENT)
    print(f"✓ Creato {METRICS_HELPER}")
    return True


def patch_gui() -> bool:
    if not GUI_FILE.exists():
        print(f"❌ {GUI_FILE} non trovato")
        return False

    content = GUI_FILE.read_text()
    modified = False

    if "class LiveActivityPanel" not in content:
        print("⚠  LiveActivityPanel non trovato in gui.py")
        print("   Esegui prima: python add_live_activity.py")
        print("   Skip patch metriche GUI (ollama_client.py e helper comunque patchati)")
        return False

    if not GUI_BACKUP.exists():
        shutil.copy2(GUI_FILE, GUI_BACKUP)
        print(f"✓ Backup: {GUI_BACKUP}")

    # 1. Aggiungi righe metriche alla UI
    if "self.metrics_label" in content:
        print("ℹ  Riga metriche già presente, skip UI")
    elif GUI_SEARCH in content:
        content = content.replace(GUI_SEARCH, GUI_REPLACE, 1)
        modified = True
        print("✓ Aggiunta riga metriche + VRAM al LiveActivityPanel")
    else:
        print("⚠  Punto inserimento UI non trovato (probabile versione diversa)")

    # 2. Aggiorna _refresh
    if "format_metrics_line" in content:
        print("ℹ  _refresh già patchato, skip")
    elif GUI_REFRESH_SEARCH in content:
        content = content.replace(GUI_REFRESH_SEARCH, GUI_REFRESH_REPLACE, 1)
        modified = True
        print("✓ _refresh patchato per popolare metriche")
    else:
        print("⚠  Punto _refresh non trovato")

    # 3. Aggiorna _show_idle
    if "Aggiorna comunque metriche" in content:
        print("ℹ  _show_idle già patchato, skip")
    elif GUI_IDLE_SEARCH in content:
        content = content.replace(GUI_IDLE_SEARCH, GUI_IDLE_REPLACE, 1)
        modified = True
        print("✓ _show_idle patchato per aggiornare metriche anche idle")
    else:
        print("⚠  Punto _show_idle non trovato")

    if modified:
        GUI_FILE.write_text(content)
        print(f"✓ gui.py aggiornato")
    return True


def main():
    print("=" * 60)
    print("PATCH: Metriche token/sec + KV cache")
    print("=" * 60)
    print()

    ok1 = patch_ollama_client()
    print()
    ok2 = create_metrics_helper()
    print()
    ok3 = patch_gui()

    print()
    print("=" * 60)
    if ok1 and ok2:
        print("✓ PATCH APPLICATE")
        print()
        print("⚠  IMPORTANTE: installa rapidfuzz nel venv:")
        print("   source .venv/bin/activate && pip install rapidfuzz && deactivate")
        print()
        print("Per testare:")
        print("  1. python -c \"import gui; import ollama_client; print('OK')\"")
        print("  2. ./avvia.sh")
        print("  3. Aggiungi un task e guarda le metriche in Live Activity")
        print()
        print("Per ripristinare:")
        print(f"  cp {ORCH_BACKUP} {ORCH_FILE}")
        print(f"  cp {GUI_BACKUP} {GUI_FILE}")
    else:
        print("⚠  Alcune patch non applicate. Leggi sopra.")
    print("=" * 60)


if __name__ == "__main__":
    main()
