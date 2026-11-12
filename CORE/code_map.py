"""CORE/code_map.py — Mappa del codice del progetto (AST → SQLite).

Idea dell'utente: un agente che usa un DATABASE per mappare il codice.
Perché funziona coi modelli piccoli: riduce le scelte libere e ancora il
modello alla realtà —

  1. PROMPT  → sezione "## PROJECT MAP" coi simboli esistenti (classi,
     metodi, firme): il modello RIUSA invece di allucinare API.
  2. VERIFICA STATICA → i nomi usati ma mai definiti (NameError latenti
     come il `coll.pop()` a livello modulo visto in Fase 2) vengono
     beccati PRIMA di eseguire, con correzione mirata.
  3. RETRIEVAL → con num_ctx limitato, la mappa dice quali simboli
     iniettare (per ora: tutta la mappa cap-ata).

Implementazione: stdlib `ast` (niente dipendenze) + SQLite per progetto
in `<progetto>/.byteswarm/codemap.db`. Rebuild INCREMENTALE per mtime:
solo i file cambiati vengono riparsi. Fail-open ovunque: senza DB o con
file non parsabili la pipeline degrada, mai crash.

M6 — signature cache: `estimate_impact` chiama `rebuild` a ogni decisione
di routing. Su progetti grandi il collo di bottiglia NON è il parsing
(gia incrementale) ma il `rglob + stat + sqlite connect` per ogni
chiamata. Cache di signature `(file_count, max_mtime_ns)` con TTL:
se il progetto non è cambiato dall'ultima chiamata, salta tutto.
"""
from __future__ import annotations

import ast
import builtins
import sqlite3
import time
from pathlib import Path

DB_DIR = ".byteswarm"
DB_NAME = "codemap.db"

# Cartelle mai mappate (artefatti/venv: nulla di "codice del progetto")
SKIP_DIRS = {".byteswarm", "__pycache__", ".venv", "venv", ".git",
             "node_modules", ".idea", ".vscode"}

MAX_MAP_CHARS = 1200  # cap della sezione nel prompt (8192 ctx: non affoga)
MAX_UNKNOWN_REPORT = 6

# M6: signature cache — se il progetto non è cambiato, rebuild è no-op.
# TTL: il worker scrive un file ogni 30 s (tick), quindi 5 s di cache
# coprono bene le chiamate ravvicinate (es. estimate_impact + render_map
# per lo stesso task). Il cache key è il path assoluto del progetto.
_BUILD_CACHE: dict[str, tuple[tuple[int, int], dict, float]] = {}
_BUILD_TTL_S = 5.0


def reset_rebuild_cache() -> None:
    """Pulisce la cache di signature (test, forzatura refresh)."""
    _BUILD_CACHE.clear()


def _project_signature(root: Path) -> tuple[int, int]:
    """(file_count, max_mtime_ns) — lettura leggera, niente parsing.

    Costo: O(N) stat() per i .py del progetto (Niente SQL, niente AST).
    Su un progetto di 500 file è ~5 ms; SQLite connect + schema +
    SELECT per-file è ~50 ms. La cache rende il caso "nessun cambio"
    (la maggioranza delle chiamate di routing) praticamente gratuito.
    """
    count = 0
    max_mtime = 0
    try:
        for p in root.rglob("*.py"):
            rel_parts = p.relative_to(root).parts
            if SKIP_DIRS & set(rel_parts):
                continue
            try:
                mtime = p.stat().st_mtime_ns
            except OSError:
                continue
            count += 1
            if mtime > max_mtime:
                max_mtime = mtime
    except Exception:
        return (-1, -1)
    return (count, max_mtime)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY, mtime INTEGER, lines INTEGER, ok INTEGER);
CREATE TABLE IF NOT EXISTS symbols (
    file TEXT, kind TEXT, name TEXT, qualname TEXT,
    signature TEXT, doc TEXT, line INTEGER);
CREATE TABLE IF NOT EXISTS calls (
    file TEXT, caller TEXT, callee TEXT, line INTEGER);
CREATE TABLE IF NOT EXISTS imports (
    file TEXT, module TEXT, names TEXT);
