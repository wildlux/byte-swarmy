"""security_scan.py — scan statico di sicurezza per byte-swarmy.

Cerca pattern pericolosi su tutti i .py del repo:
  - eval/exec/compile su input dinamico
  - os.system, subprocess con shell=True, Popen(shell=True)
  - pickle.load(s), yaml.load senza Loader
  - segreti hardcoded (password/token/secret/api_key = "...")
  - SQL stringato (f-string/%/+ in execute)
  - assert fuori da tests/ (rimossi con -O)
  - file .bak / backup / merge-conflict markers
  - file > 1 MB tracciati da git
  - open() su path potenzialmente controllato dall'utente (euristico)

Uso:
    .venv/bin/python tools/security_scan.py
    .venv/bin/python tools/security_scan.py GUI/ CORE/
    .venv/bin/python tools/security_scan.py --json
Codici: 0 pulito, 1 warning, 2 errore.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "venv", "__pycache__", ".git", "logs", "backups", "IMG",
        "node_modules", ".pytest_cache"}

SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|auth[_-]?token)\b"
    r"\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
)
# esclude placeholder espliciti
PLACEHOLDER_RE = re.compile(r"(?i)example|placeholder|xxx|changeme|your[_-]|<[^>]*>")


@dataclass
class Finding:
    path: str
    line: int
    level: str
    code: str
    msg: str

    def fmt(self) -> str:
        tag = {"info": "i", "warn": "W", "error": "E"}[self.level]
        return f"[{tag}] {self.path}:{self.line}  {self.code}  {self.msg}"


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


def _check_file(path: Path, findings: List[Finding]) -> None:
    rel = str(path.relative_to(ROOT))
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    lines = src.splitlines()

    # ── riga per riga ──────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        if SECRET_RE.search(line) and not PLACEHOLDER_RE.search(line):
            findings.append(Finding(rel, i, "error", "S001",
                                    "segreto hardcoded (verifica e sposta in env/config)"))
        if (line.startswith("<<<<<<<") or line.strip() == "======="
                or line.startswith(">>>>>>>")):
            findings.append(Finding(rel, i, "error", "S002",
                                    "marker di merge conflict"))

    # ── AST ────────────────────────────────────────────────────────
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return

    for node in ast.walk(tree):
        # eval/exec/compile
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("eval", "exec", "compile"):
            findings.append(Finding(rel, node.lineno,
                                    "warn" if rel.startswith("tests/") else "error",
                                    "S010",
                                    f"{node.func.id}() su input potenzialmente dinamico"))
        # os.system
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "system" \
                and isinstance(node.func.value, ast.Name) \
                and node.func.value.id == "os":
            findings.append(Finding(rel, node.lineno, "error", "S011",
                                    "os.system() — usa subprocess con lista argomenti"))
        # subprocess con shell=True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("run", "Popen", "call", "check_output",
                                       "check_call"):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value is True:
                    findings.append(Finding(rel, node.lineno, "error", "S012",
                                            "subprocess con shell=True"))
        # assert fuori da tests/
        if isinstance(node, ast.Assert) and not rel.startswith("tests/"):
            findings.append(Finding(rel, node.lineno, "warn", "S013",
                                    "assert in codice non-test (rimosso con -O)"))
        # SQL stringato
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "execute":
            # f-string o concatenazione o % nel primo arg
            if node.args:
                a0 = node.args[0]
                if isinstance(a0, ast.JoinedStr):
                    findings.append(Finding(rel, node.lineno, "error", "S014",
                                            "execute() con f-string (SQL injection)"))
                elif isinstance(a0, ast.BinOp) and isinstance(a0.op, (ast.Mod, ast.Add)):
                    findings.append(Finding(rel, node.lineno, "warn", "S014",
                                            "execute() con interpolazione stringa"))
        # open() su variabile (euristico)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "open" and node.args \
                and not isinstance(node.args[0], ast.Constant):
            findings.append(Finding(rel, node.lineno, "info", "S015",
                                    "open() su path non costante — verifica traversal"))
        # pickle.load(s) e yaml.load senza Loader — AST-based (no falsi
        # positivi su docstring/commenti).
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("load", "loads") and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "pickle":
                    findings.append(Finding(rel, node.lineno, "warn", "S004",
                                            "pickle.load(s) — rischio RCE su input non fidato"))
                if node.func.value.id == "yaml":
                    has_loader = any(kw.arg == "Loader" for kw in node.keywords)
                    if not has_loader:
                        findings.append(Finding(rel, node.lineno, "warn", "S003",
                                                "yaml.load senza Loader (usa SafeLoader)"))


def _repo_hygiene(findings: List[Finding]) -> None:
    # file .bak / backup
    for p in ROOT.rglob("*.bak*"):
        if any(part in SKIP for part in p.parts):
            continue
        findings.append(Finding(str(p.relative_to(ROOT)), 1, "warn", "S020",
                                "file di backup tracciabile (.bak)"))
    for p in ROOT.rglob("*.pyc"):
        if any(part in SKIP for part in p.parts):
            continue
        findings.append(Finding(str(p.relative_to(ROOT)), 1, "warn", "S021",
                                "bytecode .pyc nel repo"))
    # merge markers (tutti i file testo)
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in SKIP for part in p.parts):
            continue
        if p.suffix in (".png", ".jpg", ".pdf", ".db", ".sqlite", ".ico"):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(txt.splitlines(), 1):
            if line.startswith("<<<<<<<") or line.startswith(">>>>>>>"):
                findings.append(Finding(str(p.relative_to(ROOT)), i, "error",
                                        "S002", "marker di merge conflict"))
    # file grandi tracciati
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-s"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        out = ""
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        size = int(parts[3]) if parts[3].isdigit() else 0
        if size > 1_000_000:
            findings.append(Finding(parts[3] if False else parts[-1], 1, "warn",
                                    "S022", f"file tracciato grande ({size//1024} KB)"))
    # segreti nello staged diff
    try:
        diff = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--cached"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        diff = ""
    for i, line in enumerate(diff.splitlines(), 1):
        if line.startswith("+") and not line.startswith("+++"):
            if SECRET_RE.search(line) and not PLACEHOLDER_RE.search(line):
                findings.append(Finding("(staged)", i, "error", "S001",
                                        "segreto nel diff staged"))


def _is_nosec(f: Finding) -> bool:
    """True se la riga sorgente contiene un marcatore # nosec."""
    if f.path in ("(staged)",) or f.path.startswith("("):
        return False
    p = ROOT / f.path
    if not p.is_file():
        return False
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return False
    if 1 <= f.line <= len(lines):
        window = lines[f.line - 1:f.line + 1]
        return any("# nosec" in ln for ln in window)
    return False

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="scan statico di sicurezza")
    ap.add_argument("targets", nargs="*", default=["."])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)

    findings: List[Finding] = []
    for f in _py_files(args.targets):
        _check_file(f, findings)
    _repo_hygiene(findings)

    findings = [f for f in findings if not _is_nosec(f)]

    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]

    if args.json:
        print(json.dumps([{
            "path": f.path, "line": f.line, "level": f.level,
            "code": f.code, "msg": f.msg,
        } for f in findings], indent=2, ensure_ascii=False))
    else:
        for f in sorted(findings, key=lambda x: (x.path, x.line, x.code)):
            print(f.fmt())
        print(f"\n{len(findings)} finding — {len(errors)} errori, "
              f"{len(warns)} warning")

    if errors:
        return 2
    if warns and args.strict:
        return 2
    if warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
