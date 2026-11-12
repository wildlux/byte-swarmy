"""
model_selector.py — Auto-selezione intelligente dei modelli LLM.

Algoritmo:
1. Legge modelli disponibili da Ollama (/api/tags)
2. Legge hardware (VRAM GPU, RAM sistema, temp GPU)
3. Per ogni ruolo, calcola score per ogni modello candidato
4. Ritorna config raccomandato con spiegazione

M10 — Evidence boost: i punteggi euristicci (famiglia, nome,
quantizzazione, RAM) sono integrati con i risultati REALI della suite
T1-T10 salvati in `state/suite_compare/results.json`. Un modello che
ha 10/10 documentati riceve +30; 5-9/10 → +15; <5 o assente → 0.
Fail-open: file assente/corrotto/config non leggibile → nessun boost,
si resta sulle euristiche (comportamento pre-M10).

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
import os
import urllib.request
from pathlib import Path
from typing import Optional
import logging
import sys
_OUT = sys.stdout

from CORE.constants import OLLAMA_HOST, DEFAULT_NUM_CTX


log = logging.getLogger("byte-swarmy.model_selector")


# Path predefinito dei risultati della suite comparativa (M10).
SUITE_RESULTS_PATH = Path("state/suite_compare/results.json")
CONFIG_PATH_DEFAULT = "CONFIG/config.toml"


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

def get_ollama_models(host: str = OLLAMA_HOST) -> list:
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
# M10 — Evidence boost (risultati suite reali)
# ====================================================================

def load_suite_evidence(
    results_path: Path | str = SUITE_RESULTS_PATH,
    config_path: Path | str = CONFIG_PATH_DEFAULT,
) -> dict:
    """Legge state/suite_compare/results.json e mappa chiavi → nomi.

    Il JSON ha chiavi = model_key (es. `worker_coder`) e valori = dict
    {T1: {ok, attempts, secs, done}, T2: ...}. Per usare l'evidence in
    score_model_for_role (che lavora con `model["name"]` Ollama come
    `qwen2.5-coder:3b`), dobbiamo mappare model_key → name leggendo
    `CONFIG/config.toml [models.<key>].name`.

    Ritorna:
        {
            "qwen2.5-coder:3b": {
                "model_key": "worker_coder",
                "pass": 10, "total": 10, "mean_secs": 13.9,
                "mean_attempts": 1.1, "score": 100.0,
            },
            ...
        }
    Fail-open: file assente/corrotto/config illeggibile → {}.
    """
    out: dict[str, dict] = {}
    try:
        rp = Path(results_path)
        if not rp.exists():
            return {}
        data = json.loads(rp.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
    except Exception:
        return {}

    # model_key → ollama_name dal config.toml
    key_to_name: dict[str, str] = {}
    try:
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            return {}  # senza tomllib niente mappatura → niente evidence
        cp = Path(config_path)
        if not cp.exists():
            return {}
        with open(cp, "rb") as f:
            cfg = tomllib.load(f)
        for k, v in (cfg.get("models") or {}).items():
            if isinstance(v, dict) and v.get("name"):
                key_to_name[k] = str(v["name"])
    except Exception:
        return {}

    for model_key, per_task in data.items():
        if not isinstance(per_task, dict):
            continue
        name = key_to_name.get(model_key, "")
        if not name:
            continue  # modello non in config → salto (non posso mappare)
        total = 0
        passed = 0
        secs = 0.0
        attempts = 0
        for tid, res in per_task.items():
            if not isinstance(res, dict):
                continue
            total += 1
            if res.get("ok"):
                passed += 1
            secs += float(res.get("secs") or 0)
            attempts += int(res.get("attempts") or 0)
        if total == 0:
            continue
        mean_secs = round(secs / total, 2)
        mean_attempts = round(attempts / total, 2)
        pass_rate = passed / total
        # Score evidence: 10/10 → 100, 5/10 → 50, 0/10 → 0
        out[name] = {
            "model_key": model_key,
            "pass": passed,
            "total": total,
            "mean_secs": mean_secs,
            "mean_attempts": mean_attempts,
            "score": round(pass_rate * 100, 1),
        }
    return out


def _evidence_boost_for_model(
    model_name: str,
    evidence: dict,
) -> tuple[float, str]:
    """(boost, reason) per un modello in base all'evidence.

    Logica (soglie decise sulla suite Fase 7):
      - 10/10 → +30 (è il modello "già provato buono")
      - 7-9/10 → +20
      - 5-6/10 → +10
      - 1-4/10 → -10 (penalty: ha tentativi falliti documentati)
      - 0/10 → -20 (penalty forte)
      - assente → (0, "") — nessuna evidence, resta sulle euristiche

    Bonus secondario: se mean_attempts ≤ 1.2 (correzioni al primo
    colpo quasi sempre) → +5; se mean_secs ≤ 15 → +5 (velocità).
    """
    if not evidence:
        return 0.0, ""
    e = evidence.get(model_name)
    if not e:
        return 0.0, ""
    passed = e["pass"]
    total = e["total"]
    if total == 0:
        return 0.0, ""
    pass_rate = passed / total
    if pass_rate >= 1.0:
        boost = 30.0
        tier = f"evidence {passed}/{total}"
    elif pass_rate >= 0.7:
        boost = 20.0
        tier = f"evidence {passed}/{total}"
    elif pass_rate >= 0.5:
        boost = 10.0
        tier = f"evidence {passed}/{total}"
    elif pass_rate >= 0.1:
        boost = -10.0
        tier = f"evidence {passed}/{total} (weak)"
    else:
        boost = -20.0
        tier = f"evidence {passed}/{total} (rejected)"
    reasons = [tier]
    # Bonus secondari (solo se già pass_rate > 0)
    if pass_rate > 0:
        if e.get("mean_attempts", 99) <= 1.2:
            boost += 5.0
            reasons.append(f"low retries ({e['mean_attempts']}/task)")
        if e.get("mean_secs", 999) <= 15.0:
            boost += 5.0
            reasons.append(f"fast ({e['mean_secs']}s/task)")
    return boost, "; ".join(reasons)


# ====================================================================
# Algoritmo di scoring
# ====================================================================

def score_model_for_role(model: dict, role: str, hardware: dict,
                         evidence: Optional[dict] = None) -> tuple:
    """Calcola score (0-100) per un modello in un ruolo.
    Ritorna (score, reason_str).

    M10 — `evidence` (opzionale, dict da load_suite_evidence) aggiunge
    un boost/penalty basato sui risultati REALI della suite T1-T10:
    un modello 10/10 documentato riceve +30, uno 0/10 riceve -20.
    Fail-open: se `evidence` è None non viene applicato (si resta sulle
    euristiche, comportamento pre-M10).
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

    # 7. M10 — Evidence boost (risultati suite T1-T10 reali)
    if evidence is not None:
        boost, ev_reason = _evidence_boost_for_model(
            model["name"], evidence)
        if boost != 0 or ev_reason:
            score += boost
            if ev_reason:
                reasons.append(ev_reason)

    # Clamp 0-100
    score = max(0, min(100, score))
    return (score, "; ".join(reasons))


