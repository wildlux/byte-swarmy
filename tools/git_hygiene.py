"""git_hygiene.py — igiene del repository byte-swarmy.

Controlli (solo stdlib + git):
  - file non tracciati "sporchi" (.bak, .pyc, __pycache__, .DS_Store, *.orig)
  - file tracciati > 500 KB (candidati a .gitignore o LFS)
  - file tracciati senza newline finale
  - file tracciati con trailing whitespace
  - .gitignore mancante di pattern comuni
  - commit recenti con messaggi "wip"/"tmp"/"debug"
  - branch senza upstream

Uso:
    .venv/bin/python tools/git_hygiene.py
    .venv/bin/python tools/git_hygiene.py --json
Codici: 0 pulito, 1 warning.
"""
from __future__ import annotations

import argparse
import re
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent

JUNK_PATTERNS = (".bak", ".pyc", ".pyo", ".DS_Store", ".orig", ".rej")
JUNK_DIRS = ("__pycache__", ".pytest_cache", "node_modules")

COMMON_IGNORE = (".venv/", "__pycache__/", "*.pyc", "*.bak", "logs/",
                 "backups/", "state/", "tasks/", "project/")


@dataclass
class Finding:
    path: str
    level: str
    code: str
    msg: str

    def fmt(self) -> str:
        tag = "W" if self.level == "warn" else "i"
        return f"[{tag}] {self.path}  {self.code}  {self.msg}"


def _git(args: List[str], timeout: float = 15.0) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(ROOT)] + args,
            capture_output=True, text=True, timeout=timeout, check=True,
        )
        return r.stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="igiene git del repo")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    findings: List[Finding] = []

    # ── file non tracciati "sporchi" ──────────────────────────────
    status = _git(["status", "--porcelain", "--untracked-files=all"])
    for line in status.splitlines():
        if not line.strip():
            continue
        code = line[:2]
        path = line[3:].strip()
        if code == "??":
            if any(path.endswith(p) or p in path.split("/") for p in JUNK_PATTERNS) \
                    or any(d in path.split("/") for d in JUNK_DIRS):
                findings.append(Finding(path, "warn", "G001",
                                        "file non tracciato di spazzatura (rimuovi)"))

    # ── file tracciati grandi + newline/trailing ws ───────────────
    tracked = _git(["ls-files"]).splitlines()
    for rel in tracked:
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_size > 500 * 1024:
            findings.append(Finding(rel, "warn", "G002",
                                    f"file tracciato grande ({st.st_size//1024} KB)"))
        if p.suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf",
                        ".db", ".sqlite", ".ico", ".bin", ".so"):
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if data and not data.endswith(b"\n"):
            findings.append(Finding(rel, "warn", "G003",
                                    "file senza newline finale"))
        # trailing whitespace (solo su file piccoli, per non leggere mega-file)
        if st.st_size < 200 * 1024:
            text = data.decode("utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if line != line.rstrip():
                    findings.append(Finding(rel, "warn", "G004",
                                            f"trailing whitespace (riga {i})"))
                    break   # una sola segnalazione per file

    # ── .gitignore coverage ────────────────────────────────────────
    gi = ROOT / ".gitignore"
    if gi.is_file():
        gitignore = gi.read_text(encoding="utf-8", errors="ignore")
        missing = [pat for pat in COMMON_IGNORE if pat not in gitignore]
        if missing:
            findings.append(Finding(".gitignore", "warn", "G005",
                                    "pattern mancanti: " + ", ".join(missing)))
    else:
        findings.append(Finding(".gitignore", "warn", "G006", "file .gitignore assente"))

    # ── commit recenti sospetti ───────────────────────────────────
    log = _git(["log", "--oneline", "-15"])
    for line in log.splitlines():
        subj = line.split(" ", 1)[-1] if " " in line else line
        if any(re.search(r"\b" + w + r"\b", subj.lower()) for w in ("wip", "tmp", "debug", "xxx", "test123")):
            findings.append(Finding("(git log)", "warn", "G007",
                                    f"commit sospetto: {line}"))

    # ── branch senza upstream ─────────────────────────────────────
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    upstream = _git(["rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"]).strip()
    if branch and not upstream:
        findings.append(Finding("(branch)", "info", "G008",
                                f"branch '{branch}' senza upstream (push manuale)"))

    if args.json:
        print(json.dumps([{
            "path": f.path, "level": f.level, "code": f.code, "msg": f.msg,
        } for f in findings], indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(f.fmt())
        print(f"\n{len(findings)} finding")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
