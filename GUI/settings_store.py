"""Persistenza delle impostazioni di BYTE-SWARMY.

Salva in ``CONFIG/settings.json``:
- tema ("dark" | "light")
- lingua ("it" | "en")
- git_remotes: lista di {name, url, token, type} per push automatici
- hardware_strategy: modalità di bilanciamento CPU/GPU
  ("gpu+cpu" | "gpu_only" | "cpu_only" | "cpu_then_gpu")
- detect_gpu_at_startup: se True (default), rileva GPU all'avvio e
  sceglie il default intelligente (gpu+cpu se GPU, cpu_only altrimenti)
"""
import json
import os
import shutil
import subprocess
from typing import Dict, List, Optional

# Path assoluto del file settings.json
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(_BASE, "CONFIG", "settings.json")

# Modalità di strategia hardware (Round 3 — H1/H2)
HARDWARE_STRATEGIES = ("gpu+cpu", "gpu_only", "cpu_only", "cpu_then_gpu")

DEFAULTS = {
    "theme": "dark",          # "dark" o "light"
    "language": "it",         # "it" o "en" (work in progress)
    "git_remotes": [],        # [{"name": "origin", "url": "...", "token": "...", "type": "github|gitlab|git"}]
    # Strategia hardware (H1): default "cpu_only" until detect_gpu_at_startup
    # decide se c'è una GPU. L'orchestratore legge questa per scegliere dove
    # mandare i modelli (LLM/Decision/Timestral).
    "hardware_strategy": "cpu_only",
    "detect_gpu_at_startup": True,  # auto-detect all'avvio
}


def _detect_gpu() -> bool:
    """Rileva se c'è una GPU NVIDIA disponibile (via nvidia-smi).

    Ritorna True se nvidia-smi esiste e risponde. Fallback: nessun errore
    se nvidia-smi non è installato (restituisce False).
    """
    if not shutil.which("nvidia-smi"):
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def auto_detect_hardware_strategy() -> str:
    """Sceglie la strategia hardware di default in base a GPU presente.

    - GPU rilevata → "gpu+cpu" (potenza massima: LLM su GPU, Decision+Timestral su CPU)
    - Nessuna GPU → "cpu_only" (tutto su CPU)
    """
    return "gpu+cpu" if _detect_gpu() else "cpu_only"


def load_settings() -> Dict:
    """Carica le impostazioni da CONFIG/settings.json (con fallback ai default).

    Se ``detect_gpu_at_startup=True`` e la strategia salvata non è mai
    stata sovrascritta dall'utente, ricalcola la default strategy.
    """
    if not os.path.exists(SETTINGS_FILE):
        # Prima esecuzione: applica auto-detect
        s = dict(DEFAULTS)
        if s.get("detect_gpu_at_startup", True):
            s["hardware_strategy"] = auto_detect_hardware_strategy()
        return s
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge con defaults per chiavi mancanti
        merged = dict(DEFAULTS)
        merged.update(data)
        # Auto-detect solo se l'utente non ha mai salvato esplicitamente
        # una strategia (campo "user_set_hardware_strategy" traccia questo)
        if (merged.get("detect_gpu_at_startup", True)
                and not merged.get("user_set_hardware_strategy", False)):
            merged["hardware_strategy"] = auto_detect_hardware_strategy()
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save_settings(settings: Dict) -> bool:
    """Salva le impostazioni in CONFIG/settings.json. Ritorna True se ok."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f"Errore salvataggio settings: {e}")
        return False


def get_theme() -> str:
    return load_settings().get("theme", "dark")


def set_theme(theme: str) -> bool:
    s = load_settings()
    s["theme"] = theme if theme in ("dark", "light") else "dark"
    return save_settings(s)


def get_language() -> str:
    return load_settings().get("language", "it")


def set_language(lang: str) -> bool:
    s = load_settings()
    s["language"] = lang if lang in ("it", "en") else "it"
    return save_settings(s)


def get_git_remotes() -> List[Dict]:
    return load_settings().get("git_remotes", [])


def set_git_remotes(remotes: List[Dict]) -> bool:
    s = load_settings()
    s["git_remotes"] = remotes
    return save_settings(s)


def add_git_remote(name: str, url: str, token: str = "", rtype: str = "git") -> bool:
    """Aggiunge (o aggiorna se name già esiste) un remote Git."""
    remotes = get_git_remotes()
    # Rimuovi se esiste già con stesso name
    remotes = [r for r in remotes if r.get("name") != name]
    remotes.append({
        "name": name,
        "url": url,
        "token": token,
        "type": rtype,
    })
    return set_git_remotes(remotes)


def remove_git_remote(name: str) -> bool:
    remotes = get_git_remotes()
    remotes = [r for r in remotes if r.get("name") != name]
    return set_git_remotes(remotes)


# ── Strategia Hardware (H1/H2) ───────────────────────────────────

def get_hardware_strategy() -> str:
    """Ritorna la strategia hardware attuale (una di HARDWARE_STRATEGIES)."""
    s = load_settings().get("hardware_strategy", "cpu_only")
    return s if s in HARDWARE_STRATEGIES else "cpu_only"


def set_hardware_strategy(strategy: str, user_set: bool = True) -> bool:
    """Imposta la strategia hardware.

    ``user_set=True`` (default) marca la scelta come esplicita — l'auto-detect
    non la sovrascriverà più. ``user_set=False`` per ripristinare auto-detect.
    """
    s = load_settings()
    s["hardware_strategy"] = strategy if strategy in HARDWARE_STRATEGIES else "cpu_only"
    s["user_set_hardware_strategy"] = bool(user_set)
    return save_settings(s)


def is_gpu_available() -> bool:
    """Wrapper pubblico per _detect_gpu (usato da orchestratore + GUI)."""
    return _detect_gpu()


def get_effective_strategy_description(strategy: str = None) -> str:
    """Ritorna una descrizione umana della strategia (per tooltip UI)."""
    s = strategy or get_hardware_strategy()
    return {
        "gpu+cpu": "GPU+CPU: LLM su GPU (potenza), Decision+Timestral su CPU (parallelo)",
        "gpu_only": "Solo GPU: tutto su GPU (più veloce, più consumo)",
        "cpu_only": "Solo CPU: tutto su CPU (no GPU, più lento ma sicuro)",
        "cpu_then_gpu": "CPU→GPU: default CPU, switcha a GPU se CPU overload",
    }.get(s, "Strategia sconosciuta")
