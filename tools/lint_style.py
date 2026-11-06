"""lint_style.py — stile, leggibilità e guardia tema per byte-swarmy.

Controlli statici (solo stdlib, ast) su tutti i .py del repo:
  - lunghezza riga (>100 warn, >120 err)
  - trailing whitespace / tab / newline finale
  - except nudo (warn)
  - print() in CORE/ (warn: usare logging)
  - funzioni >60 righe (warn), nesting >4 (warn)
  - moduli pubblici senza docstring (info)
  - colori hardcoded inline nei pannelli GUI (guardia anti-regressione tema)
  - import potenzialmente inutilizzati (euristica)
  - marcatori TODO/FIXME/HACK/XXX (info)

Uso:
    .venv/bin/python tools/lint_style.py            # tutto il repo
    .venv/bin/python tools/lint_style.py GUI/       # solo un'area
    .venv/bin/python tools/lint_style.py --json     # per CI
    .venv/bin/python tools/lint_style.py --strict   # warning = errore
Codici: 0 pulito, 1 warning, 2 errore.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "venv", "__pycache__", ".git", "logs", "backups", "IMG",
        "node_modules", ".pytest_cache", "TEST_GUI_SEPARATA"}

# Guardia tema: setStyleSheet in GUI con colore di testo hardcodato SENZA
# background → non sincronizzato col tema (regressione tipica).
_COLOR_INLINE = re.compile(
    r"setStyleSheet\s*\([^)]*color\s*:\s*#[0-9a-fA-F]{3,6}[^)]*\)",
    re.IGNORECASE | re.DOTALL,
)
_COLOR_WITH_BG = re.compile(r"background(?:-color)?\s*:", re.IGNORECASE)

# File esclusi dall'audit (debito noto, junk candidate — non riparare a
# mano: decidere la cancellazione con l'utente, vedi DOCS/AGENT.md).
SKIP_FILES: set = {"GUI/TEST_GUI_QT_12.py"}


@dataclass
class Finding:
    path: str
    line: int
    level: str   # info / warn / error
    code: str
    msg: str

    def fmt(self, color: bool) -> str:
        tag = {"info": "i", "warn": "W", "error": "E"}[self.level]
        prefix = f"[{tag}] {self.path}:{self.line}"
        return f"{prefix}  {self.code}  {self.msg}"


def _py_files(targets: List[str]) -> List[Path]:
    out: List[Path] = []
    for t in (targets or ["."]):
        p = Path(t)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_file():
            if p.suffix == ".py":
                out.append(p)
            continue
        if p.is_dir():
            for f in p.rglob("*.py"):
                if any(part in SKIP for part in f.parts):
                    continue
                out.append(f)
    return sorted(set(out))


def _nesting(node: ast.AST) -> int:
    depth = 0
    cur = node
    while getattr(cur, "parent", None) is not None:
        if isinstance(cur.parent, (ast.If, ast.For, ast.While, ast.With,
                                   ast.Try, ast.ExceptHandler, ast.FunctionDef,
                                   ast.AsyncFunctionDef, ast.ClassDef)):
            # solo blocchi di controllo contano
            if isinstance(cur.parent, (ast.If, ast.For, ast.While, ast.With,
                                       ast.Try, ast.ExceptHandler)):
                depth += 1
        cur = cur.parent
    return depth


def _check_file(path: Path, findings: List[Finding]) -> None:
    rel = str(path.relative_to(ROOT))
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    lines = src.splitlines()

    # ── riga per riga ──────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        if len(line) > 100:
            findings.append(Finding(rel, i, "warn", "W001",
                                    f"riga lunga ({len(line)} > 100)"))
        if line != line.rstrip():
            findings.append(Finding(rel, i, "info", "I004",
                                    "trailing whitespace"))
        if "\t" in line:
            findings.append(Finding(rel, i, "error", "E002",
                                    "tab nel sorgente (usa 4 spazi)"))
        if "TODO" in line or "FIXME" in line or "HACK" in line or "XXX" in line:
            findings.append(Finding(rel, i, "info", "I001",
                                    "marcatore TODO/FIXME/HACK/XXX"))
    if lines and not src.endswith("\n"):
        findings.append(Finding(rel, len(lines), "warn", "W003",
                                "file senza newline finale"))

    # ── AST ────────────────────────────────────────────────────────
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        findings.append(Finding(rel, e.lineno or 1, "error", "E003",
                                f"SyntaxError: {e.msg}"))
        return

    # parent pointers
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node  # type: ignore[attr-defined]

    # docstring modulo
    if not ast.get_docstring(tree):
        findings.append(Finding(rel, 1, "info", "I002",
                                "modulo senza docstring"))

    # bare except
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(Finding(rel, node.lineno, "warn", "W004",
                                    "except nudo (cattura BaseException)"))

    # print in CORE/
    if rel.startswith("CORE/"):
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"):
                findings.append(Finding(rel, node.lineno, "warn", "W005",
                                        "print() in CORE/ — usa logging"))

    # funzioni lunghe + nesting
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if end - node.lineno > 60:
                findings.append(Finding(rel, node.lineno, "warn", "W006",
                                        f"funzione lunga ({end-node.lineno+1} righe)"))
            # nesting massimo dentro la funzione
            maxd = 0
            for sub in ast.walk(node):
                if sub is node:
                    continue
                if isinstance(sub, (ast.If, ast.For, ast.While, ast.With,
                                    ast.Try, ast.ExceptHandler)):
                    # profondità relativa: conta antenati di controllo
                    d = 0
                    cur = sub
                    while cur is not node and getattr(cur, "parent", None):
                        if isinstance(cur.parent, (ast.If, ast.For, ast.While,
                                                   ast.With, ast.Try)):
                            d += 1
                        cur = cur.parent
                    maxd = max(maxd, d)
            if maxd > 4:
                findings.append(Finding(rel, node.lineno, "warn", "W007",
                                        f"nesting profondo ({maxd})"))

    # guardia tema: setStyleSheet con colore di testo hardcodato senza bg
    # Una riga del blocco setStyleSheet con marcatore `# nolint <motivo>`
    # (stesso schema di `# nosec` in security_scan.py) sopprime W010 —
    # si usa per le eccezioni visive intenzionali (overlay crediti, brand…).
    if rel.startswith("GUI/") and rel.endswith(".py"):
        for m in _COLOR_INLINE.finditer(src):
            chunk = m.group(0)
            if _COLOR_WITH_BG.search(chunk):
                continue
            ln = src[:m.start()].count("\n") + 1
            endln = ln + chunk.count("\n")
            block = lines[ln - 1:endln]
            if any("# nolint" in l for l in block):
                continue
            findings.append(Finding(rel, ln, "warn", "W010",
                                    "setStyleSheet con colore hardcodato "
                                    "senza background → non sincronizzato "
                                    "col tema"))

    # import potenzialmente inutilizzati (euristica, solo nomi semplici)
    imported: List[tuple] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    imported.append((a.asname, node.lineno))
                elif "." not in a.name:
                    imported.append((a.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.names and node.names[0].name == "*":
                continue
            for a in node.names:
                name = a.asname or a.name
                if name and name != "*":
                    imported.append((name, node.lineno))
    for name, ln in imported:
        # conta usi fuori dalla riga di import
        uses = 0
        for i, line in enumerate(lines, 1):
            if i == ln:
                continue
            if re.search(r"\b" + re.escape(name) + r"\b", line):
                uses += 1
        if uses == 0 and not name.startswith("_"):
            findings.append(Finding(rel, ln, "info", "I003",
                                    f"import possibilmente inutilizzato: {name}"))


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="lint stile/leggibilità")
    ap.add_argument("targets", nargs="*", default=["."])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="i warning contano come errore (exit 2)")
    ap.add_argument("--fix", action="store_true",
                    help="applica fix automatici sicuri (trailing ws, newline finale)")
    args = ap.parse_args(argv)

    files = _py_files(args.targets)

    fixed = 0
    if args.fix:
        for f in files:
            try:
                src = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            new = "\n".join(line.rstrip() for line in src.splitlines())
            if src.endswith("\n") or src == "":
                new += "\n"
            if new != src:
                f.write_text(new, encoding="utf-8")
                fixed += 1
        print(f"fixed {fixed} file (trailing ws + newline finale)")

    findings: List[Finding] = []
    skipped = [f for f in files if str(f.relative_to(ROOT)) in SKIP_FILES]
    files = [f for f in files if f not in skipped]
    for f in files:
        _check_file(f, findings)
    if skipped:
        for s in skipped:
            print(f"[skip] {s.relative_to(ROOT)}  (file noto come debito: "
                  "vedi SKIP_FILES in tools/lint_style.py)")

    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]
    infos = [f for f in findings if f.level == "info"]

    if args.json:
        print(json.dumps([{
            "path": f.path, "line": f.line, "level": f.level,
            "code": f.code, "msg": f.msg,
        } for f in findings], indent=2, ensure_ascii=False))
    else:
        color = sys.stdout.isatty()
        for f in sorted(findings, key=lambda x: (x.path, x.line, x.code)):
            print(f.fmt(color))
        print(f"\n{len(files)} file analizzati — "
              f"{len(errors)} errori, {len(warns)} warning, {len(infos)} info")

    if errors:
        return 2
    if warns and args.strict:
        return 2
    if warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
