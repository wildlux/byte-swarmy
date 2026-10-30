"""
model_selector.py — Auto-selezione intelligente dei modelli LLM.

Algoritmo:
1. Legge modelli disponibili da Ollama (/api/tags)
2. Legge hardware (VRAM GPU, RAM sistema, temp GPU)
3. Per ogni ruolo, calcola score per ogni modello candidato
4. Ritorna config raccomandato con spiegazione

Usage:
    from CORE.model_selector import get_recommendations, apply_recommendations
    recs = get_recommendations()
    for role, info in recs.items():
        print(f"{role}: {info['model']} (score: {info['score']:.1f}/100)")
        print(f"  reason: {info['reason']}")

    # Applica al config
    apply_recommendations(recs, "CONFIG/config.toml")
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Optional
import logging

log = logging.getLogger("byte-swarmy.model_selector")


# ====================================================================
# Definizione ruoli e requirements
# ====================================================================

ROLE_DEFINITIONS = {
    "orchestrator": {
        "description": "Decisioni veloci, caricamento rapido",
        "max_size_gb": 1.5,
        "ideal_size_gb": 0.5,
        "required_capability": "completion",
        "preferred_families": ["qwen2", "llama", "phi3", "qwen3"],
        "preferred_names": ["qwen2.5:0.5b", "qwen2.5:1.5b", "llama3.2:1b"],
        "penalize_families": [],
    },
    "planner": {
        "description": "Pianificazione task, instruction following",
        "max_size_gb": 4.0,
        "ideal_size_gb": 2.5,
        "required_capability": "completion",
        "preferred_families": ["phi3", "qwen2", "qwen3", "llama"],
        "preferred_names": ["phi3:mini", "qwen2.5:1.5b", "qwen3:4b"],
        "penalize_families": [],
    },
    "worker_coder": {
        "description": "Generazione codice, JSON ReAct format",
        "max_size_gb": 3.0,
        "ideal_size_gb": 1.5,
        "required_capability": "completion",
        "preferred_families": ["qwen2", "llama", "phi3"],
        "preferred_names": ["qwen2.5-coder:1.5b", "qwen2.5-coder:3b",
                            "deepseek-coder:1.3b", "deepseek-coder:6.7b"],
        "penalize_families": [],
        "name_keywords": ["coder", "code"],
    },
    "worker_general": {
        "description": "Task generali, auditing, spiegazioni",
        "max_size_gb": 3.0,
        "ideal_size_gb": 1.5,
        "required_capability": "completion",
        "preferred_families": ["qwen2", "llama", "phi3", "qwen3"],
        "preferred_names": ["qwen2.5:1.5b", "phi3:mini", "llama3.2:3b"],
        "penalize_families": [],
    },
    "embedding": {
        "description": "Embedding per ricerca semantica",
        "max_size_gb": 1.0,
        "ideal_size_gb": 0.3,
        "required_capability": "embedding",
        "preferred_families": ["nomic-bert", "gemma3"],
        "preferred_names": ["nomic-embed-text", "embeddinggemma"],
        "penalize_families": [],
    },
    "decision": {
        "description": "Scomposizione task generici in sottotask",
        "max_size_gb": 6.0,
        "ideal_size_gb": 4.0,
        "required_capability": None,  # qualsiasi, ma preferisce "decision"
        "preferred_families": ["qwen35", "qwen3", "qwen2"],
        "preferred_names": ["tev1:4b", "d3:4b", "nimble:4b", "qwen2.5:3b"],
        "penalize_families": [],
        "preferred_capability": "decision",
    },
}


# ====================================================================
# Lettori hardware
# ====================================================================

def get_ollama_models(host: str = "http://localhost:11434") -> list:
    """Legge la lista dei modelli da Ollama /api/tags."""
    try:
        data = json.loads(
            urllib.request.urlopen(f"{host}/api/tags", timeout=5).read()
        )
        models = []
        for m in data.get("models", []):
            details = m.get("details", {})
            models.append({
                "name": m.get("name", ""),
                "size_bytes": m.get("size", 0),
                "size_gb": m.get("size", 0) / 1e9,
                "family": details.get("family", ""),
                "families": details.get("families") or [],
                "capabilities": details.get("capabilities", []) or ["completion"],
                "parameter_size": details.get("parameter_size", ""),
                "quantization": details.get("quantization_level", ""),
                "context_length": details.get("context_length", 0),
            })
        return models
    except Exception as e:
        log.warning(f"cannot read ollama models: {e}")
        return []


def get_gpu_info() -> dict:
    """Legge VRAM GPU e temperatura via nvidia-smi."""
    import subprocess
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split(",")
            return {
                "vram_mb": int(parts[0].strip()),
                "vram_gb": int(parts[0].strip()) / 1024,
                "temp_c": float(parts[1].strip()) if len(parts) > 1 else 0,
            }
    except Exception:
        pass
    return {"vram_mb": 0, "vram_gb": 0, "temp_c": 0}


def get_ram_info() -> dict:
    """Legge RAM totale sistema."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return {"ram_mb": kb // 1024, "ram_gb": (kb // 1024) / 1024}
    except Exception:
        pass
    return {"ram_mb": 0, "ram_gb": 0}


