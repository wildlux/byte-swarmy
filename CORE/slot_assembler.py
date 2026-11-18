"""CORE/slot_assembler.py — assembler deterministico degli slot.

SLOT-2 dell'architettura a slot: il pezzo che oggi NON esiste. Prende uno
scheletro (template) con marker e i frammenti prodotti dal 3b e produce
un file Python compilabile. Zero LLM.

Formato dello scheletro::

    \"\"\"docstring\"\"\"
    # @@imports
    # @@slot: greet
    # @@slot: main

Un marker è una riga di commento:

- ``# @@slot: <nome>`` — punto in cui inserire il frammento con
  ``anchor == "<nome>"``. L'indentazione del marker viene applicata a
  tutte le righe del frammento (slot dentro una classe/funzione).
- ``# @@imports`` — punto in cui raccogliere gli import estratti dai
  frammenti (dedupe contro quelli già presenti nello scheletro).

Gli import top-level dei frammenti vengono *sollevati* fuori dallo slot e
inseriti una sola volta; il resto del frammento resta nel punto
dell'anchor. Se ``# @@imports`` manca, gli import nuovi vanno dopo
l'ultimo import dello scheletro (o dopo la docstring).

Nessun I/O implicito: ``assemble_slots`` è puro; ``assemble_to_file``
scrive solo dove gli viene detto.
"""

from __future__ import annotations

import ast
import os
import re
import textwrap
from pathlib import Path
from typing import Mapping, Sequence

__all__ = [
    "AssemblerError",
    "assemble_slots",
    "assemble_to_file",
    "slot_anchors",
]

_SLOT_MARK = re.compile(
    r"^(?P<indent>[ \t]*)#\s*@@slot:\s*(?P<name>[A-Za-z_][\w.-]*)\s*$")
_IMPORTS_MARK = re.compile(r"^(?P<indent>[ \t]*)#\s*@@imports\s*$")


class AssemblerError(ValueError):
    """Scheletro o slot non assemblables (messaggio per il worker)."""


def slot_anchors(source: str) -> list[str]:
    """Nomi degli anchor presenti nello scheletro, in ordine di apparizione."""
    names: list[str] = []
    for line in source.splitlines():
        m = _SLOT_MARK.match(line)
        if m:
            names.append(m.group("name"))
    return names


