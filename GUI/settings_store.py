"""Persistenza delle impostazioni di BYTE-SWARMY.

Salva in ``CONFIG/settings.json``:
- tema ("dark" | "light")
- lingua ("it" | "en")
- git_remotes: lista di {name, url, token, type} per push automatici

Il file è createdo al primo salvataggio. Se non esiste, si usano i default.
"""
import json
import os
from typing import Dict, List, Optional

# Path assoluto del file settings.json
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(_BASE, "CONFIG", "settings.json")

DEFAULTS = {
    "theme": "dark",          # "dark" o "light"
    "language": "it",         # "it" o "en" (work in progress)
    "git_remotes": [],        # [{"name": "origin", "url": "...", "token": "...", "type": "github|gitlab|git"}]
}


def load_settings() -> Dict:
    """Carica le impostazioni da CONFIG/settings.json (con fallback ai default)."""
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge con defaults per chiavi mancanti
        merged = dict(DEFAULTS)
        merged.update(data)
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
