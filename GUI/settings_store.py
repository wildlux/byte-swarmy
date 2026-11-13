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

from CORE.state_repository import load_json, save_json

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
    # Debug GUI: mostra info widget sotto il mouse nella barra in basso
    "gui_debug": False,
    # Livello zoom interfaccia (percentuale, 50..200). Salvato quando l'utente
    # usa i pulsanti zoom o le scorciatoie Ctrl++ / Ctrl+- / Ctrl+0.
    "zoom_level": 100,
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
    data = load_json(SETTINGS_FILE, dict(DEFAULTS))
    if data is None:
        data = dict(DEFAULTS)
    # Merge con defaults per chiavi mancanti
    merged = dict(DEFAULTS)
    merged.update(data)
    # Auto-detect solo se l'utente non ha mai salvato esplicitamente
    # una strategia (campo "user_set_hardware_strategy" traccia questo)
    if (merged.get("detect_gpu_at_startup", True)
            and not merged.get("user_set_hardware_strategy", False)):
        merged["hardware_strategy"] = auto_detect_hardware_strategy()
    return merged


def save_settings(settings: Dict) -> bool:
    """Salva le impostazioni in CONFIG/settings.json. Ritorna True se ok."""
    return save_json(SETTINGS_FILE, settings)


def get_theme() -> str:
    return load_settings().get("theme", "dark")


def set_theme(theme: str) -> bool:
    # Valida contro i temi realmente disponibili (10+ temi, non solo
    # dark/light): un tema sconosciuto cade su "dark".
    try:
        from GUI.theme import theme as _T
        if theme not in _T.available_themes():
            theme = "dark"
    except Exception:
        if theme not in ("dark", "light"):
            theme = "dark"
    s = load_settings()
    s["theme"] = theme
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


# ── Debug GUI ─────────────────────────────────────────────────────────

def get_gui_debug() -> bool:
    """Ritorna se il debug GUI è attivo (mostra info widget sotto il mouse)."""
    return bool(load_settings().get("gui_debug", False))


def set_gui_debug(enabled: bool) -> bool:
    """Attiva/disattiva il debug GUI."""
    s = load_settings()
    s["gui_debug"] = bool(enabled)
    return save_settings(s)


# ── Chiusura finestra & orchestratore ────────────────────────────────

def get_close_action() -> str:
    """Azione ricordata alla chiusura della finestra:
    "" (chiedi ogni volta), "stop" (termina orchestratore),
    "keep" (lascia l'orchestratore attivo in background)."""
    try:
        v = str(load_settings().get("close_action", "") or "")
        return v if v in ("stop", "keep") else ""
    except Exception:
        return ""


def set_close_action(action: str) -> bool:
    """Salva l'azione ricordata alla chiusura ("" = chiedi ogni volta)."""
    try:
        s = load_settings()
        s["close_action"] = action if action in ("stop", "keep") else ""
        return save_settings(s)
    except Exception:
        return False


# ── Zoom interfaccia ─────────────────────────────────────────────────

def get_zoom_level() -> int:
    """Ritorna il livello zoom salvato (percentuale, clampato a 50..200)."""
    try:
        v = int(load_settings().get("zoom_level", 100))
    except Exception:
        v = 100
    return max(50, min(200, v))


def set_zoom_level(level: int) -> bool:
    """Salva il livello zoom dell'interfaccia in CONFIG/settings.json."""
    try:
        level = max(50, min(200, int(level)))
    except Exception:
        return False
    s = load_settings()
    s["zoom_level"] = level
    return save_settings(s)
