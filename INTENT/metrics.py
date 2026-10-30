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


# ====================================================================
# Architetture modelli noti (per stima KV cache precisa)
# ====================================================================

MODEL_ARCHITECTURES = {
    # Qwen2.5 family (head_dim = 128, GQA con kv_heads ridotti)
    "qwen2.5:0.5b": {"layers": 24, "kv_heads": 4, "head_dim": 64, "hidden": 896},
    "qwen2.5:1.5b": {"layers": 28, "kv_heads": 2, "head_dim": 128, "hidden": 1536},
    "qwen2.5:3b": {"layers": 36, "kv_heads": 2, "head_dim": 128, "hidden": 2048},
    "qwen2.5:7b": {"layers": 28, "kv_heads": 4, "head_dim": 128, "hidden": 3584},
    "qwen2.5-coder:1.5b": {"layers": 28, "kv_heads": 2, "head_dim": 128, "hidden": 1536},
    "qwen2.5-coder:3b": {"layers": 36, "kv_heads": 2, "head_dim": 128, "hidden": 2048},
    "qwen2.5-coder:7b": {"layers": 28, "kv_heads": 4, "head_dim": 128, "hidden": 3584},
    
    # Qwen3 family
    "qwen3:1.7b": {"layers": 28, "kv_heads": 4, "head_dim": 128, "hidden": 2048},
    "qwen3:4b": {"layers": 36, "kv_heads": 4, "head_dim": 128, "hidden": 2560},
    "qwen3:8b": {"layers": 36, "kv_heads": 8, "head_dim": 128, "hidden": 4096},
    
    # Qwen3.5 family (tev1 si basa su qwen3.5:4b)
    "tev1:4b": {"layers": 36, "kv_heads": 4, "head_dim": 128, "hidden": 2560},
    "qwen3.5:4b": {"layers": 36, "kv_heads": 4, "head_dim": 128, "hidden": 2560},
    
    # Llama3.2 family
    "llama3.2:1b": {"layers": 16, "kv_heads": 8, "head_dim": 64, "hidden": 2048},
    "llama3.2:3b": {"layers": 28, "kv_heads": 8, "head_dim": 128, "hidden": 3072},
    
    # Phi3 family
    "phi3:mini": {"layers": 32, "kv_heads": 32, "head_dim": 96, "hidden": 3072},
    "phi3:3.8b": {"layers": 32, "kv_heads": 32, "head_dim": 96, "hidden": 3072},
    
    # DeepSeek Coder (basato su Llama)
    "deepseek-coder:1.3b": {"layers": 22, "kv_heads": 2, "head_dim": 128, "hidden": 2048},
    "deepseek-coder:6.7b": {"layers": 32, "kv_heads": 32, "head_dim": 128, "hidden": 4096},
    
    # Mistral 7B
    "mistral:7b": {"layers": 32, "kv_heads": 8, "head_dim": 128, "hidden": 4096},
    
    # Codellama 7B
    "codellama:7b": {"layers": 32, "kv_heads": 32, "head_dim": 128, "hidden": 4096},
    
    # Llama2 Uncensored (7B)
    "llama2-uncensored:7b": {"layers": 32, "kv_heads": 32, "head_dim": 128, "hidden": 4096},
}


def get_model_arch(model_name: str) -> dict:
    """Ritorna architettura del modello, o stima se non noto."""
    name_lower = model_name.lower()
    
    if model_name in MODEL_ARCHITECTURES:
        return MODEL_ARCHITECTURES[model_name]
    
    for known_name, arch in MODEL_ARCHITECTURES.items():
        if known_name in name_lower or name_lower.startswith(known_name):
            return arch
    
    # Stima euristica da param size
    if "0.5b" in name_lower or "1b" in name_lower:
        return {"layers": 24, "kv_heads": 4, "head_dim": 64, "hidden": 1024}
    elif "1.5b" in name_lower:
        return {"layers": 28, "kv_heads": 2, "head_dim": 128, "hidden": 1536}
    elif "3b" in name_lower or "4b" in name_lower:
        return {"layers": 36, "kv_heads": 4, "head_dim": 128, "hidden": 2560}
    elif "7b" in name_lower or "8b" in name_lower:
        return {"layers": 32, "kv_heads": 8, "head_dim": 128, "hidden": 4096}
    elif "13b" in name_lower or "14b" in name_lower:
        return {"layers": 40, "kv_heads": 8, "head_dim": 128, "hidden": 5120}
    else:
        return {"layers": 32, "kv_heads": 8, "head_dim": 128, "hidden": 4096}


def estimate_kv_cache_mb(context_tokens: int, model_name: str = "") -> float:
    """Stima DINAMICA della KV cache in MB basata sull'architettura reale.
    
    Formula: 2 (K+V) × num_layers × num_kv_heads × head_dim × dtype_size × tokens
    
    Per modelli con GQA (Grouped Query Attention), num_kv_heads è ridotto
    rispetto agli attention heads (es. qwen2.5:7b ha 28 query heads ma solo 4 kv_heads).
    """
    if context_tokens <= 0:
        return 0.0
    
    arch = get_model_arch(model_name)
    num_layers = arch["layers"]
    num_kv_heads = arch["kv_heads"]
    head_dim = arch["head_dim"]
    
    # KV cache è fp16 = 2 bytes per scalare
    # 2 (K e V) × dtype_size (2 bytes per fp16)
    dtype_size = 2
    
    bytes_total = 2 * num_layers * num_kv_heads * head_dim * dtype_size * context_tokens
    return round(bytes_total / (1024 * 1024), 1)


def get_model_arch_info(model_name: str) -> dict:
    """Ritorna info complete sull'architettura per display."""
    arch = get_model_arch(model_name)
    kv_per_token = 2 * arch["layers"] * arch["kv_heads"] * arch["head_dim"] * 2
    return {
        **arch,
        "kv_per_token_bytes": kv_per_token,
        "kv_per_1k_tokens_mb": round(kv_per_token * 1000 / (1024 * 1024), 1),
        "is_known": model_name in MODEL_ARCHITECTURES,
    }


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