# ====================================================================
# Algoritmo di scoring
# ====================================================================

def score_model_for_role(model: dict, role: str, hardware: dict) -> tuple:
    """Calcola score (0-100) per un modello in un ruolo.
    Ritorna (score, reason_str).
    """
    role_def = ROLE_DEFINITIONS[role]
    reasons = []
    score = 50.0  # base
    
    # === HARD GATE: capability richiesta ===
    req_cap = role_def["required_capability"]
    if req_cap:
        if req_cap not in model["capabilities"]:
            return (0, f"missing required capability: {req_cap}")
    
    # Embedding: deve avere SOLO embedding (non completion)
    if role == "embedding":
        if "completion" in model["capabilities"]:
            return (0, "is a chat model, not pure embedding")
    
    # === HARD GATE: size vs VRAM ===
    vram_gb = hardware.get("vram_gb", 0)
    ram_gb = hardware.get("ram_gb", 0)
    model_gb = model["size_gb"]
    
    if vram_gb > 0:
        # Lascia 25% per KV cache e altro
        max_vram = vram_gb * 0.75
        if model_gb > max_vram:
            return (0, f"too big for VRAM ({model_gb:.1f}GB > {max_vram:.1f}GB available)")
    
    if ram_gb > 0 and model_gb > ram_gb * 0.5:
        return (0, f"too big for RAM ({model_gb:.1f}GB > {ram_gb*0.5:.1f}GB limit)")
    
    # === SCORING ===
    
    # 1. Size score: più vicino all'ideal_size, meglio è
    ideal = role_def["ideal_size_gb"]
    max_size = role_def["max_size_gb"]
    if model_gb <= ideal:
        size_score = 20  # perfetto
        reasons.append(f"size {model_gb:.1f}GB ≤ ideal {ideal}GB")
    elif model_gb <= max_size:
        # Penalità lineare
        ratio = (model_gb - ideal) / (max_size - ideal)
        size_score = 20 - (15 * ratio)
        reasons.append(f"size {model_gb:.1f}GB (acceptable)")
    else:
        size_score = -10
        reasons.append(f"size {model_gb:.1f}GB > max {max_size}GB")
    score += size_score
    
    # 2. Family score
    family = model["family"]
    families = model["families"] or [family]
    preferred_families = role_def["preferred_families"]
    family_match = any(f in preferred_families for f in families if f)
    if family_match:
        score += 15
        reasons.append(f"family {family} preferred")
    
    # 3. Name match (preferred names)
    if model["name"] in role_def["preferred_names"]:
        score += 20
        reasons.append(f"exact preferred name match")
    elif role_def.get("name_keywords"):
        # worker_coder: reward se il nome contiene "coder"
        name_lower = model["name"].lower()
        for kw in role_def["name_keywords"]:
            if kw in name_lower:
                score += 15
                reasons.append(f"name contains '{kw}'")
                break
    
    # 4. Preferred capability (es. decision)
    pref_cap = role_def.get("preferred_capability")
    if pref_cap and pref_cap in model["capabilities"]:
        score += 25
        reasons.append(f"has preferred capability: {pref_cap}")
    
    # 5. Thermal penalty (se GPU calda, preferisci modelli piccoli)
    gpu_temp = hardware.get("temp_c", 0)
    if gpu_temp > 85 and model_gb > 2.0:
        score -= 15
        reasons.append(f"thermal penalty (GPU {gpu_temp:.0f}°C, model > 2GB)")
    elif gpu_temp > 75 and model_gb > 3.0:
        score -= 8
        reasons.append(f"minor thermal penalty")
    
    # 6. Quantization bonus (Q4_K_M è buon compromesso)
    quant = model.get("quantization", "")
    if "Q4_K_M" in quant:
        score += 5
        reasons.append("good quantization (Q4_K_M)")
    elif "Q8" in quant:
        score += 3
        reasons.append("Q8 quantization")
    elif "BF16" in quant or "F16" in quant:
        score -= 5  # troppo grosso senza quantization
        reasons.append("unquantized (BF16/F16) - too big")
    
    # Clamp 0-100
    score = max(0, min(100, score))
    return (score, "; ".join(reasons))


