#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travasa_todo.py — travasa le voci completate da `todo.md` a `IMPLEMENTED.md`.

La regola operativa del repo (flusso unidirezionale):
    il task nasce in `todo.md` → si esegue → si registra in
    `IMPLEMENTED.md` → si cancella da `todo.md`.

Questo tool automatizza l'ultimo passaggio:
  1. trova le righe `- [x]` in todo.md (+ le righe di continuazione
     indentate che ne descrivono i dettagli);
  2. le sposta in una sezione "Completati (spostati da todo.md)" di
     IMPLEMENTED.md, senza toccare le sezioni storiche (Cicli, …);
  3. non crea doppioni: se la voce è già registrata in IMPLEMENTED.md la
     rimuove solo da todo.md (idempotente, rieseguibile).

Uso:
    python travasa_todo.py              # esegue lo travaso sul repo qui
    python travasa_todo.py --dry-run    # mostra solo cosa farebbe
    python travasa_todo.py <dir>        # opera su un altro repo

Dopo lo travaso, `todo.md` contiene solo voci `- [ ]` (aperte).
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

CHECKED = re.compile(r"^\s*-\s+\[x\]\s*")     # voce completata
SECTION = re.compile(r"^##\s+")               # sezione markdown

MARKER = "Completati (spostati da todo.md"


def _split_item(lines: list[str], i: int) -> tuple[str, int]:
    """Ritorna il blocco dell'item in `i` (con righe di continuazione
    indentate) e l'indice della prima riga dopo il blocco."""
    block = [lines[i]]
    j = i + 1
    while j < len(lines):
        line = lines[j]
        if not line.strip():
            break
        if SECTION.match(line) or line.lstrip().startswith("- ["):
            break
        if line.startswith(" ") or line.startswith("\t"):
            block.append(line)
            j += 1
        else:
            break
    return "\n".join(block), j


def _rstrip_blank(lines: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def travasa(todo_path: Path, impl_path: Path, dry_run: bool = False) -> int:
    todo_lines = todo_path.read_text(encoding="utf-8").splitlines()
    impl_text = impl_path.read_text(encoding="utf-8")

    moved: list[str] = []
    kept: list[str] = []
    i = 0
    while i < len(todo_lines):
        if CHECKED.match(todo_lines[i]):
            block, i = _split_item(todo_lines, i)
            moved.append(block)
        else:
            kept.append(todo_lines[i])
            i += 1

    if not moved:
        print("todo.md: nessuna voce `- [x]` da trasvasare. ✔")
        return 0

    if dry_run:
        print(f"travaso dry-run — {len(moved)} voce/i in attesa:")
        for block in moved:
            print("  " + block.splitlines()[0].strip())
        return len(moved)

    # idempotente: salta le voci già registrate (match sulla prima riga)
    known = {ln.strip() for ln in impl_text.splitlines() if ln.strip()}
    fresh = [b for b in moved
             if b.splitlines()[0].strip() not in known]
    dup = len(moved) - len(fresh)

    if fresh:
        parts = []
        if MARKER not in impl_text:
            parts.append(f"\n## 📋 {MARKER}) — "
                         f"{datetime.date.today().isoformat()}\n")
        parts.extend(b + "\n" for b in fresh)
        impl_path.write_text(
            impl_text.rstrip() + "\n" + "\n".join(parts) + "\n",
            encoding="utf-8")

    todo_path.write_text(
        "\n".join(_rstrip_blank(kept)) + "\n", encoding="utf-8")

    print(f"travaso: {len(fresh)} voce/i → IMPLEMENTED.md; "
          f"{dup} già registrata/e (ignorata/e). "
          f"todo.md ora ha solo voci aperte. ✔")
    return len(fresh)


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    positional = [a for a in argv if not a.startswith("-")]
    root = Path(positional[0] if positional else ".").resolve()
    # Dalla consolidation docs (2026-11-05) todo.md e IMPLEMENTED.md vivono
    # in DOCS/; accettiamo anche la radice per backward compat.
    todo = root / "todo.md"
    impl = root / "IMPLEMENTED.md"
    if not todo.exists() and (root / "DOCS" / "todo.md").exists():
        todo = root / "DOCS" / "todo.md"
        impl = root / "DOCS" / "IMPLEMENTED.md"
    if not todo.exists() or not impl.exists():
        print(f"Manca todo.md o IMPLEMENTED.md in {root}", file=sys.stderr)
        return 1
    return 0 if travasa(todo, impl, dry_run=dry_run) is not None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
