"""CORE/import_check.py — nomi indefiniti (API allucinate) in un sorgente.

Motivazione (C85): pyflakes sul nostro stesso repo ha trovato 12 nomi
indefiniti. Un nome indefinito è la firma dell'allucinazione API: il
modello scrive `QTimer.singleShot` ma ha importato `QTimer` da un modulo
sbagliato, oppure chiama un simbolo che non esiste.

Il modulo è il mattone condiviso da due gate:

- **P1-2** (`CORE/tools.py`): dopo `write_file`/`patch_code` su un `.py`
  il file viene controllato; a fine task il worker rifiuta il `done` se
  restano nomi indefiniti (come il test-gate del Cycle 78).
- **SLOT-1** (`CORE/slot_gate.py`): il frammento di uno slot viene
  controllato PRIMA dell'assembly, con i nomi delle refs come noti.

Backend: pyflakes (se installato) → analisi di scope completa. Fallback:
analisi AST interna (modulo/funzione/classe/comprehension) per non
dipendere da un pacchetto a runtime. Entrambi riportano solo gli errori
*bloccanti*: nomi indefiniti e errori di sintassi.

Zero LLM, nessuna rete.
"""

from __future__ import annotations

import ast
import builtins
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

# pyflakes è la dipendenza di lint del progetto; se manca si usa l'AST.
try:  # pragma: no cover - dipende dall'ambiente
    from pyflakes import api as _pyflakes_api
    from pyflakes import reporter as _pyflakes_reporter
except Exception:  # pragma: no cover
    _pyflakes_api = None
    _pyflakes_reporter = None


@dataclass(frozen=True)
class Issue:
    """Un errore bloccante trovato nel sorgente."""

    filename: str
    line: int
    col: int
    kind: str          # "undefined_name" | "syntax"
    message: str

    def __str__(self) -> str:
        return f"{self.filename}:{self.line}:{self.col + 1}: {self.message}"


# Solo questi kinds bloccano il done/gate: sono errori, non stile.
BLOCKING_KINDS = frozenset({"undefined_name", "syntax"})


def blocking(issues: Iterable[Issue]) -> list[Issue]:
    """Filtra i soli errori che devono bloccare (non warning di stile)."""
    return [i for i in issues if i.kind in BLOCKING_KINDS]


# ----------------------------------------------------------------------
# Backend pyflakes
# ----------------------------------------------------------------------

if _pyflakes_reporter is not None:  # pragma: no branch

    class _Collector(_pyflakes_reporter.Reporter):
        """Reporter pyflakes che raccoglie solo i messaggi bloccanti."""

        def __init__(self, filename: str) -> None:
            # pyflakes 4 richiede warningStream + errorStream; le versioni
            # precedenti accettano solo errorStream. Il costruttore base è
            # usato solo per i default: noi sovrascriviamo tutto.
            try:
                super().__init__(None, None)  # type: ignore[arg-type]
            except TypeError:  # pragma: no cover - pyflakes < 4
                super().__init__(None)  # type: ignore[arg-type]
            self.filename = filename
            self.issues: list[Issue] = []

        def flake(self, message) -> None:  # pyflakes >= 4
            kind = type(message).__name__
            if kind not in ("UndefinedName", "UndefinedLocal"):
                return
            text = str(message)
            short = text.split(": ", 1)[-1]
            self.issues.append(Issue(
                self.filename,
                int(getattr(message, "lineno", 0) or 0),
                int(getattr(message, "col", 0) or 0),
                "undefined_name",
                short,
            ))

        def flakes(self, message) -> None:  # pyflakes < 4
            self.flake(message)

        def syntaxError(self, *args) -> None:
            # v4: (filename, msg, lineno, offset, text)
            # v3: (msg, lineno, offset, text)
            if len(args) >= 5:
                _fn, msg, lineno, offset, _text = args[:5]
            elif len(args) == 4:
                msg, lineno, offset, _text = args
            else:  # pragma: no cover - difensivo
                msg, lineno, offset = "syntax error", 0, 0
            self.issues.append(Issue(
                self.filename, int(lineno or 0), int(offset or 0),
                "syntax", f"syntax error: {msg}",
            ))

        def unexpectedError(self, filename: str, msg: str) -> None:
            self.issues.append(Issue(
                filename, 0, 0, "syntax", f"unexpected error: {msg}"))


