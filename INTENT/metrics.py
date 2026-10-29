"""
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
