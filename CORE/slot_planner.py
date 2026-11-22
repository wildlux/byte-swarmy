"""CORE/slot_planner.py — planner deterministico a slot (SLOT-3 / P2-3).

Step [1] dell'`DOCS/ARCHITETTURA_SLOT.md`: trasforma un task dichiarativo in
una lista PICCOLA di slot {file, anchor, tipo, refs proprie, test proprio}.
Il modello 3b riempie un solo slot alla volta; qui NON si generate codice e
NON si chiama alcun LLM: la scelta del template avviene per parole chiave,
con punteggio deterministico e fail-closed.

Regole (verificate dai test):

- un solo template per task; in caso di pareggio o zero match il piano è
  RIFIUTATO con motivo esplicito (il planner NON inventa architetture —
  coerentemente con il radar Architettura 2/4);
- gli anchor sono derivati dai marker `# SLOT:` reali del template: se il
  template cambia (conteggio marker diverso) il piano è rifiutato;
- ogni ref deve comparire davvero tra i nomi del template (AST): refs
  allucinate bloccano il piano;
- il test di ogni slot deve esistere in `tests/test_gui_templates.py`;
- output identico per input identico (nessun timestamp, nessun random).
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from CORE.slot_gate import ALLOWED_KINDS

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "GUI" / "refs" / "templates"
TEST_FILE = ROOT / "tests" / "test_gui_templates.py"

_MARKER_RE = re.compile(r"^\s*#\s*SLOT:\s*(?P<text>.+?)\s*$")


@dataclass(frozen=True)
class SlotSpec:
    """Uno slot da riempire: tutto quello che il filler deve sapere."""

    anchor: str
    kind: str
    marker: str
    refs: tuple[str, ...]
    instruction: str
    test: str

    def to_dict(self) -> dict:
        return {
            "anchor": self.anchor,
            "kind": self.kind,
            "marker": self.marker,
            "refs": list(self.refs),
            "instruction": self.instruction,
            "test": self.test,
        }


@dataclass(frozen=True)
class SlotPlan:
    """Piano completo, o piano rifiutato con motivo (fail closed)."""

    task: str
    template: str | None
    slots: tuple[SlotSpec, ...]
    rejected: bool
    reason: str

    @property
    def ok(self) -> bool:
        return not self.rejected and bool(self.slots)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "template": self.template,
            "rejected": self.rejected,
            "reason": self.reason,
            "slots": [s.to_dict() for s in self.slots],
        }

    def to_markdown(self) -> str:
        lines = [f"# Piano SLOT — {self.task}", ""]
        if self.rejected:
            lines += [f"**RIFIUTATO**: {self.reason}", ""]
            return "\n".join(lines)
        lines += [
            f"Template: `{self.template}`",
            "",
            "| Slot | Tipo | Refs | Test |",
            "|---|---|---|---|",
        ]
        for slot in self.slots:
            refs = ", ".join(f"`{r}`" for r in slot.refs)
            lines.append(
                f"| `{slot.anchor}` — {slot.instruction} | {slot.kind} | "
                f"{refs} | `{slot.test}` |")
        lines += [
            "",
            "Regola: un solo slot per turno, max 40 righe, gate per-slot "
            "prima dell'assemblaggio. Nessuna API fuori dalle refs.",
            "",
        ]
        return "\n".join(lines)


# Definizioni indicizzate per nome file. L'ordine degli slot deve seguire
# l'ordine dei marker `# SLOT:` nel template (verificato in _validate).
_TEMPLATES: dict[str, dict] = {
    "finestra.py.tpl": {
        "keywords": ("finestra", "window", "dialog", "mainwindow"),
        "test": "test_finestra_snapshot",
        "slots": (
            ("titolo", "statement", "TITLE",
             "impostare il titolo della finestra"),
            ("dimensioni", "statement", "WIDTH",
             "impostare larghezza e altezza iniziali"),
        ),
    },
    "layout.py.tpl": {
        "keywords": ("layout", "form", "etichetta", "pulsante", "button"),
        "test": "test_layout_snapshot",
        "slots": (
            ("etichetta", "statement", "FIELD_LABEL",
             "impostare l'etichetta del campo"),
            ("pulsanti", "statement", "OK_TEXT",
             "impostare i testi dei pulsanti"),
        ),
    },
    "segnali.py.tpl": {
        "keywords": ("segnal", "signal", "live", "tempo reale", "aggiorna"),
        "test": "test_segnali_collegati",
        "slots": (
            ("tipo_segnale", "statement", "pyqtSignal",
             "dichiarare il tipo del segnale"),
            ("placeholder", "method", "QLineEdit",
             "impostare il placeholder del campo di testo"),
        ),
    },
    "thread.py.tpl": {
        "keywords": ("thread", "worker", "asincrono", "async", "sfondo"),
        "test": "test_thread_completa_e_si_ferma",
        "slots": (
            ("messaggio", "statement", "DONE_MESSAGE",
             "impostare il messaggio di fine lavoro"),
        ),
    },
}


def _import_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Nomi introdotti da un import, senza alias '*'."""
    result: list[str] = []
    for alias in node.names:
        if alias.name == "*":
            continue
        if isinstance(node, ast.ImportFrom):
            result.append(alias.asname or alias.name)
        else:
            result.append(alias.asname or alias.name.split(".")[0])
    return result