# ----------------------------------------------------------------------
# Fallback: analisi di scope con l'AST
# ----------------------------------------------------------------------

_BUILTINS = frozenset(dir(builtins))


class _Scope:
    __slots__ = ("kind", "parent", "bound", "globals", "nonlocals")

    def __init__(self, kind: str, parent: "_Scope | None" = None) -> None:
        self.kind = kind          # "module" | "function" | "class" | "comp"
        self.parent = parent
        self.bound: set[str] = set()
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()


class _AstResolver(ast.NodeVisitor):
    """Risolutore di nomi sufficiente per i casi reali (nessuna magia).

    Limiti onesti: import condizionali, `exec`, `globals()[...]` e
    metaprogrammazione possono produrre falsi positivi. Per questo il
    fallback è usato solo se pyflakes manca e il gate è fail-open dopo
    due tentativi.
    """

    def __init__(self, filename: str, known: Iterable[str] = ()) -> None:
        self.filename = filename
        self.module = _Scope("module")
        self.module.bound |= set(known)
        self.scope = self.module
        self.issues: list[Issue] = []
        self._seen: set[tuple[str, int]] = set()

    # -- scope helpers --------------------------------------------------
    def _bind(self, name: str) -> None:
        if name in self.scope.globals:
            self.module.bound.add(name)
        elif name in self.scope.nonlocals:
            p = self.scope.parent
            while p is not None and p.kind not in ("function", "module"):
                p = p.parent
            if p is not None:
                p.bound.add(name)
        else:
            self.scope.bound.add(name)

    def _resolve(self, name: str) -> bool:
        if name in _BUILTINS:
            return True
        scope: _Scope | None = self.scope
        first = True
        while scope is not None:
            # Lo scope di classe non è visibile alle funzioni annidate.
            if scope.kind == "class" and not first:
                scope = scope.parent
                continue
            if name in scope.bound:
                return True
            if scope.kind == "module":
                return False
            first = False
            scope = scope.parent
        return False

    def _run(self, kind: str, nodes: Sequence[ast.AST],
             extra_bound: Iterable[str] = ()) -> None:
        parent = self.scope
        self.scope = _Scope(kind, parent)
        self.scope.bound |= set(extra_bound)
        for node in nodes:
            self.visit(node)
        self.scope = parent

    # -- binding constructs --------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._bind(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self._bind(alias.asname or alias.name)

    def visit_Global(self, node: ast.Global) -> None:
        self.scope.globals.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.scope.nonlocals.update(node.names)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            if not self._resolve(node.id):
                key = (node.id, node.lineno)
                if key not in self._seen:
                    self._seen.add(key)
                    self.issues.append(Issue(
                        self.filename, node.lineno, node.col_offset,
                        "undefined_name", f"undefined name '{node.id}'",
                    ))
        elif isinstance(node.ctx, ast.Store):
            self._bind(node.id)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # `x += 1` legge x prima di scriverla.
        if isinstance(node.target, ast.Name):
            if not self._resolve(node.target.id):
                key = (node.target.id, node.target.lineno)
                if key not in self._seen:
                    self._seen.add(key)
                    self.issues.append(Issue(
                        self.filename, node.target.lineno,
                        node.target.col_offset, "undefined_name",
                        f"undefined name '{node.target.id}'",
                    ))
            self._bind(node.target.id)
            self.visit(node.value)
            return
        self.generic_visit(node)

    def _visit_args(self, args: ast.arguments) -> None:
        for default in list(args.defaults) + [d for d in args.kw_defaults if d]:
            self.visit(default)
        all_args = (list(getattr(args, "posonlyargs", [])) + list(args.args)
                    + list(args.kwonlyargs))
        for arg in all_args:
            if arg.annotation is not None:
                self.visit(arg.annotation)
            self.scope.bound.add(arg.arg)
        if args.vararg is not None:
            if args.vararg.annotation is not None:
                self.visit(args.vararg.annotation)
            self.scope.bound.add(args.vararg.arg)
        if args.kwarg is not None:
            if args.kwarg.annotation is not None:
                self.visit(args.kwarg.annotation)
            self.scope.bound.add(args.kwarg.arg)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._bind(node.name)
        for dec in node.decorator_list:
            self.visit(dec)
        if node.returns is not None:
            self.visit(node.returns)
        parent = self.scope
        self.scope = _Scope("function", parent)
        self._visit_args(node.args)
        for stmt in node.body:
            self.visit(stmt)
        self.scope = parent

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._bind(node.name)
        for dec in node.decorator_list:
            self.visit(dec)
        for base in node.bases:
            self.visit(base)
        for kw in node.keywords:
            self.visit(kw.value)
        parent = self.scope
        self.scope = _Scope("class", parent)
        for stmt in node.body:
            self.visit(stmt)
        self.scope = parent

    def visit_Lambda(self, node: ast.Lambda) -> None:
        parent = self.scope
        self.scope = _Scope("function", parent)
        self._visit_args(node.args)
        self.visit(node.body)
        self.scope = parent

    def _visit_comprehension(self, node, result_nodes: Sequence[ast.AST]) -> None:
        generators = node.generators
        if not generators:
            self.generic_visit(node)
            return
        # Il primo iterable è valutato nello scope esterno.
        self.visit(generators[0].iter)
        parent = self.scope
        self.scope = _Scope("comp", parent)
        for gen in generators:
            self.visit(gen.target)
            for cond in gen.ifs:
                self.visit(cond)
        for result in result_nodes:
            self.visit(result)
        self.scope = parent

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node, [node.key, node.value])

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is not None:
            self.visit(node.type)
        if node.name:
            self._bind(node.name)
        for stmt in node.body:
            self.visit(stmt)