def get_recommendations(
    ollama_host: str = OLLAMA_HOST,
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
            "_evidence": {"qwen2.5-coder:3b": {...}, ...},  # M10
        }
    """
    models = get_ollama_models(ollama_host)
    hardware = {**get_gpu_info(), **get_ram_info()}
    # M10 — carica l'evidence una sola volta (fail-open totale)
    evidence = load_suite_evidence(SUITE_RESULTS_PATH, config_path)

    recs = {
        "_hardware": hardware,
        "_available_models": len(models),
        "_timestamp": __import__("time").time(),
        "_evidence": evidence,  # M10: visibile per debug/display
    }

    for role in ROLE_DEFINITIONS:
        if not models:
            recs[role] = {"model": None, "score": 0, "reason": "no models available"}
            continue

        # Score tutti i modelli
        scored = []
        for m in models:
            score, reason = score_model_for_role(m, role, hardware,
                                                 evidence=evidence)
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
                    "num_ctx": DEFAULT_NUM_CTX,
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
    # M10 — mostra se l'evidence è stata caricata
    ev = recs.get("_evidence") or {}
    if ev:
        lines.append(f"Evidence suite: {len(ev)} modello/i con risultati "
                     f"T1-T10 documentati")
    else:
        lines.append("Evidence suite: NESSUNA (lanciare "
                     "`python scripts/suite_compare.py worker_coder` per "
                     "generarla e ottenere boost evidence-based)")
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
    logging.basicConfig(stream=_OUT, format="%(message)s", level=logging.INFO)
    import sys
    log.info("=" * 60)
    log.info("MODEL SELECTOR - TEST")
    log.info("=" * 60)

    recs = get_recommendations()
    log.info(format_recommendations(recs))

    if "--apply" in sys.argv:
        log.info("\n→ Applicazione al config.toml...")
        if apply_recommendations(recs):
            log.info("✓ Config aggiornato. Riavvia l'orchestratore.")
        else:
            log.error("✗ Applicazione fallita.")