def _template_names(source: str) -> set[str]:
    """Nomi reali del template (import, def, argomenti, riferimenti)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(_import_names(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return names


def _markers(source: str) -> list[str]:
    return [m.group("text") for line in source.splitlines()
            if (m := _MARKER_RE.match(line))]


def _score(task: str, keywords: tuple[str, ...]) -> int:
    text = task.lower()
    return sum(1 for word in keywords if word.strip() in text)


def _pick(task: str) -> tuple[str | None, str]:
    ranked = sorted(
        ((_score(task, spec["keywords"]), name)
         for name, spec in _TEMPLATES.items()),
        key=lambda pair: (-pair[0], pair[1]),
    )
    best, name = ranked[0]
    if best == 0:
        return None, (
            "nessuna parola chiave riconosciuta: il planner non inventa "
            "architetture, usa un task dichiarativo con template noto")
    if len(ranked) > 1 and ranked[1][0] == best:
        rivals = ", ".join("`" + n + "`" for score, n in ranked
                           if score == best)
        return None, "template ambiguo (" + rivals + "): specifica meglio il task"
    return name, ""


def plan_slots(task: str) -> SlotPlan:
    """Produce il piano per un task; rifiuta con motivo se non è sicuro."""
    task = str(task or "").strip()
    if not task:
        return SlotPlan(task, None, (), True, "task vuoto")
    name, reason = _pick(task)
    if name is None:
        return SlotPlan(task, None, (), True, reason)

    spec = _TEMPLATES[name]
    path = TEMPLATE_DIR / name
    if not path.is_file() or not TEST_FILE.is_file():
        return SlotPlan(task, name, (), True,
                        f"template o file di test mancante: {name}")
    try:
        source = path.read_text(encoding="utf-8")
        test_source = TEST_FILE.read_text(encoding="utf-8")
        names = _template_names(source)
        markers = _markers(source)
    except (OSError, SyntaxError) as exc:
        return SlotPlan(task, name, (), True, f"template non leggibile: {exc}")

    if len(markers) != len(spec["slots"]):
        return SlotPlan(
            task, name, (), True,
            f"il template {name} ha {len(markers)} marker `# SLOT:`, "
            f"il planner ne conosce {len(spec['slots'])}: aggiornare le "
            "definizioni invece di indovinare")

    slots: list[SlotSpec] = []
    for index, (anchor, kind, ref, instruction) in enumerate(spec["slots"]):
        # Il test di un template copre tutti i suoi slot: usare un indice
        # falso would sembrare un node-id parametrizzato inesistente.
        test_id = spec["test"]
        if kind not in ALLOWED_KINDS:
            return SlotPlan(task, name, (), True,
                            f"kind non ammesso per `{anchor}`: {kind}")
        if ref not in names:
            return SlotPlan(
                task, name, (), True,
                f"ref `{ref}` per `{anchor}` non presente nel template")
        if spec["test"] not in test_source:
            return SlotPlan(
                task, name, (), True,
                f"test `{spec['test']}` assente in tests/test_gui_templates.py")
        slots.append(SlotSpec(
            anchor=anchor,
            kind=kind,
            marker=markers[index],
            refs=(ref,),
            instruction=instruction,
            test=test_id,
        ))
    if not slots:
        return SlotPlan(task, name, (), True, "nessuno slot prodotto")
    return SlotPlan(task, name, tuple(slots), False, "")
