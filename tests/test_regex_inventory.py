# -*- coding: utf-8 -*-
"""Inventario deterministico delle regex del software (2026-11-22).

Scansiona SORGENTI (AST, senza importare i moduli) e REGISTRO centralizzato:

- `CORE/regex_controller.py` → `DEFAULT_PATTERNS` + `LANG_HINTS`;
- chiamate `re.compile/search/match/findall/...` con pattern letterale;
- `RegexController.add('nome', r'pattern')`.

Stampa l'inventario con `pytest tests/test_regex_inventory.py -q -s`.
Nessuna regex viene modificata: il test è solo lettura e validazione.
I duplicati tra *usages* sono ammessi e conteggiati; sono considerati un
difetto solo nel registro centralizzato, dove dovrebbero avere un solo nome.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.regex_controller import DEFAULT_PATTERNS, LANG_HINTS  # noqa: E402

SCAN_DIRS = ("CORE", "GUI", "tools")
SKIP_PARTS = frozenset({"__pycache__", ".git", ".venv", "data", "state",
                        "node_modules", "build", "dist"})
RE_METHODS = frozenset({"compile", "fullmatch", "match", "search", "findall",
                        "finditer", "sub", "subn", "split"})
FLAG_NAMES = {"I": re.I, "IGNORECASE": re.I, "M": re.M, "MULTILINE": re.M,
              "S": re.S, "DOTALL": re.S, "X": re.X, "VERBOSE": re.X,
              "A": re.A, "ASCII": re.A, "L": re.L, "LOCALE": re.L}


def _sources():
    """File Python sorgente da scansionare (esclusi dati e ambienti)."""
    for name in SCAN_DIRS:
        base = ROOT / name
        if base.is_dir():
            for path in sorted(base.rglob("*.py")):
                if not any(p in SKIP_PARTS for p in path.parts):
                    yield path


def _constant(node):
    """Valore stringa letterale, oppure None per espressioni dinamiche."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _flags(node):
    """Flag `re.X` espliciti in una chiamata (0 se assenti)."""
    if node is None:
        return 0
    if isinstance(node, ast.Attribute) and node.attr in FLAG_NAMES:
        return FLAG_NAMES[node.attr]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flags(node.left) | _flags(node.right)
    return 0


def _aliases(tree):
    """Alias locali del modulo `re` e di `re.compile`."""
    mods, compilers = {"re"}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re":
                    mods.add(alias.asname or "re")
        elif isinstance(node, ast.ImportFrom) and node.module == "re":
            for alias in node.names:
                if alias.name == "compile":
                    compilers.add(alias.asname or "compile")
    return mods, compilers


def _labels(tree):
    """Mappa id(call) → nome variabile assegnata, per etichettare l'uso."""
    labels = {}
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if (target is not None and isinstance(target, ast.Name)
                and isinstance(node.value, ast.Call)):
            labels[id(node.value)] = target.id
    return labels


def _is_re_call(func, mods, compilers):
    if isinstance(func, ast.Attribute):
        return (isinstance(func.value, ast.Name)
                and func.value.id in mods and func.attr in RE_METHODS)
    if isinstance(func, ast.Name):
        return func.id in compilers
    return False


def _scan_source(path):
    """Pattern letterali trovati in un file sorgente."""
    entries = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return entries
    mods, compilers = _aliases(tree)
    labels = _labels(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_re = _is_re_call(func, mods, compilers)
        is_add = (isinstance(func, ast.Attribute) and func.attr == "add"
                  and len(node.args) >= 2)
        if not (is_re or is_add):
            continue
        pattern = _constant(node.args[0] if is_re else node.args[1])
        if pattern is None:
            continue
        if is_add:
            name = _constant(node.args[0]) or "add"
            flags = _flags(node.args[2] if len(node.args) > 2 else None)
        else:
            name = labels.get(id(node), func.attr if isinstance(func, ast.Attribute)
                              else func.id)
            flags = _flags(node.args[1] if len(node.args) > 1 else None)
        rel = path.relative_to(ROOT).as_posix()
        entries.append({"source": f"{rel}:{node.lineno}", "name": name,
                        "pattern": pattern, "flags": flags})
    return entries


def build_inventory():
    """Inventario completo: registro centralizzato + usages sorgente."""
    registry = []
    for name, pattern in {**DEFAULT_PATTERNS, **LANG_HINTS}.items():
        registry.append({"source": "CORE/regex_controller.py", "name": name,
                         "pattern": pattern, "flags": 0})
    usages = []
    for path in _sources():
        usages.extend(_scan_source(path))
    return registry, usages


def format_inventory(registry, usages):
    """Testo leggibile dell'inventario, con conteggi e pattern sospetti."""
    lines = ["INVENTARIO REGEX — Byte-Swarmy", "=" * 72,
             f"Registro centralizzato: {len(registry)} | usages sorgente: "
             f"{len(usages)} | file sorgente: {len(list(_sources()))}",
             "", "REGISTRO (CORE/regex_controller.py)", "-" * 72]
    lines.extend(f"  {e['name']:<22} {e['pattern']}" for e in registry)
    lines.extend(["", "USAGES (CORE/, GUI/, tools/)", "-" * 72])
    lines.extend(f"  {e['source']:<44} {e['name']:<20} {e['pattern']}"
                 for e in usages)
    invalids = [e for e in registry + usages if _invalid(e)]
    lines.extend(["", f"INVALIDI: {len(invalids)}"])
    lines.extend(f"  {e['source']} · {e['name']} · {e['pattern']}"
                 for e in invalids)
    return "\n".join(lines)


def _invalid(entry):
    """True se il pattern non compila o è vuoto."""
    if not entry["pattern"]:
        return True
    try:
        re.compile(entry["pattern"], entry["flags"])
    except (re.error, ValueError, TypeError):
        return True
    return False


def test_inventario_e_legibile_e_stampabile():
    """Con `-s` stampa tutte le regex; il testo contiene le sezioni attese."""
    registry, usages = build_inventory()
    text = format_inventory(registry, usages)
    print("\n" + text)
    assert "REGISTRO (CORE/regex_controller.py)" in text
    assert "USAGES (CORE/, GUI/, tools/)" in text
    assert "json_object" in text
    assert len(usages) > 50


def test_ogni_pattern_compila():
    registry, usages = build_inventory()
    bad = [e for e in registry + usages if _invalid(e)]
    assert not bad, f"pattern invalidi: {bad[:5]}"


def test_registro_senza_duplicati():
    """Nel registro centralizzato due nomi non devono condividere un pattern."""
    registry, _ = build_inventory()
    seen = {}
    dupes = []
    for entry in registry:
        key = (entry["pattern"], entry["flags"])
        if key in seen:
            dupes.append((seen[key], entry["name"]))
        else:
            seen[key] = entry["name"]
    assert not dupes, f"pattern duplicati nel registro: {dupes}"


def test_fonti_scansionate():
    """Le cartelle sorgente devono essere presenti e contenere regex."""
    files = list(_sources())
    assert all((ROOT / d).is_dir() for d in SCAN_DIRS)
    assert len(files) > 100
    _, usages = build_inventory()
    assert any(e["source"].startswith("CORE/") for e in usages)
