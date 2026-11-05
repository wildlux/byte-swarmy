"""repo_map.py — mappa dinamica del repo per gli agenti.

Genera una fotografia compatta della struttura (ruoli aree, moduli con
docstring, file ROCQ/caldi, dir runtime) per orientare una sessione
senza esplorare il tree da capo. Solo stdlib: ast + pathlib.

Uso:
    .venv/bin/python tools/repo_map.py             # stampa a stdout
    .venv/bin/python tools/repo_map.py --out state/repo_map.md
    .venv/bin/python tools/repo_map.py --json      # per scripting
    .venv/bin/python tools/repo_map.py --days 3    # soglia "caldi"
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "logs", "backups", "IMG", "node_modules",
}
# Dir di runtime: contate, non dettagliate (binari/log/db).
RUNTIME_DIRS = ("CONFIG", "state", "tasks", "project", "data")

# Ruoli statici: orientamento immediato senza leggere i file.
AREA_ROLES: Dict[str, str] = {
    "CORE": "orchestratore, worker, tools, code SQLite, audio/intent bridge",
    "GUI": "PyQt6: plancia, pannelli, tema QSS in GUI/theme/",
    "MONITORING": "Timestral, thermal manager, predizione EMA",
    "SAFETY": "pitone security.py + sandbox bubblewrap (entrare, mai uscire)",
    "INTENT": "router 28 intent × 3 lingue (rapidfuzz)",
    "CONFIG": "config runtime (actors.json, scheduled_tasks.json, …)",
    "tests": "pytest + unittest; E2E live con skip su pause.flag",
    "DOCS": "todo.md, IMPLEMENTED.md, AGENT.md, specifiche",
    "scripts": "sync.sh (push manuale) + setup/",
    "tools": "travasa_todo.py, repo_map.py, capture usbmon",
}


@dataclass
class FileInfo:
    path: str
    size_kb: float
    age_days: float
    doc: str = ""
    classes: List[str] = field(default_factory=list)
    functions: int = 0

    def line(self) -> str:
        col = f"{self.size_kb:6.1f}K {self.age_days:5.1f}g"
        head = f"{col}  {self.path:<46}"
        if self.doc:
            return f"{head} {self.doc[:70]}"
        if self.classes:
            return f"{head} [{', '.join(self.classes[:3])}]"
        return head


def _walk_dirs() -> List[Path]:
    keys = [d for d in AREA_ROLES if (ROOT / d).is_dir()]
    keys += [d.name for d in ROOT.iterdir()
             if d.is_dir() and d.name not in keys
             and d.name not in SKIP_DIRS and not d.name.startswith(".")]
    return sorted(set(keys))


def _describe(path: Path) -> Tuple[str, List[str], int]:
    """Docstring (prima riga) + classi top-level via AST. Fail-soft."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError, ValueError):
        return "", [], 0
    doc = ""
    try:
        d = ast.get_docstring(tree)
        if d:
            doc = " ".join(d.split())
    except Exception:
        doc = ""
    classes: List[str] = []
    functions = 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions += 1
    return doc, classes, functions


def collect(days: float) -> Tuple[List[str], List[FileInfo], List[FileInfo]]:
    """Ritorna (righe tree, file doc, file caldi)."""
    now = time.time()
    tree_lines: List[str] = []
    docs: List[FileInfo] = []
    hot: List[FileInfo] = []
    for dname in _walk_dirs():
        d = ROOT / dname
        tree_lines.append(f"## {dname}/ — {AREA_ROLES.get(dname, '')}")
        entries = sorted(p for p in d.iterdir() if p.is_file())
        for p in entries:
            rel = str(p.relative_to(ROOT))
            st = p.stat(follow_symlinks=False)
            age = max(0.0, (now - st.st_mtime) / 86_400)
            info = FileInfo(rel, st.st_size / 1024, age)
            if p.suffix == ".py":
                info.doc, info.classes, info.functions = _describe(p)
                docs.append(info)
            tree_lines.append("  " + rel)
            if age <= days:
                hot.append(info)
        tree_lines.append("")
    return tree_lines, docs, hot


def _runtime_line() -> str:
    parts = []
    for name in RUNTIME_DIRS:
        d = ROOT / name
        if d.is_dir():
            n = sum(1 for p in d.rglob("*") if p.is_file())
            parts.append(f"{name}/{n}")
    return "  ".join(parts)


def _git_status(timeout: float = 5.0) -> Tuple[int, List[str]]:
    """(files modificati/non tracciati, ultime git log one-line)."""
    try:
        st = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=timeout, check=True,
        ).stdout.splitlines()
        log = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--oneline", "-3"],
            capture_output=True, text=True, timeout=timeout, check=True,
        ).stdout.splitlines()
        return len(st), st[:12] + log
    except (subprocess.SubprocessError, OSError):
        return -1, []


def render(days: float, as_json: bool) -> str:
    tree_lines, docs, hot = collect(days)
    dirty, git_info = _git_status()
    if as_json:
        payload = {
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "areas": AREA_ROLES,
            "python_modules": [vars(i) | {} for i in docs],
            "hot_files_days": days,
            "hot": [i.path for i in hot],
            "git_dirty_files": dirty,
            "git_status_head": [l for l in git_info if l and not l.startswith("[")],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    out: List[str] = []
    out.append("# 🗺️ repo_map — fotografia del repository")
    out.append("")
    out.append(f"_Generata {time.strftime('%Y-%m-%d %H:%M:%S')} · "
               f"interprete `.venv/bin/python` · rigenera con "
               f"`.venv/bin/python tools/repo_map.py --out state/repo_map.md`_")
    out.append("")
    out.append(f"**Git:** {' ⚠ ' + str(dirty) + ' file modificati' if dirty else 'tree pulito'}"
               + (" · " + " | ".join(git_info[-3:]) if git_info else ""))
    out.append("")
    out.append(f"**Dir runtime:** {_runtime_line()}")
    out.append("")
    out.extend(tree_lines)
    out.append(f"## File .py modificati negli ultimi {days:g} giorni "
               f"(caldi — attenzione a regressioni)")
    for i in sorted(hot, key=lambda x: x.age_days)[:15]:
        out.append("  " + i.line())
    if not hot:
        out.append("  (nessuno)")
    out.append("")
    out.append("_Comandi rapidi: vedi DOCS/AGENT.md → Shell Commands._")
    return "\n".join(out) + "\n"


def main(argv: List[str]) -> int:
    days = 7.0
    as_json = "--json" in argv
    out_path: Optional[Path] = None
    if "--days" in argv:
        i = argv.index("--days")
        if i + 1 < len(argv):
            days = float(argv[i + 1])
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            out_path = Path(argv[i + 1])
            if not out_path.is_absolute():
                out_path = ROOT / out_path
    text = render(days if days else 7.0, as_json)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"repo_map → {out_path} ({len(text)} caratteri)")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
