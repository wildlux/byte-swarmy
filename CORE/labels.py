"""
CORE/labels.py — Etichette (tag) per i task: nome + colore.

Un'etichetta ha un nome (es. "unione_merge", "Arancione") e un colore.
Se il nome corrisponde a un colore noto (es. "Arancione", "Orange"), si usa
quel colore; altrimenti si assegna un colore deterministico (hash) coerente
per lo stesso nome. Le etichette sono persistite in state/labels.json.

Uso:
    from CORE.labels import get_color, get_or_create_label, list_labels
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent.resolve()
LABELS_FILE = BASE_DIR / "state" / "labels.json"
# Tombstone delle etichette di default eliminate dall'utente. senza questo
# file ``ensure_default_labels()`` ricreerebbe "Test" subito dopo remove_label:
# l'eliminazione sembrava funzionare ma l'etichetta ricompariva (2026-11-22).
DELETED_FILE = BASE_DIR / "state" / "labels_deleted.json"

# Mappa nome-colore (italiano + inglese) → hex.
COLOR_NAMES = {
    "rosso": "#dc2626", "red": "#dc2626",
    "arancione": "#f59e0b", "orange": "#f59e0b",
    "giallo": "#eab308", "yellow": "#eab308",
    "verde": "#16a34a", "green": "#16a34a",
    "blu": "#2563eb", "blue": "#2563eb",
    "viola": "#9333ea", "purple": "#9333ea", "violet": "#9333ea",
    "rosa": "#ec4899", "pink": "#ec4899",
    "grigio": "#64748b", "gray": "#64748b", "grey": "#64748b",
    "nero": "#0f172a", "black": "#0f172a",
    "bianco": "#f8fafc", "white": "#f8fafc",
    "marrone": "#92400e", "brown": "#92400e",
    "turchese": "#0d9488", "teal": "#0d9488", "cyan": "#06b6d4",
}

# Palette per hash deterministico (colori distinti e leggibili).
_PALETTE = [
    "#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#9333ea",
    "#0d9488", "#ec4899", "#0891b2", "#b45309", "#475569",
]


def _load() -> dict:
    if not LABELS_FILE.exists():
        return {}
    try:
        return json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LABELS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _deleted() -> set[str]:
    """Nomi eliminati dall'utente (non devono essere ricreati dai default)."""
    try:
        value = json.loads(DELETED_FILE.read_text(encoding="utf-8"))
        return {str(v) for v in value} if isinstance(value, list) else set()
    except Exception:
        return set()


def _save_deleted(names: set[str]) -> None:
    DELETED_FILE.parent.mkdir(parents=True, exist_ok=True)
    DELETED_FILE.write_text(
        json.dumps(sorted(names), indent=2, ensure_ascii=False),
        encoding="utf-8")


def _hash_color(name: str) -> str:
    """Colore deterministico per un nome non riconosciuto."""
    h = int(hashlib.sha256(name.lower().encode("utf-8")).hexdigest(), 16)
    return _PALETTE[h % len(_PALETTE)]


def get_color(name: str) -> str:
    """Restituisce il colore di un'etichetta (esistente o deterministico)."""
    name = (name or "").strip()
    if not name:
        return _PALETTE[0]
    data = _load()
    if name in data and isinstance(data[name], str):
        return data[name]
    low = name.lower()
    if low in COLOR_NAMES:
        return COLOR_NAMES[low]
    return _hash_color(name)


def get_or_create_label(name: str) -> dict:
    """Restituisce {name, color} creando l'etichetta se non esiste.

    La creazione esplicita rimuove l'eventuale tombstone: un'etichetta
    eliminata e poi riaggiunta torna a essere un default normale.
    """
    name = (name or "").strip()
    color = get_color(name)
    data = _load()
    if name not in data:
        data[name] = color
        _save(data)
    deleted = _deleted()
    if name in deleted:
        deleted.discard(name)
        _save_deleted(deleted)
    return {"name": name, "color": color}


def list_labels() -> list[dict]:
    """Elenca tutte le etichette registrate (nome + colore)."""
    ensure_default_labels()
    data = _load()
    out = []
    for name, color in data.items():
        if isinstance(color, str):
            out.append({"name": name, "color": color})
    # Aggiunge i colori noti non ancora registrati? No: solo registrati.
    return sorted(out, key=lambda x: x["name"].lower())


DEFAULT_LABELS = {
    "GUI": "#2563eb",
    "Finestra": "#2563eb",
    "Bottoni": "#16a34a",
    "Schede": "#9333ea",
    "Refactoring": "#f59e0b",
    "Codice morto": "#dc2626",
    "Test": "#0891b2",
    "Documentazione": "#64748b",
    "Bug": "#dc2626",
    "Feature": "#16a34a",
    "Performance": "#f59e0b",
    "Sicurezza": "#b91c1c",
    # Tipologie di programmazione
    "programmazione gui": "#2563eb",
    "programmazione CLI": "#16a34a",
    "script": "#f59e0b",
    "freecad script": "#9333ea",
    "blender script": "#dc2626",
}


def ensure_default_labels() -> None:
    """Crea i default mancanti, saltando quelli eliminati dall'utente."""
    data = _load()
    deleted = _deleted()
    changed = False
    for name, color in DEFAULT_LABELS.items():
        if name not in data and name not in deleted:
            data[name] = color
            changed = True
    if changed:
        _save(data)


def parse_labels(text: str) -> list[str]:
    """Estrae i nomi di etichetta da un testo ('#Nome' o '#unione_merge').

    Restituisce i nomi senza '#', deduplicati, preservando l'ordine.
    """
    if not text:
        return []
    matches = re.findall(r"#([A-Za-z0-9_\-]+)", text)
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def set_color(name: str, color: str) -> None:
    """Imposta/aggiorna il colore di un'etichetta."""
    name = (name or "").strip()
    if not name:
        return
    data = _load()
    data[name] = color
    _save(data)


def remove_label(name: str) -> bool:
    """Rimuove un'etichetta dal registro e la testamenta se è un default.

    Ritorna True se il nome era presente. La tombstone impedisce che
    ``ensure_default_labels`` lo ricrei al successivo ``list_labels``.
    """
    name = (name or "").strip()
    if not name:
        return False
    data = _load()
    if name not in data:
        return False
    del data[name]
    _save(data)
    if name in DEFAULT_LABELS:
        deleted = _deleted()
        deleted.add(name)
        _save_deleted(deleted)
    return True


def rename_label(old: str, new: str) -> bool:
    """Rinomina un'etichetta (preserva il colore)."""
    old = (old or "").strip()
    new = (new or "").strip()
    if not old or not new or old == new:
        return False
    data = _load()
    if old not in data:
        return False
    color = data.pop(old)
    data[new] = color
    _save(data)
    return True