CREATE INDEX IF NOT EXISTS idx_sym_file ON symbols(file);
CREATE INDEX IF NOT EXISTS idx_calls_file ON calls(file);
"""


def db_path(project_root: str | Path) -> Path:
    return Path(project_root) / DB_DIR / DB_NAME


# ── Parsing AST ────────────────────────────────────────────────────────
def _sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """'f(a, b, c)' — solo nomi (niente valori default: compatto)."""
    args = []
    a = node.args
    for group in (a.posonlyargs, a.args):
        args.extend(x.arg for x in group)
    if a.vararg:
        args.append(f"*{a.vararg.arg}")
    for x in a.kwonlyargs:
        args.append(x.arg)
    if a.kwarg:
        args.append(f"**{a.kwarg.arg}")
    return f"{node.name}({', '.join(args)})"


class _FileVisitor(ast.NodeVisitor):
    """Estrae simboli (classi/funzioni/metodi di primo livello), chiamate
    (con chiamante per il grafo) e import di un file."""

    def __init__(self) -> None:
        self.symbols: list[dict] = []
        self.calls: list[dict] = []
        self.imports: list[dict] = []
        # stack di (nome, kind): serve a qualname e a sapere se siamo
        # dentro una class (i def annidati lì dentro sono 'method')
        self._scope: list[tuple[str, str]] = []

    def _push(self, name: str, kind: str) -> None:
        self._scope.append((name, kind))

    def _pop(self) -> None:
        self._scope.pop()

    @property
    def _qual(self) -> str:
        return ".".join(n for n, _ in self._scope)

    # simboli
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append({
            "kind": "class", "name": node.name, "qualname": self._qual,
            "signature": node.name, "doc": ast.get_docstring(node) or "",
            "line": node.lineno})
        self._push(node.name, "class")
        self.generic_visit(node)
        self._pop()

    def _visit_function(self, node) -> None:
        kind = ("method"
                if self._scope and self._scope[-1][1] == "class"
                else "function")
        self.symbols.append({
            "kind": kind, "name": node.name, "qualname": self._qual,
            "signature": _sig(node), "doc": ast.get_docstring(node) or "",
            "line": node.lineno})
        self._push(node.name, "function")
        self.generic_visit(node)
        self._pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    # chiamate (grafo best-effort: Nome o attributo finale)
    def visit_Call(self, node: ast.Call) -> None:
        f = node.func
        if isinstance(f, ast.Name):
            callee = f.id
        elif isinstance(f, ast.Attribute):
            callee = f.attr
        else:
            callee = ""
        if callee:
            self.calls.append({"caller": self._qual, "callee": callee,
                               "line": node.lineno})
        self.generic_visit(node)

    # import
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append({"module": alias.name,
                                 "names": alias.asname or ""})
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append({
            "module": node.module or "",
            "names": ", ".join(a.name for a in node.names)})
        self.generic_visit(node)


def _parse_py_file(path: Path) -> dict:
    """{'symbols', 'calls', 'imports', 'lines', 'ok'} — mai solleva."""
    out = {"symbols": [], "calls": [], "imports": [], "lines": 0, "ok": 0}
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except Exception:  # SyntaxError, encoding, IO — file marcato non-ok
        return out
    out["ok"] = 1
    out["lines"] = src.count("\n") + 1
    v = _FileVisitor()
    v.visit(tree)
    out["symbols"] = v.symbols
    out["calls"] = v.calls
    out["imports"] = v.imports
    return out


# ── Rebuild incrementale ──────────────────────────────────────────────
def rebuild(project_root: str | Path, *, force: bool = False) -> dict:
    """Aggiorna la mappa: solo i file cambiati (mtime) + cache di
    signature (M6). Mai solleva.

    `force=True` salta la cache: per test e forzatura refresh."""
    root = Path(project_root)
    stats = {"files": 0, "symbols": 0, "db": str(db_path(root))}
    # M6: fast path — se la signature (file_count, max_mtime) è
    # uguale all'ultima chiamata e il TTL non è scaduto, salta tutto
    # (niente SQLite, niente AST). Su progetti grandi e chiamate
    # ravvicinate (estimate_impact + render_map_section per lo stesso
    # task) è il salvavita prestazionale.
    try:
        sig = _project_signature(root)
    except Exception:
        sig = (-1, -1)
    cache_key = str(root.resolve())
    if not force and sig != (-1, -1):
        cached = _BUILD_CACHE.get(cache_key)
        if cached is not None:
            cached_sig, cached_stats, cached_ts = cached
            if cached_sig == sig and (time.time() - cached_ts) < _BUILD_TTL_S:
                return cached_stats
    try:
        dbp = db_path(root)
        dbp.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(dbp, timeout=2)
        conn.executescript(_SCHEMA)

        seen: dict[str, int] = {}
        for p in sorted(root.rglob("*.py")):
            rel_parts = p.relative_to(root).parts
            if SKIP_DIRS & set(rel_parts):
                continue
            try:
                mtime = p.stat().st_mtime_ns
            except OSError:
                continue
            rel = "/".join(rel_parts)
            seen[rel] = mtime
            row = conn.execute("SELECT mtime FROM files WHERE path=?",
                               (rel,)).fetchone()
            if row and row[0] == mtime:
                continue  # invariato: niente re-parse
            parsed = _parse_py_file(p)
            for table in ("symbols", "calls", "imports"):
                conn.execute(f"DELETE FROM {table} WHERE file=?", (rel,))
            conn.execute(
                "INSERT OR REPLACE INTO files(path, mtime, lines, ok) "
                "VALUES(?,?,?,?)", (rel, mtime, parsed["lines"], parsed["ok"]))
            for s in parsed["symbols"]:
                conn.execute(
                    "INSERT INTO symbols(file, kind, name, qualname, "
                    "signature, doc, line) VALUES(?,?,?,?,?,?,?)",
                    (rel, s["kind"], s["name"], s["qualname"],
                     s["signature"], s["doc"][:120], s["line"]))
            for c in parsed["calls"]:
                conn.execute(
                    "INSERT INTO calls(file, caller, callee, line) "
                    "VALUES(?,?,?,?)",
                    (rel, c["caller"], c["callee"], c["line"]))
            for i in parsed["imports"]:
                conn.execute(
                    "INSERT INTO imports(file, module, names) VALUES(?,?,?)",
                    (rel, i["module"], i["names"]))

        # file scomparsi
        for (rel,) in conn.execute("SELECT path FROM files").fetchall():
            if rel not in seen:
                for table in ("files", "symbols", "calls", "imports"):
                    conn.execute(f"DELETE FROM {table} WHERE file=?", (rel,))

        conn.commit()
        stats["files"] = len(seen)
        stats["symbols"] = conn.execute(
            "SELECT COUNT(*) FROM symbols").fetchone()[0]
        conn.close()
    except Exception:
        pass  # fail-open: mappa assente → prompt senza PROJECT MAP
    # M6: aggiorna la cache di signature (anche in caso di fail-open,
    # così la prossima chiamata con lo stesso progetto salta tutto).
    if sig != (-1, -1):
        _BUILD_CACHE[cache_key] = (sig, stats, time.time())
    return stats


def symbols(project_root: str | Path) -> list[dict]:
    """Tutte le voci della mappa (file, kind, name, qualname, sig, line)."""
    try:
        conn = sqlite3.connect(db_path(project_root), timeout=2)
        rows = conn.execute(
            "SELECT file, kind, name, qualname, signature, line, doc "
            "FROM symbols ORDER BY file, line").fetchall()
        conn.close()
        return [{"file": r[0], "kind": r[1], "name": r[2], "qualname": r[3],
                 "signature": r[4], "line": r[5], "doc": r[6]} for r in rows]
    except Exception:
        return []


def calls(project_root: str | Path) -> list[dict]:
    """Tutte le chiamate (file, caller, callee, line) — per il grafo."""
    try:
        conn = sqlite3.connect(db_path(project_root), timeout=2)
        rows = conn.execute(
            "SELECT file, caller, callee, line FROM calls "
            "ORDER BY file, line").fetchall()
        conn.close()
        return [{"file": r[0], "caller": r[1], "callee": r[2], "line": r[3]}
                for r in rows]
    except Exception:
        return []


def find_symbol(project_root: str | Path, name: str) -> dict | None:
    """Ricerca per nome (match esatto o suffisso di qualname)."""
    want = str(name or "").strip()
    if not want:
        return None
    for s in symbols(project_root):
        if s["name"] == want or s["qualname"].endswith(want):
            return s
    return None


# ── Sezione prompt ────────────────────────────────────────────────────
def render_map_section(project_root: str | Path,
                       exclude_files: set[str] | None = None,
                       max_chars: int = MAX_MAP_CHARS) -> str:
    """'## PROJECT MAP' per il prompt: simboli esistenti raggruppati.

    `exclude_files`: il file che sta per essere SOVRASCRITTO dalla
    generazione (i suoi simboli vecchi sono rumore). '' se vuota.
    """
    try:
        rebuild(project_root)
        rows = symbols(project_root)
    except Exception:
        return ""
    if not rows:
        return ""
    ex = {str(e) for e in (exclude_files or ())}

    by_file: dict[str, list[dict]] = {}
    for r in rows:
        if r["file"] in ex:
            continue
        by_file.setdefault(r["file"], []).append(r)

    lines = ["## PROJECT MAP — simboli già presenti nel progetto",
             "(RIUSA questi nomi e firme; non reinventare funzioni che "
             "esistono già)"]
    for f in sorted(by_file):
        lines.append(f"{f}:")
        items = by_file[f]
        # i metodi portano qualname = percorso-classe (la class stessa è
        # registrata PRIMA di entrare nel suo scope): la chiave per
        # raggrupparli è qualname_padre + '.' + nome_classe
        methods_of: dict[str, list[str]] = {}
        for it in items:
            if it["kind"] == "method":
                methods_of.setdefault(it["qualname"], []).append(it["name"])
        for it in items:
            if it["kind"] == "class":
                key = it["qualname"] + ("." if it["qualname"] else "") \
                    + it["name"]
                ms = methods_of.get(key, [])
                ms_txt = f" — {', '.join(m + '()' for m in ms)}" if ms else ""
                lines.append(f"  class {it['signature']}{ms_txt}")
            elif it["kind"] == "function":
                lines.append(f"  def {it['signature']}")
    section = "\n".join(lines)
    if len(section) > max_chars:
        section = section[:max_chars] + "\n...[mappa troncata]"
    return section


# ── Verifica statica dei nomi ─────────────────────────────────────────
_BUILTIN_EXTRA = {"__name__", "__file__", "__doc__", "__debug__",
                  "__builtins__", "__spec__", "__package__", "__loader__",
                  "__cached__"}


def check_code_names(code: str, max_report: int = MAX_UNKNOWN_REPORT,
                     ) -> list[tuple[str, int]]:
    """Nomi usati (Load) ma mai definiti/importati → NameError latenti.

    Analisi di scope approssimata (tutto ciò che assegna/definisce in
    QUALSIASI punto del file conta come disponibile) — sufficiente per
    beccare i refusi e le variabili mai create (il caso `coll.pop()` a
    livello modulo della regressione T8). I nomi usati SOLO in
    annotazioni sono esclusi (le annotazioni pigre di Python 3.14 non
    valutano a import-time). Mai solleva.
    """
    try:
        tree = ast.parse(str(code or ""))
    except Exception:
        return []  # la sintassi la becca py_compile

    bound: set[str] = set(dir(builtins)) | _BUILTIN_EXTRA
    annot_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.alias):
            bound.add((node.asname or node.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)

        # annotazioni: permetto i loro nomi anche se non importati
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ([node.returns] +
                        [a.annotation for a in ast.walk(node.args)
                         if isinstance(a, ast.arg) and a.annotation]):
                if sub:
                    annot_names |= {n.id for n in ast.walk(sub)
                                    if isinstance(n, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and node.annotation:
            annot_names |= {n.id for n in ast.walk(node.annotation)
                            if isinstance(n, ast.Name)}

    unknown: list[tuple[str, int]] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.id not in bound
                and node.id not in annot_names
                and node.id not in seen):
            seen.add(node.id)
            unknown.append((node.id, node.lineno))
            if len(unknown) >= max_report:
                break
    return unknown
