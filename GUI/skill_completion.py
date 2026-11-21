"""
GUI/skill_completion.py — Autocompletamento skill con trigger "@".

Mostra un popup con tutte le skill operative (.opencode/skill/*) quando
l'utente digita "@" nel campo comando, indicando se ogni skill è
abilitata o disabilitata. Lo stato abilitato/disabilitato è persistito
in state/skills_enabled.json (default: tutte abilitate).
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QCompleter

BASE_DIR = Path(__file__).parent.parent.resolve()
SKILLS_ROOT = BASE_DIR / ".opencode" / "skill"
ENABLED_FILE = BASE_DIR / "state" / "skills_enabled.json"


def _load_enabled() -> dict:
    """Legge lo stato abilitato/disabilitato delle skill."""
    if not ENABLED_FILE.exists():
        return {}
    try:
        return json.loads(ENABLED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_enabled(data: dict) -> None:
    """Persiste lo stato abilitato/disabilitato delle skill."""
    ENABLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENABLED_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8")


def list_skills_with_status() -> list:
    """Legge le skill operative + stato abilitato/disabilitato."""
    enabled = _load_enabled()
    out = []
    if not SKILLS_ROOT.is_dir():
        return out
    for f in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        name = f.parent.name
        description = ""
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("description:"):
                description = line.split("description:", 1)[1].strip()
                break
        out.append({
            "name": name,
            "description": description,
            "enabled": bool(enabled.get(name, True)),
        })
    return out


def set_skill_enabled(name: str, enabled: bool) -> None:
    """Imposta lo stato abilitato/disabilitato di una skill."""
    data = _load_enabled()
    data[name] = bool(enabled)
    _save_enabled(data)


class SkillMentionCompleter(QCompleter):
    """Completer che mostra le skill con trigger '@'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self._refresh_model()

    def _refresh_model(self) -> None:
        """Ricarica il modello con le skill correnti."""
        self._model.clear()
        for sk in list_skills_with_status():
            marker = "✅" if sk["enabled"] else "⛔"
            item = QStandardItem(f"{marker} {sk['name']}")
            item.setData(sk["name"], Qt.ItemDataRole.UserRole)
            item.setData(sk["name"], Qt.ItemDataRole.EditRole)
            item.setToolTip(sk["description"])
            self._model.appendRow(item)

    def refresh(self) -> None:
        """Alias pubblico per ricaricare il modello."""
        self._refresh_model()

    def selected_skill_name(self, index: QModelIndex) -> str:
        """Restituisce il nome della skill dall'indice selezionato."""
        if not index.isValid():
            return ""
        return str(index.data(Qt.ItemDataRole.UserRole) or "")
