"""core/processor.py — Elaborazione dati (mini-repo per benchmark esterno)."""

import json


def load_json(path):
    """Carica un file JSON e ritorna il dizionario."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    """Salva un dizionario su file JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def filter_active(items):
    """Filtra gli elementi con status 'active'."""
    result = []
    for item in items:
        if item.get("status") == "active":
            result.append(item)
    return result


def group_by_category(items):
    """Raggruppa gli elementi per categoria."""
    groups = {}
    for item in items:
        cat = item.get("category", "unknown")
        groups.setdefault(cat, []).append(item)
    return groups