def get_recommendations(
    ollama_host: str = "http://localhost:11434",
    config_path: str = "CONFIG/config.toml",
) -> dict:
    """Calcola raccomandazioni per tutti i ruoli.
    
    Returns:
        {
            "orchestrator": {"model": "qwen2.5:0.5b", "score": 95.0, "reason": "..."},
            "worker_coder": {"model": "qwen2.5-coder:1.5b", "score": 88.0, "reason": "..."},
            ...
            "_hardware": {"vram_gb": 4.0, "ram_gb": 16.0, "gpu_temp": 65},
            "_available_models": 23,
        }
    """
    models = get_ollama_models(ollama_host)
    hardware = {**get_gpu_info(), **get_ram_info()}
    
    recs = {
        "_hardware": hardware,
        "_available_models": len(models),
        "_timestamp": __import__("time").time(),
    }
    
    for role in ROLE_DEFINITIONS:
        if not models:
            recs[role] = {"model": None, "score": 0, "reason": "no models available"}
            continue
        
        # Score tutti i modelli
        scored = []
        for m in models:
            score, reason = score_model_for_role(m, role, hardware)
            if score > 0:
                scored.append((score, m, reason))
        
        if not scored:
            recs[role] = {
                "model": None, "score": 0,
                "reason": f"no suitable model (all rejected by hard gates)"
            }
            continue
        
        # Sort per score desc
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_model, best_reason = scored[0]
        
        recs[role] = {
            "model": best_model["name"],
            "score": best_score,
            "reason": best_reason,
            "size_gb": best_model["size_gb"],
            "alternatives": [
                {"model": s[1]["name"], "score": s[0]}
                for s in scored[1:4]  # top 3 alternative
            ],
        }
    
    return recs


# ====================================================================
# Applicazione al config.toml
# ====================================================================