def _ast_issues(source: str, filename: str,
                known: Iterable[str] = ()) -> list[Issue]:
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [Issue(filename, int(exc.lineno or 0), int(exc.offset or 0),
                      "syntax", f"syntax error: {exc.msg}")]
    resolver = _AstResolver(filename, known)
    resolver.visit(tree)
    return resolver.issues


# ----------------------------------------------------------------------
# API pubblica
# ----------------------------------------------------------------------

def check_source(source: str, filename: str = "<fragment>",
                 known: Iterable[str] = ()) -> list[Issue]:
    """Nomi indefiniti + errori di sintassi nel sorgente.

    `known` sono nomi considerati già definiti (es. le refs di uno slot):
    vengono aggiunti allo scope di modulo, quindi nessun offset di riga.
    """
    text = textwrap.dedent(source)
    if _pyflakes_api is not None:
        header = ""
        names = sorted({n for n in known if n.isidentifier()})
        if names:
            # Definizioni in coda: non spostano le righe del sorgente.
            header = "\n" + " = ".join(names) + " = None\n"
        collector = _Collector(filename)
        _pyflakes_api.check(text + header, filename, collector)
        return collector.issues
    return _ast_issues(text, filename, known)  # pragma: no cover


def check_path(path: str | Path) -> list[Issue]:
    """Come check_source, ma legge il file dal disco (fail-open)."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return check_source(source, str(p))


def format_issues(issues: Iterable[Issue], limit: int = 8) -> str:
    """Riga(s) leggibili per il prompt di correction."""
    items = list(issues)
    lines = [str(i) for i in items[:limit]]
    if len(items) > limit:
        lines.append(f"... e altri {len(items) - limit} errori")
    return "\n".join(lines)


def format_report(by_path: Mapping[str, Sequence[Issue]],
                  limit: int = 4) -> str:
    """Report multi-file: un blocco per file, max `limit` errori per file."""
    blocks: list[str] = []
    for path, issues in by_path.items():
        blocking_issues = blocking(issues)
        if blocking_issues:
            blocks.append(f"{path}:\n{format_issues(blocking_issues, limit)}")
    return "\n".join(blocks)
