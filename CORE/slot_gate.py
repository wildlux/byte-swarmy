"""CORE/slot_gate.py — gate deterministico per UN frammento (slot).

SLOT-1 dell'architettura a slot (`RAG/DOCS/ARCHITETTURA_SLOT.md`): il 3b non
scrive file interi, riempie slot piccoli. Questo gate verifica il
frammento PRIMA dell'assembly:

- sintassi valida (`ast.parse` / pyflakes);
- nessun nome indefinito *al di fuori* delle refs dichiarate per lo slot.

Un frammento che passa qui è ancora da verificare col gate finale (test,
auditor): il gate per-slot riduce il raggio dell'errore, non lo sostituisce.

Zero LLM, nessuna rete, nessun I/O di progetto.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from CORE.import_check import Issue, check_source, format_issues

# Tipi di slot ammessi (il planner li emette; un tipo ignoto è un bug).
ALLOWED_KINDS = frozenset({
    "function", "method", "class", "handler", "widget", "import", "statement",
})

# Per questi tipi `self`/`cls` sono impliciti (metodo/gestore di widget).
_SELF_KINDS = frozenset({"method", "handler", "widget"})

_DEF_RE = re.compile(r"\b(?:def|class)\s+([A-Za-z_]\w*)")
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_ATTR_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\.")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")


@dataclass
class SlotVerdict:
    """Esito del gate su un frammento."""

    ok: bool
    kind: str
    undefined: list[Issue] = field(default_factory=list)
    syntax: list[Issue] = field(default_factory=list)
    known: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return self.syntax + self.undefined

    def summary(self) -> str:
        """Una riga per i log; dettaglio con `detail()`."""
        if self.ok:
            return f"slot OK ({self.kind})"
        parts = []
        if self.syntax:
            parts.append(f"{len(self.syntax)} errore/i di sintassi")
        if self.undefined:
            parts.append(f"{len(self.undefined)} nome/i indefinito/i")
        return f"slot RIFIUTATO ({self.kind}): " + ", ".join(parts)

    def detail(self, limit: int = 8) -> str:
        """Blocco multi-riga per il prompt di correction."""
        if self.ok:
            return self.summary()
        return self.summary() + "\n" + format_issues(self.errors, limit)


def names_from_refs(refs: Iterable[str] | None) -> set[str]:
    """Nomi definiti dalle refs (codice Python o prosa tecnica).

    Le refs sono curate: se un nome compare lì, è lecito usarlo. Per il
    codice Python si prendono i binding reali; per la prosa si prendono
    gli identificatori (le refs non contengono segreti né rumore).
    """
    names: set[str] = set()
    for ref in refs or ():
        if not isinstance(ref, str) or not ref.strip():
            continue
        try:
            tree = ast.parse(textwrap.dedent(ref))
        except SyntaxError:
            names.update(_DEF_RE.findall(ref))
            names.update(_CALL_RE.findall(ref))
            names.update(_ATTR_RE.findall(ref))
            names.update(_IDENT_RE.findall(ref))
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name):
                # Ref curate: un nome citato (anche solo letto, es.
                # `QTimer.singleShot(...)` in prosa) è lecito.
                names.add(node.id)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
    return names


def _implicit_names(kind: str) -> set[str]:
    return {"self"} if kind in _SELF_KINDS else set()


def gate_slot(fragment: str, refs: Sequence[str] | None = None,
              kind: str = "function") -> SlotVerdict:
    """Valida UN frammento di slot.

    Args:
        fragment: codice dello slot (funzione, metodo, classe, statement).
        refs: API/simboli disponibili per questo slot (non per il file).
        kind: uno di ALLOWED_KINDS (metadata + nomi impliciti).

    Returns:
        SlotVerdict con `ok`, errori di sintassi e nomi indefiniti.
    """
    if kind not in ALLOWED_KINDS:
        raise ValueError(
            f"kind sconosciuto: {kind!r} (ammessi: {sorted(ALLOWED_KINDS)})")

    text = textwrap.dedent(fragment or "").strip("\n")
    if not text.strip():
        issue = Issue("<slot>", 0, 0, "syntax", "frammento vuoto")
        return SlotVerdict(ok=False, kind=kind, syntax=[issue])

    known = names_from_refs(refs) | _implicit_names(kind)
    issues = check_source(text, "<slot>", known)
    syntax = [i for i in issues if i.kind == "syntax"]
    undefined = [i for i in issues if i.kind == "undefined_name"]
    return SlotVerdict(
        ok=not issues, kind=kind, undefined=undefined, syntax=syntax,
        known=sorted(known),
    )
