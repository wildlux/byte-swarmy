"""
GUI/skills_panel.py — Pannello "Skill" per la Plancia di Controllo.

Mostra l'elenco delle skill operative (.opencode/skill/*/SKILL.md) con
nome e descrizione, cosi l'utente le vede tutte dentro la Plancia.
I dati sono letti da file (zero LLM), quindi deterministici.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QLabel, QHBoxLayout, QScrollArea, QPushButton, QVBoxLayout, QWidget,
)

from GUI.theme.theme import set_prop as _theme_prop


def _skills_root() -> Path:
    """Cartella delle skill operative del repo."""
    return Path(__file__).resolve().parent.parent / ".opencode" / "skill"


def list_skills() -> list:
    """Legge le SKILL.md del repo → lista di dict (name, description, path).

    Solo file di testo: nessun LLM, nessuna ambiguità.
    """
    root = _skills_root()
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
        out.append({"name": name, "description": description,
                    "path": str(f)})
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
            name_lbl = QLabel(sk["name"])
            name_lbl.setStyleSheet("font-size:12px; font-weight:bold; ")
            name_lbl.setWordWrap(True)
            lay.addWidget(name_lbl)
            desc_lbl = QLabel(sk["description"])
            desc_lbl.setWordWrap(True)
            _theme_prop(desc_lbl, "role", "muted")
            lay.addWidget(desc_lbl)

        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _back_to_main(self):
        parent = self.parent()
        while parent is not None and not hasattr(parent, "back_to_main"):
            parent = parent.parent()
        if parent is not None and hasattr(parent, "back_to_main"):
            parent.back_to_main()