def _imports_of(code: str, where: str) -> tuple[list[tuple[str, str]], str]:
    """Estrae gli import top-level e ritorna (import, codice_restante)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise AssemblerError(
            f"{where}: syntax error alla riga {exc.lineno}: {exc.msg}") from exc

    lines = code.splitlines()
    imports: list[tuple[str, str]] = []
    drop: set[int] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                raise AssemblerError(
                    f"{where}: gli import `from __future__` non possono "
                    "stare dentro uno slot (devono essere nello scheletro).")
            segment = "\n".join(lines[node.lineno - 1:node.end_lineno])
            imports.append((ast.dump(node), segment))
            drop.update(range(node.lineno, node.end_lineno + 1))
    kept = [line for i, line in enumerate(lines, 1) if i not in drop]
    return imports, "\n".join(kept).strip("\n")


def _indent_block(code: str, indent: str) -> list[str]:
    if not indent:
        return code.splitlines()
    return [indent + line if line.strip() else line
            for line in code.splitlines()]


def _validate_slots(slots: Sequence[Mapping]) -> dict[str, str]:
    """Valida la forma degli slot; ritorna {anchor: codice_dedent}."""
    by_anchor: dict[str, str] = {}
    for idx, slot in enumerate(slots):
        if not isinstance(slot, Mapping):
            raise AssemblerError(f"slot #{idx}: atteso dict, trovato "
                                 f"{type(slot).__name__}")
        anchor = slot.get("anchor")
        code = slot.get("code")
        if not isinstance(anchor, str) or not anchor.strip():
            raise AssemblerError(f"slot #{idx}: 'anchor' mancante o vuoto")
        if not isinstance(code, str):
            raise AssemblerError(
                f"slot '{anchor}': 'code' mancante o non stringa")
        if anchor in by_anchor:
            raise AssemblerError(f"slot duplicato: '{anchor}'")
        by_anchor[anchor] = textwrap.dedent(code).strip("\n")
    return by_anchor


def _stub_markers(source: str) -> str:
    """Sostituisce i marker con `pass` (stesse righe) per poter parsare.

    Serve agli scheletri in cui un anchor è l'unico statement di un
    blocco (es. classe con solo `# @@slot: run`): senza stub l'AST
    fallirebbe con "expected an indented block", benché il template sia
    legittimo.
    """
    out: list[str] = []
    for line in source.splitlines():
        m = _SLOT_MARK.match(line)
        if m:
            out.append(f"{m.group('indent')}pass")
        elif _IMPORTS_MARK.match(line):
            out.append("pass")
        else:
            out.append(line)
    return "\n".join(out)


def _base_imports(source: str) -> list[tuple[str, str]]:
    try:
        tree = ast.parse(_stub_markers(source))
    except SyntaxError as exc:
        raise AssemblerError(
            f"scheletro: syntax error alla riga {exc.lineno}: {exc.msg}"
        ) from exc
    lines = source.splitlines()
    imports: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append((ast.dump(node),
                            "\n".join(lines[node.lineno - 1:node.end_lineno])))
    return imports


def _insertion_index(source: str) -> int:
    """Riga (0-based) dopo cui inserire gli import, senza marker."""
    try:
        tree = ast.parse(_stub_markers(source))
    except SyntaxError:
        return 0
    lines = source.splitlines()
    idx = 0
    # shebang + eventuale coding cookie
    while idx < len(lines) and (lines[idx].startswith("#!")
                                or (idx <= 1 and "coding" in lines[idx]
                                    and lines[idx].lstrip().startswith("#"))):
        idx += 1
    if tree.body and isinstance(tree.body[0], ast.Expr) and \
            isinstance(tree.body[0].value, ast.Constant) and \
            isinstance(tree.body[0].value.value, str):
        idx = max(idx, tree.body[0].end_lineno or 0)
    last_import = max(
        (n.end_lineno or 0 for n in tree.body
         if isinstance(n, (ast.Import, ast.ImportFrom))), default=0)
    return max(idx, last_import)


def assemble_slots(base_source: str, slots: Sequence[Mapping]) -> str:
    """Inserisce gli slot nello scheletro e ritorna il sorgente assemblato.

    Raises:
        AssemblerError: anchor mancante/duplicato, slot malformato,
            frammento non parsabile o risultato non compilabile.
    """
    if not isinstance(base_source, str):
        raise AssemblerError("scheletro non è una stringa")

    anchors = slot_anchors(base_source)
    dupes = {a for a in anchors if anchors.count(a) > 1}
    if dupes:
        raise AssemblerError(
            "anchor duplicati nello scheletro: " + ", ".join(sorted(dupes)))

    by_anchor = _validate_slots(slots)
    unknown = sorted(set(by_anchor) - set(anchors))
    if unknown:
        raise AssemblerError(
            "anchor senza marker nello scheletro: " + ", ".join(unknown)
            + (f" (disponibili: {', '.join(anchors)})" if anchors else
               " (nessun marker @@slot nello scheletro)"))

    base_import_dumps = {dump for dump, _ in _base_imports(base_source)}
    new_imports: list[str] = []
    seen = set(base_import_dumps)
    slot_bodies: dict[str, list[str]] = {}

    for anchor in anchors:
        if anchor not in by_anchor:
            continue  # marker lasciato com'è: slot opzionale non fornito
        imports, body = _imports_of(by_anchor[anchor], f"slot '{anchor}'")
        for dump, segment in imports:
            if dump not in seen:
                seen.add(dump)
                new_imports.append(segment)
        slot_bodies[anchor] = body.splitlines()

    lines = base_source.splitlines()
    has_import_marker = any(_IMPORTS_MARK.match(line) for line in lines)

    if new_imports and not has_import_marker:
        at = _insertion_index(base_source)
        lines[at:at] = new_imports

    out: list[str] = []
    import_marker_done = False
    for line in lines:
        m = _SLOT_MARK.match(line)
        if m:
            anchor = m.group("name")
            if anchor in slot_bodies:
                out.extend(_indent_block(
                    "\n".join(slot_bodies[anchor]), m.group("indent")))
            else:
                out.append(line)  # slot non fornito: marker conservato
            continue
        mark = _IMPORTS_MARK.match(line)
        if mark:
            if import_marker_done:
                raise AssemblerError("marker `# @@imports` duplicato")
            if mark.group("indent"):
                raise AssemblerError(
                    "il marker `# @@imports` deve essere a livello modulo")
            out.extend(new_imports)
            import_marker_done = True
            continue
        out.append(line)

    assembled = "\n".join(out).rstrip("\n") + "\n"
    try:
        compile(assembled, "<assembled>", "exec")
    except SyntaxError as exc:
        raise AssemblerError(
            f"risultato non compilabile (riga {exc.lineno}): {exc.msg}"
        ) from exc
    return assembled


def assemble_to_file(base_path: str | Path, slots: Sequence[Mapping],
                     out_path: str | Path | None = None) -> Path:
    """Assembla e scrive il risultato (default: stesso file dello scheletro).

    Scrittura atomica; il file di destinazione non viene toccato se
    l'assembly fallisce.
    """
    base = Path(base_path)
    try:
        base_source = base.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssemblerError(f"scheletro non leggibile: {exc}") from exc
    assembled = assemble_slots(base_source, slots)
    dest = Path(out_path) if out_path is not None else base
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.slot-tmp")
    try:
        tmp.write_text(assembled, encoding="utf-8")
        os.replace(tmp, dest)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise AssemblerError(f"scrittura fallita: {exc}") from exc
    return dest
