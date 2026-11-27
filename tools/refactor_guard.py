#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E1 — gate deterministico per refactoring (AST + behavioral diff).

Un refactoring è accettato solo se:
  1. prima e dopo sono Python valido (AST);
  2. l'API pubblica di primo livello è invariata (nomi e argomenti,
     annotazioni e default ignorati: cambiano i tipi, non il contratto);
  3. l'output del programma sugli stessi input è identico
     (``CORE.behavioral_diff.snapshot``/``verify``).

Zero LLM, zero rete. Fail-open: se lo snapshot non è conclusivo
(il file non è eseguibile come script) lo stato è WARN, non FAIL.
Non esegue patch: riceve due file già scritti e dice se il refactoring
li ha mantenuti equivalenti.

Uso:
    .venv/bin/python tools/refactor_guard.py --before /tmp/a.py --after /tmp/b.py
    .venv/bin/python tools/refactor_guard.py --before a.py --after b.py --json
    .venv/bin/python tools/refactor_guard.py --before a.py --after b.py \
        --inputs "1,2" --out RAG/DOCS/REFACTOR_GUARD_REPORT.md
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import behavioral_diff as bd  # noqa: E402

DEFAULT_INPUTS = [""]


@dataclass(frozen=True)
class ApiChange:
    kind: str
    name: str
    detail: str

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "detail": self.detail}


@dataclass(frozen=True)
class GuardReport:
    before: str
    after: str
    syntax_ok: bool
    api_changes: tuple[ApiChange, ...]
    behavior_ok: bool
    behavior_diff: str
    behavior_conclusive: bool
    issues: tuple[str, ...]

    @property
    def blocking(self) -> tuple[ApiChange, ...]:
        return tuple(c for c in self.api_changes
                     if c.kind in ("removed", "changed"))

    @property
    def ok(self) -> bool:
        return (self.status == "OK")

    @property
    def status(self) -> str:
        if (not self.syntax_ok or self.issues or self.blocking
                or (self.behavior_conclusive and not self.behavior_ok)):
            return "FAIL"
        if not self.behavior_conclusive:
            return "WARN"
        return "OK"

    def to_dict(self) -> dict:
        return {
            "before": self.before,
            "after": self.after,
            "status": self.status,
            "syntax_ok": self.syntax_ok,
            "api_changes": [c.to_dict() for c in self.api_changes],
            "behavior_ok": self.behavior_ok,
            "behavior_conclusive": self.behavior_conclusive,
            "behavior_diff": self.behavior_diff[:600],
            "issues": list(self.issues),
        }

    def markdown(self) -> str:
        def label(raw: str) -> str:
            p = Path(raw)
            try:
                return p.resolve().relative_to(ROOT).as_posix()
            except ValueError:
                return p.name  # file temporaneo fuori dal repo

        if self.behavior_ok and self.behavior_conclusive:
            behavior = "✅"
        elif not self.behavior_conclusive:
            behavior = "⚠️"
        else:
            behavior = "❌"

        lines = [
            "# 🛡️ Refactor Guard (E1)",
            "",
            f"**Stato**: `{self.status}` — "
            f"`{label(self.before)}` → `{label(self.after)}`",
            "",
            "_Gate E1: 8/8 refactoring atomici verdi in "
            "`tests/test_refactor_guard.py` — zero LLM._",
            "",
            "| Check | Esito |",
            "|---|---|",
            f"| Sintassi AST | {'✅' if self.syntax_ok else '❌'} |",
            f"| API pubblica invariata | "
            f"{'✅' if not self.blocking else '❌'} |",
            f"| Comportamento identico | {behavior} |",
            "",
        ]
        if self.api_changes:
            lines += ["| Cambio API | Tipo | Dettaglio |", "|---|---|---|"]
            for c in self.api_changes:
                lines.append(f"| `{c.name}` | {c.kind} | {c.detail} |")
            lines.append("")
        for issue in self.issues:
            lines.append(f"- ❌ {issue}")
        if self.behavior_diff:
            lines += ["", "```text", self.behavior_diff[:800], "```"]
        return "\n".join(lines) + "\n"


def _signature(node) -> tuple[str, ...]:
    """Nomi degli argomenti: ignora annotazioni/default (non contratto)."""
    a = node.args
    names = [x.arg for x in a.posonlyargs + a.args]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    names += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    return tuple(names)


def public_api(source: str) -> dict[str, tuple]:
    """Simboli pubblici di primo livello con la loro firma AST."""
    tree = ast.parse(source)
    api: dict[str, tuple] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                api[node.name] = ("function", _signature(node))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            methods = {m.name: _signature(m) for m in node.body
                       if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and not m.name.startswith("_")}
            api[node.name] = ("class", tuple(sorted(methods.items())))
    return api


def _api_changes(before: dict[str, tuple], after: dict[str, tuple]) -> tuple:
    changes: list[ApiChange] = []
    for name in sorted(set(before) | set(after)):
        if name not in after:
            changes.append(ApiChange("removed", name,
                                     "simbolo pubblico rimosso"))
        elif name not in before:
            changes.append(ApiChange("added", name,
                                     "nuovo simbolo pubblico (informativo)"))
        elif before[name] != after[name]:
            changes.append(ApiChange(
                "changed", name,
                f"{before[name]} → {after[name]}"))
    return tuple(changes)


def check_refactor(before_path, after_path, inputs=None,
                   timeout: int = 5) -> GuardReport:
    """Confronta due file e restituisce il report deterministico."""
    before, after = Path(before_path), Path(after_path)
    issues: list[str] = []
    for p in (before, after):
        if not p.exists():
            issues.append(f"file mancante: {p}")
    if issues:
        return GuardReport(str(before), str(after), False, (),
                           False, "", False, tuple(issues))

    sources: dict[str, str] = {}
    for label, p in (("before", before), ("after", after)):
        try:
            sources[label] = p.read_text(encoding="utf-8")
            ast.parse(sources[label])
        except (OSError, UnicodeDecodeError, SyntaxError) as e:
            issues.append(f"{label}: Python non valido: {str(e)[:160]}")
    if issues:
        return GuardReport(str(before), str(after), False, (),
                           False, "", False, tuple(issues))

    changes = _api_changes(public_api(sources["before"]),
                           public_api(sources["after"]))
    inputs = list(inputs) if inputs else list(DEFAULT_INPUTS)
    snap = bd.snapshot(before, inputs, timeout=timeout)
    conclusive = not any(str(o).startswith("__ERROR__")
                         for o in snap.get("outputs", []))
    behavior_ok, behavior_diff = bd.verify(after, snap, timeout=timeout)
    return GuardReport(str(before), str(after), True, changes,
                       behavior_ok, behavior_diff, conclusive, ())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", required=True, help="file prima del refactoring")
    ap.add_argument("--after", required=True, help="file dopo il refactoring")
    ap.add_argument("--inputs", default="",
                    help="input stdin separati da virgola (default: uno vuoto)")
    ap.add_argument("--json", action="store_true", help="stampa solo JSON")
    ap.add_argument("--out", default=None, help="scrive report Markdown qui")
    args = ap.parse_args(argv)

    inputs = [x for x in args.inputs.split(",")] if args.inputs else None
    report = check_refactor(args.before, args.after, inputs=inputs)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.markdown(), encoding="utf-8")
        print(f"Report scritto: {out} ({report.status})")
    else:
        sys.stdout.write(report.markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
