"""
GUI/skills_panel.py — Pannello "Skill" per la Plancia di Controllo.

Mostra l'elenco delle skill operative (.opencode/skill/*/SKILL.md) con
nome, descrizione e stato abilitato/disabilitato. L'utente può abilitare
o disabilitare ogni skill con il checkbox; lo stato è persistito in
state/skills_enabled.json. I dati sono letti da file (zero LLM).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox, QLabel, QScrollArea, QPushButton, QVBoxLayout, QWidget,
    QHBoxLayout,
)

from GUI.skill_completion import set_skill_enabled
from GUI.theme.theme import set_prop as _theme_prop


def list_skills() -> list:
    """Legge le SKILL.md del repo → lista di dict (name, description, path, enabled)."""
    from GUI.skill_completion import list_skills_with_status
    root = Path(__file__).resolve().parent.parent / ".opencode" / "skill"
    status = {s["name"]: s["enabled"] for s in list_skills_with_status()}
    out = []
    if not root.is_dir():
        return out
    for f in sorted(root.glob("*/SKILL.md")):
        name = f.parent.name
        description = ""
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("description:"):
                description = line.split("description:", 1)[1].strip()
                break
        out.append({
            "name": name,
            "description": description,
            "path": str(f),
            "enabled": bool(status.get(name, True)),
        })
    return out


class SkillsPanel(QWidget):
    """Pannello Plancia: elenco di tutte le skill operative."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("skills_panel")
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>🎓 Skill Operative</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        expl = QLabel(
            "Abilita/disabilita le skill con il checkbox. Le skill disabilitate "
            "verranno mostrate come ⛔ nel popup '@' del campo comando.")
        expl.setWordWrap(True)
        _theme_prop(expl, "role", "muted")
        outer.addWidget(expl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        content = QWidget()
        content.setObjectName("panelScrollContent")
        content.setStyleSheet("QWidget#panelScrollContent { background: transparent; }")
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 0, 0, 0)

        for sk in list_skills():
            row = QHBoxLayout()
            row.setSpacing(8)
            cb = QCheckBox()
            cb.setChecked(sk["enabled"])
            cb.toggled.connect(
                lambda checked, n=sk["name"]: self._on_toggle_skill(n, checked))
            row.addWidget(cb)
            name_lbl = QLabel(sk["name"])
            name_lbl.setStyleSheet("font-size:12px; font-weight:bold; ")
            row.addWidget(name_lbl)
            row.addStretch()
            lay.addLayout(row)
            desc_lbl = QLabel(sk["description"])
            desc_lbl.setWordWrap(True)
            _theme_prop(desc_lbl, "role", "muted")
            lay.addWidget(desc_lbl)

        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _on_toggle_skill(self, name: str, enabled: bool) -> None:
        set_skill_enabled(name, enabled)
        # Aggiorna il completer se raggiungibile (via parent tree).
        parent = self.parent()
        while parent is not None and not hasattr(parent, "skill_completer"):
            parent = parent.parent()
        if parent is not None and hasattr(parent, "skill_completer"):
            try:
                parent.skill_completer.refresh()
            except Exception:
                pass

    def _back_to_main(self):
        parent = self.parent()
        while parent is not None and not hasattr(parent, "back_to_main"):
            parent = parent.parent()
        if parent is not None and hasattr(parent, "back_to_main"):
            parent.back_to_main()