def apply_recommendations(recs: dict, config_path: str = "CONFIG/config.toml") -> bool:
    """Scrive le raccomandazioni nel config.toml.
    Ritorna True se tutto OK.
    """
    try:
        import tomllib
        import shutil
        
        # Backup
        backup = Path(config_path).with_suffix(".toml.bak.autoselect")
        shutil.copy2(config_path, backup)
        
        # Leggi config attuale
        with open(config_path, "rb") as f:
            cfg = tomllib.load(f)
        
        # Aggiorna [models.*]
        models_cfg = cfg.get("models", {})
        role_to_section = {
            "orchestrator": "orchestrator",
            "planner": "planner",
            "worker_coder": "worker_coder",
            "worker_general": "worker_general",
            "embedding": "embedding",
        }
        for role, section in role_to_section.items():
            rec = recs.get(role, {})
            if rec.get("model"):
                if section not in models_cfg:
                    models_cfg[section] = {}
                models_cfg[section]["name"] = rec["model"]
        
        # Aggiorna [decision_models.active] e [decision_models.tev1].enabled
        # (il modello raccomandato diventa active, gli altri disabled)
        decision_rec = recs.get("decision", {})
        if decision_rec.get("model"):
            decision_cfg = cfg.get("decision_models", {})
            recommended = decision_rec["model"]
            
            # Cerca la sezione che ha questo modello, o creane una nuova
            # basata sul nome modello
            model_section_name = recommended.split(":")[0].replace("-", "_").replace(".", "_")
            
            # Disabilita tutti gli altri decision models
            for key, val in decision_cfg.items():
                if isinstance(val, dict) and "enabled" in val:
                    if val.get("name") == recommended:
                        val["enabled"] = True
                        decision_cfg["active"] = key
                    else:
                        val["enabled"] = False
            
            # Se nessuno matcha, aggiungi una sezione nuova
            if not any(
                isinstance(v, dict) and v.get("name") == recommended
                for v in decision_cfg.values()
            ):
                decision_cfg[model_section_name] = {
                    "name": recommended,
                    "enabled": True,
                    "temperature": 0.1,
                    "num_ctx": 4096,
                }
                decision_cfg["active"] = model_section_name
            
            cfg["decision_models"] = decision_cfg
            cfg["models"] = models_cfg
        
        # Scrivi config con tomli_w
        try:
            import tomli_w
        except ImportError:
            log.error("tomli_w non installato. Installa con: pip install tomli-w")
            return False
        
        with open(config_path, "wb") as f:
            tomli_w.dump(cfg, f)
        
        log.info(f"config aggiornato con auto-selezione (backup: {backup})")
        return True
    
    except Exception as e:
        log.error(f"apply_recommendations failed: {e}")
        return False


def format_recommendations(recs: dict) -> str:
    """Formatta le raccomandazioni per display testuale."""
    lines = ["🎯 Auto-selezione modelli:", "=" * 60]
    
    hw = recs.get("_hardware", {})
    lines.append(f"Hardware: VRAM {hw.get('vram_gb', 0):.1f}GB | "
                 f"RAM {hw.get('ram_gb', 0):.1f}GB | "
                 f"GPU {hw.get('temp_c', 0):.0f}°C")
    lines.append(f"Modelli disponibili: {recs.get('_available_models', 0)}")
    lines.append("")
    
    for role in ROLE_DEFINITIONS:
        rec = recs.get(role, {})
        model = rec.get("model", "—")
        score = rec.get("score", 0)
        reason = rec.get("reason", "")
        size = rec.get("size_gb", 0)
        
        if model:
            icon = "✓" if score >= 70 else ("⚠" if score >= 40 else "✗")
            lines.append(f"{icon} {role:15} → {model:30} (score: {score:.0f}/100, {size:.1f}GB)")
            lines.append(f"  reason: {reason}")
            # Alternative
            alts = rec.get("alternatives", [])
            if alts:
                alt_str = ", ".join(f"{a['model']} ({a['score']:.0f})" for a in alts)
                lines.append(f"  alternatives: {alt_str}")
        else:
            lines.append(f"✗ {role:15} → NESSUN MODELLO ADATTO")
            lines.append(f"  reason: {reason}")
        lines.append("")
    
    return "\n".join(lines)


# ====================================================================
# Self-test
# ====================================================================

if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("MODEL SELECTOR - TEST")
    print("=" * 60)
    
    recs = get_recommendations()
    print(format_recommendations(recs))
    
    if "--apply" in sys.argv:
        print("\n→ Applicazione al config.toml...")
        if apply_recommendations(recs):
            print("✓ Config aggiornato. Riavvia l'orchestratore.")
        else:
            print("✗ Applicazione fallita.")
