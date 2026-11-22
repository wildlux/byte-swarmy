"""CORE/dead_code.py — rilevamento deterministico di codice morto (report-only).

Analizza file Python con ``ast`` e restituisce candidati: funzioni, metodi,
classi e import che non risultano referenziati altrove. **Non modifica nulla**:
la decisione finale spetta sempre all'utente, dopo verifica con
``find_references`` / ``get_call_graph`` (dynamic dispatch e hook di framework
possono dare falsi positivi).

Uso::

    from CORE.dead_code import scan, format_report
    findings = scan(".")
    print(format_report(findings, "."))
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {
    ".git", ".venv", "__pycache__", "data", "node_modules",
    "build", "dist", ".mypy_cache", ".pytest_cache",
}

# Entry point canonici e hook di framework: richiamati dall'esterno, quindi
# l'assenza di chiamate nel sorgente NON significa codice morto.
_ENTRY_PREFIXES = (
    "main", "run", "start", "stop", "tick", "execute", "handle", "process",
    "setup", "teardown", "test_", "is_", "get_", "set_", "has_", "on_",
    "visit_",  # ast.NodeVisitor / QStyledItemDelegate: dynamic dispatch
)
_FRAMEWORK_HOOKS = {
    "mousePressEvent", "mouseReleaseEvent", "mouseMoveEvent", "mouseDoubleClickEvent",
    "enterEvent", "leaveEvent", "keyPressEvent", "keyReleaseEvent", "wheelEvent",
    "resizeEvent", "paintEvent", "closeEvent", "dragEnterEvent", "dragMoveEvent",
    "dropEvent", "contextMenuEvent", "focusInEvent", "focusOutEvent", "showEvent",
    "hideEvent", "timerEvent", "event", "eventFilter", "sizeHint", "minimumSizeHint",
    "__init__", "__call__", "__str__", "__repr__", "__eq__", "__hash__",
}


def _iter_py_files(root: Path) -> list[Path]:
    """File .py sotto root, ordinati, escludendo directory generate."""
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    out = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _is_candidate(name: str) -> bool:
    """Nome pubblico e non appartenente a entry point/hook noti."""
    if not name or name.startswith("_"):
        return False
    if name in _FRAMEWORK_HOOKS:
        return False
    if any(name.startswith(prefix) or name == prefix.rstrip("_")
           for prefix in _ENTRY_PREFIXES):
        return False
    return True


class _Collector(ast.NodeVisitor):
    """Raccoglie definizioni, riferimenti e import in un insieme di file."""

    def __init__(self, root: Path):
        self.root = root
        self.definitions: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
        self.used: set[str] = set()
        self.imports: list[tuple[str, str, int, str]] = []
        self._path = root
        self._type_checking = 0

    def scan_file(self, path: Path) -> None:
        self._path = path
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, ValueError):
            return
        self.visit(tree)

    # --- definizioni ---
    def _record(self, node, kind: str) -> None:
        if not _is_candidate(node.name):
            return
        # Qualsiasi decoratore indica un framework (route, slot, property,
        # override): la chiamata può avvenire fuori dal codice sorgente.
        if getattr(node, "decorator_list", None):
            return
        self.definitions[node.name].append(
            (_rel(self._path, self.root), node.lineno, kind))

    def visit_FunctionDef(self, node):
        self._record(node, "funzione")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._record(node, "funzione")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._record(node, "classe")
        self.generic_visit(node)

    # --- riferimenti ---
    def visit_Name(self, node):
        self.used.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        self.used.add(node.attr)
        self.generic_visit(node)

    def visit_keyword(self, node):
        if node.arg:
            self.used.add(node.arg)
        self.generic_visit(node)

    # --- import ---
    def visit_Import(self, node):
        if not self._type_checking and self._path.name != "__init__.py":
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound and not bound.startswith("_"):
                    self.imports.append(
                        (bound, _rel(self._path, self.root), node.lineno, "import"))

    def visit_ImportFrom(self, node):
        if node.module == "__future__" or self._type_checking:
            return
        if self._path.name == "__init__.py":  # re-export intenzionale
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name
            if bound and not bound.startswith("_"):
                self.imports.append(
                    (bound, _rel(self._path, self.root), node.lineno, "import"))

    def visit_If(self, node):
        is_tc = "TYPE_CHECKING" in ast.dump(node.test)
        if is_tc:
            self._type_checking += 1
        self.generic_visit(node)
        if is_tc:
            self._type_checking -= 1


def scan(path: str | Path = ".", *, include_imports: bool = True) -> list[dict]:
    """Restituisce i candidati codice morto sotto ``path`` (sola lettura).

    Ogni voce è un dict con ``name``, ``kind``, ``file``, ``line`` e
    ``message``. L'ordine è deterministico (file, riga, nome).
    """
    root = Path(path)
    try:
        files = _iter_py_files(root)
    except (OSError, ValueError):
        return []
    if not files:
        return []
    base = root if root.is_dir() else root.parent

    collector = _Collector(base)
    for file in files:
        collector.scan_file(file)

    findings = []
    for name, defs in collector.definitions.items():
        if name in collector.used:
            continue
        for rel, line, kind in defs:
            findings.append({
                "type": "dead_code",
                "name": name,
                "kind": kind,
                "file": rel,
                "line": line,
                "message": f"{kind.capitalize()} '{name}' definito/a ma mai referenziato/a",
            })
    if include_imports:
        for name, rel, line, kind in collector.imports:
            if name in collector.used:
                continue
            findings.append({
                "type": "dead_code",
                "name": name,
                "kind": kind,
                "file": rel,
                "line": line,
                "message": f"Import '{name}' non referenziato (possibile re-export)",
            })
    findings.sort(key=lambda f: (f["file"], f["line"], f["name"]))
    return findings


def format_report(findings: list[dict], path: str = ".", limit: int = 60) -> str:
    """Formatta il report per il tool: testo stabile, nessuna modifica."""
    if not findings:
        return f"CODICE MORTO — {path}: nessun candidato rilevato."
    lines = [
        f"CODICE MORTO — report SOLO LETTURA per {path}",
        f"Candidati: {len(findings)} (mostrati: {min(limit, len(findings))})",
    ]
    for item in findings[:limit]:
        lines.append(
            f"- [{item['kind']}] {item['file']}:{item['line']} "
            f"{item['name']} — {item['message']}")
    if len(findings) > limit:
        lines.append(f"... altri {len(findings) - limit} candidati (non mostrati)")
    lines.append(
        "Verifica con find_references(symbol) prima di rimuovere: "
        "dynamic dispatch/hook possono dare falsi positivi. "
        "Questo tool NON cancella nulla.")
    return "\n".join(lines)


__all__ = ["scan", "format_report"]
