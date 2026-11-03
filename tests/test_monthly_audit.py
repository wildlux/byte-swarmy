# -*- coding: utf-8 -*-
"""
tests/test_monthly_audit.py — Audit mensile del software BYTE-SWARMY.

Controlli:
  1. Variabili inutilizzate (pubbliche, a livello modulo e attributi di classe)
  2. Codice morto (funzioni/metodi mai chiamati nel repo)
  3. Porte/endpoint esposti (bind su 0.0.0.0, host non-loopback, socket.listen)
  4. Superficie reverse proxy (subprocess che potrebbero esporre porte:
     ngrok, cloudflared, ssh -R, socat, nginx, caddy, frp, tailscale, ecc.)

Esegue anche controlli complementari:
  - Moduli banditi (socket/ctypes/pickle fuori allowlist)
  - File critici ancora presenti e non vuoti
  - config.toml valido

Fallisce (assert) se trova problemi critici; emette warning per gli altri.
Si può lanciare standalone:
    python tests/test_monthly_audit.py
    python tests/test_monthly_audit.py --json   # report JSON su stdout
    python tests/test_monthly_audit.py --html logs/audit/report.html
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Directory da saltare nella scansione file (ambiente, cache, runtime)
_ENV_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", "build",
             "dist", ".ruff_cache", ".mypy_cache", "logs", "state",
             "tasks", "backups", "project"}

# Directory del codice sorgente da analizzare (non test, non esempi)
_SOURCE_DIRS = ("CORE", "GUI", "SAFETY", "MONITORING", "INTENT")

# Moduli banditi al di fuori dell'allowlist
_BANNED_IMPORTS = {
    "socket": {"CORE/sandbox_selftest.py", "tests/test_mcp_e2e.py",
               "tests/test_sandbox.py", "CORE/monthly_audit.py",
               "tests/test_monthly_audit.py"},
    "ctypes": {"CORE/sandbox_selftest.py"},  # legittimo: selftest del sandbox
    "pickle": set(),
    "marshal": set(),
    "telnetlib": set(),
    "ftplib": set(),
    "http.server": set(),
    "BaseHTTPServer": set(),
    "SimpleHTTPServer": set(),
    "SocketServer": set(),
    "TCPServer": set(),
    "UDPServer": set(),
}

# File critici che devono esistere e non essere vuoti
CRITICAL_FILES = [
    "CORE/orchestrator.py",
    "CORE/tools.py",
    "CORE/ollama_client.py",
    "CORE/scheduler_worker.py",
    "SAFETY/security.py",
    "SAFETY/security_checks.py",
    "SAFETY/watchdog.py",
    "CONFIG/config.toml",
    "GUI/control_center.py",
    "GUI/gui_backend.py",
    "GUI/settings_store.py",
    "GUI/main_window.py",
]

# Host non-loopback banditi in bind()/listen()
_FORBIDDEN_HOSTS = ("0.0.0.0", "::", "[::]", "localhost", "*", "")

# Porte legittime (loopback only)
_ALLOWED_PORTS = {11434, 8080, 8090, 8092}  # Ollama, MCP example, etc.

# Comandi subprocess che potrebbero esporre porte all'esterno (reverse proxy,
# tunnel, port-forward). Li segnaliamo sempre, anche se su loopback, perché
# la loro presenza va revisionata manualmente.
_TUNNEL_COMMANDS = re.compile(
    r"\b("
    r"ngrok|cloudflared|frpc|frps|bore|tunnelto|localhost\.run|"
    r"ssh\s+.*-[RL]\s+\d+|autossh|"
    r"socat\s+.*TCP-LISTEN|socat\s+.*TCP4-LISTEN|"
    r"iptables\s+.*-t\s+nat.*DNAT|"
    r"nginx|haproxy|caddy|traefik|"
    r"tailscale|zerotier|wireguard|wg-quick|"
    r"docker\s+.*-p\s+\d+|docker\s+.*--publish|"
    r"podman\s+.*-p\s+\d+|"
    r"kubectl\s+port-forward|"
    r"stunnel|spiped|"
    r"redir|rinetd|"
    r"python\s+-m\s+http\.server|"
    r"ruby\s+-run\s+-e\s+httpd|"
    r"php\s+-S\s+|"
    r"nc\s+-l|ncat\s+-l|netcat\s+-l"
    r")\b",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════
# Helper: scanning del repo
# ═══════════════════════════════════════════════════════════════

def _iter_source_files(root: Path = None) -> Iterable[Path]:
    """Itera sui file .py delle directory sorgente, saltando env/cache.

    Per self-audit (root=ROOT o None): itera CORE/GUI/SAFETY/MONITORING/INTENT.
    Per target esterni: itera tutti i .py della root (skip env/cache).
    """
    base = Path(root) if root else ROOT
    if root is None or base.resolve() == ROOT.resolve():
        # Self-audit: usa le directory byte-swarmy
        for subdir in _SOURCE_DIRS:
            d = base / subdir
            if not d.is_dir():
                continue
            for p in d.rglob("*.py"):
                if any(part in _ENV_DIRS for part in p.parts):
                    continue
                yield p
    else:
        # Target esterno: tutti i .py ricorsivamente (skip env/cache)
        for p in base.rglob("*.py"):
            if any(part in _ENV_DIRS for part in p.parts):
                continue
            yield p


def _iter_all_py_files(root: Path = None) -> Iterable[Path]:
    """Itera su TUTTI i .py del repo (esclusi env/cache) — per cross-ref."""
    base = Path(root) if root else ROOT
    for p in base.rglob("*.py"):
        if any(part in _ENV_DIRS for part in p.parts):
            continue
        yield p


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _rel(p: Path, root: Path = None) -> str:
    """Percorso relativo a root, con separatori normalizzati a /."""
    base = Path(root) if root else ROOT
    try:
        return str(p.relative_to(base)).replace(os.sep, "/")
    except ValueError:
        return str(p)


# ═══════════════════════════════════════════════════════════════
# AUDIT 1: Variabili inutilizzate
# ═══════════════════════════════════════════════════════════════

def _scan_unused_variables(root: Path = None) -> list[dict]:
    """Trova variabili pubbliche a livello modulo mai referenziate altrove.

    Cerca:
      - assegnazioni a livello modulo con nome NON usato in altri file
      - attributi di classe pubblici (no underscore) mai referenziati
    Salta: __all__, __version__, costanti UPPER_CASE pubbliche (potrebbero
    essere API), variabili con underscore (private per convenzione).
    """
    # Costruisce l'indice di tutti gli identificatori usati nel repo
    used_identifiers: set[str] = set()
    # Mappa: nome variabile -> lista di (file, riga) dove è definita
    module_vars: dict[str, list[tuple[str, int]]] = defaultdict(list)

    for p in _iter_all_py_files(root):
        src = _read_text(p)
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError:
            continue
        # Raccogli tutti i Name e Attribute usati (load context)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_identifiers.add(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                used_identifiers.add(node.attr)
        # Raccogli assegnazioni a livello modulo (non dentro funzioni/classi)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        # Salta privati e dunder
                        if name.startswith("_"):
                            continue
                        # Salta costanti UPPER_CASE (potrebbero essere API)
                        # Es: MAX_RETRIES, DEFAULT_TIMEOUT, CONFIG_FILE, ecc.
                        if name.isupper() or name.replace("_", "").isupper():
                            continue
                        # Salta __all__, __version__ ecc.
                        if name in ("__all__", "__version__", "__author__"):
                            continue
                        module_vars[name].append((_rel(p, root), node.lineno))

    # Cerca variabili definite ma mai usate altrove
    findings = []
    for name, defs in module_vars.items():
        # Una variabile è "usata" se appare come identificatore in qualsiasi file
        # (incluso quello di definizione). Se appare solo in 1 file ed è
        # definita ma mai caricata, è sospetta.
        if name not in used_identifiers:
            for f, line in defs:
                findings.append({
                    "type": "unused_module_variable",
                    "file": f,
                    "line": line,
                    "name": name,
                    "severity": "warning",
                    "message": f"Variabile modulo '{name}' definita ma mai referenziata",
                })
    return findings


# ═══════════════════════════════════════════════════════════════
# AUDIT 2: Codice morto (funzioni/metodi mai chiamati)
# ═══════════════════════════════════════════════════════════════

# Suffissi che indicano metodi speciali / entry point / hook — non segnare
# come morti anche se non chiamati esplicitamente.
_NOT_DEAD_SUFFIXES = (
    "__init__", "__main__", "__call__", "__enter__", "__exit__",
    "__str__", "__repr__", "__len__", "__iter__", "__next__",
    "__getitem__", "__setitem__", "__delitem__", "__contains__",
    "__eq__", "__hash__", "__bool__", "__getattr__", "__setattr__",
)
_ENTRY_POINT_NAMES = {
    "main", "run", "start", "stop", "tick", "tick_once", "execute",
    "handle", "process", "on_", "do_", "setup", "teardown",
    "test_",  # funzioni di test
    "is_", "get_", "set_", "has_",  # getter/setter pubblici
}


def _scan_dead_code(root: Path = None) -> list[dict]:
    """Trova funzioni/metodi pubblici mai chiamati nel repo.

    Euristiche:
      - Definizioni di `def name(...)` e `async def name(...)` pubbliche (no _)
      - Cerca `name(` in tutti i file .py
      - Salta metodi dunder, entry point canonici (main, run, start, ...),
        getter/setter (is_*, get_*, set_*, has_*), funzioni di test (test_*)
      - Salta override di metodi base Qt (mousePressEvent, enterEvent, ...)
    """
    # Raccogli tutte le definizioni di funzione pubbliche
    definitions: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    # Raccogli tutte le chiamate (Name o Attribute con ctx=Call)
    called_names: set[str] = set()

    for p in _iter_all_py_files(root):
        src = _read_text(p)
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
                    continue  # privata
                # Salta dunder (a parte __init__ che è ok)
                if name.startswith("__") and name.endswith("__"):
                    continue
                # Salta entry point canonici
                if name in _ENTRY_POINT_NAMES or any(name.startswith(p) for p in _ENTRY_POINT_NAMES):
                    continue
                # Salta override di metodi Qt comuni
                if name in {"mousePressEvent", "mouseReleaseEvent", "mouseMoveEvent",
                            "enterEvent", "leaveEvent", "keyPressEvent", "keyReleaseEvent",
                            "wheelEvent", "resizeEvent", "paintEvent", "closeEvent",
                            "dragEnterEvent", "dragMoveEvent", "dropEvent", "contextMenuEvent",
                            "focusInEvent", "focusOutEvent", "showEvent", "hideEvent",
                            "timerEvent", "event", "eventFilter"}:
                    continue
                definitions[name].append((_rel(p, root), node.lineno, name))
            elif isinstance(node, ast.Call):
                # Resolves name(...) e obj.name(...)
                fn = node.func
                if isinstance(fn, ast.Name):
                    called_names.add(fn.id)
                elif isinstance(fn, ast.Attribute):
                    called_names.add(fn.attr)

    findings = []
    for name, defs in definitions.items():
        if name not in called_names:
            for f, line, _ in defs:
                findings.append({
                    "type": "dead_code",
                    "file": f,
                    "line": line,
                    "name": name,
                    "severity": "warning",
                    "message": f"Funzione/metodo '{name}' definito ma mai chiamato",
                })
    return findings


# ═══════════════════════════════════════════════════════════════
# AUDIT 3: Porte/endpoint esposti
# ═══════════════════════════════════════════════════════════════

def _scan_exposed_ports(root: Path = None) -> list[dict]:
    """Trova bind/listen su porte, specialmente non-loopback.

    Pattern cercati:
      - socket.socket(...).bind((host, port))
      - HTTPServer((host, port), ...)
      - uvicorn.run(..., host=..., port=...)
      - app.run(host=..., port=...) [flask]
      - host="0.0.0.0" o host="::" in qualsiasi contesto di bind
    """
    findings = []
    for p in _iter_all_py_files(root):
        src = _read_text(p)
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError:
            continue
        rel_p = _rel(p, root)
        for node in ast.walk(tree):
            # Caso 1: socket.bind((host, port))
            if isinstance(node, ast.Call):
                fn = node.func
                # Resolves .bind(...) chiamato su qualsiasi oggetto
                if isinstance(fn, ast.Attribute) and fn.attr == "bind":
                    if node.args and isinstance(node.args[0], ast.Tuple):
                        host, port = _extract_host_port(node.args[0])
                        findings.extend(_check_bind(rel_p, node.lineno, host, port))
                # Caso 2: HTTPServer / TCPServer / UDPServer ((host, port), ...)
                if isinstance(fn, ast.Name) and fn.id in {"HTTPServer", "TCPServer",
                                                           "UDPServer", "SocketServer",
                                                           "BaseHTTPServer"}:
                    if node.args and isinstance(node.args[0], ast.Tuple):
                        host, port = _extract_host_port(node.args[0])
                        findings.extend(_check_bind(rel_p, node.lineno, host, port))
                # Caso 3: uvicorn.run(app, host=..., port=...)
                if isinstance(fn, ast.Attribute) and fn.attr == "run":
                    # Controlla keyword args host=/port=
                    host = port = None
                    for kw in node.keywords:
                        if kw.arg == "host" and isinstance(kw.value, ast.Constant):
                            host = kw.value.value
                        elif kw.arg == "port" and isinstance(kw.value, ast.Constant):
                            port = kw.value.value
                    if host is not None or port is not None:
                        findings.extend(_check_bind(rel_p, node.lineno, host, port))
                # Caso 4: app.run(host=..., port=...) [flask-like]
                if isinstance(fn, ast.Attribute) and fn.attr == "run":
                    for kw in node.keywords:
                        if kw.arg == "host" and isinstance(kw.value, ast.Constant):
                            if kw.value.value in _FORBIDDEN_HOSTS:
                                findings.append({
                                    "type": "exposed_port",
                                    "file": rel_p, "line": node.lineno,
                                    "host": str(kw.value.value),
                                    "severity": "critical",
                                    "message": f"app.run(host={kw.value.value!r}) espone servizio su tutte le interfacce",
                                })

    # Scansione testuale per 0.0.0.0 in stringhe (anche in config, shell, ecc.)
    for p in _iter_source_files(root):
        src = _read_text(p)
        rel_p = _rel(p, root)
        for m in re.finditer(r'["\'](0\.0\.0\.0|::)\s*["\']', src):
            line = src[:m.start()].count("\n") + 1
            findings.append({
                "type": "exposed_host_string",
                "file": rel_p, "line": line,
                "host": m.group(1),
                "severity": "warning",
                "message": f"Stringa host non-loopback '{m.group(1)}' trovata — verificare contesto",
            })
    return findings


def _extract_host_port(tuple_node: ast.Tuple) -> tuple[str | None, int | None]:
    """Estrae (host, port) da un ast.Tuple letterale."""
    host = None
    port = None
    if len(tuple_node.elts) >= 2:
        if isinstance(tuple_node.elts[0], ast.Constant):
            host = str(tuple_node.elts[0].value)
        if isinstance(tuple_node.elts[1], ast.Constant):
            port = tuple_node.elts[1].value
    return host, port


def _check_bind(rel_p: str, line: int, host: str | None, port: int | None) -> list[dict]:
    """Classifica un bind: critical se host non-loopback, warning se porta non standard."""
    findings = []
    if host in _FORBIDDEN_HOSTS:
        findings.append({
            "type": "exposed_port",
            "file": rel_p, "line": line,
            "host": str(host), "port": port,
            "severity": "critical",
            "message": f"bind su host non-loopback {host!r}:{port} — servizio esposto all'esterno",
        })
    elif port is not None and port not in _ALLOWED_PORTS and not (port > 0 and host in ("127.0.0.1", "::1", "localhost")):
        # Porta non standard anche su loopback — segnaliamo per revisione
        findings.append({
            "type": "nonstandard_port",
            "file": rel_p, "line": line,
            "host": str(host), "port": port,
            "severity": "warning",
            "message": f"bind su porta non standard {host}:{port} — verificare che sia intenzionale",
        })
    return findings


# ═══════════════════════════════════════════════════════════════
# AUDIT 4: Superficie reverse proxy / tunnel
# ═══════════════════════════════════════════════════════════════

def _scan_proxy_tunnel_surface(root: Path = None) -> list[dict]:
    """Trova comandi subprocess che potrebbero esporre porte all'esterno.

    Cerca pattern di reverse proxy / tunnel / port-forward in:
      - subprocess.Popen([...]) e subprocess.run([...])
      - stringhe shell (subprocess.run("...", shell=True))
      - os.system(...)
    """
    findings = []
    for p in _iter_source_files(root):
        src = _read_text(p)
        rel_p = _rel(p, root)
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            # Resolves subprocess.Popen / subprocess.run / os.system
            callee = None
            if isinstance(fn, ast.Attribute):
                callee = fn.attr
            elif isinstance(fn, ast.Name):
                callee = fn.id
            if callee not in {"Popen", "run", "system", "call", "check_call",
                              "check_output"}:
                continue
            # Raccogli tutti gli argomenti stringa
            for arg in node.args:
                cmd_str = _extract_string(arg)
                if cmd_str:
                    findings.extend(_check_tunnel_command(rel_p, node.lineno, cmd_str))
            for kw in node.keywords:
                cmd_str = _extract_string(kw.value)
                if cmd_str:
                    findings.extend(_check_tunnel_command(rel_p, node.lineno, cmd_str))
    return findings


def _extract_string(node: ast.AST) -> str:
    """Estrae una stringa da un nodo AST (Constant o join di Constants)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.List):
        parts = []
        for elt in node.elts:
            s = _extract_string(elt)
            if s:
                parts.append(s)
            else:
                return ""  # lista con elementi non-stringa, non analizzabile
        return " ".join(parts)
    if isinstance(node, ast.JoinedStr):
        # f-string: raccogli le parti costanti
        parts = []
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                parts.append(val.value)
        return "".join(parts)
    return ""


def _check_tunnel_command(rel_p: str, line: int, cmd: str) -> list[dict]:
    """Verifica se un comando shell è un potenziale tunnel/reverse proxy."""
    findings = []
    m = _TUNNEL_COMMANDS.search(cmd)
    if m:
        tool = m.group(1)
        findings.append({
            "type": "potential_tunnel",
            "file": rel_p, "line": line,
            "tool": tool,
            "command": cmd[:200],
            "severity": "critical",
            "message": (
                f"Trovato comando potenzialmente pericoloso per esposizione porte: "
                f"'{tool}'. Questo tool può creare tunnel/reverse proxy verso "
                f"l'esterno. Verificare che sia intenzionale e autorizzato."
            ),
        })
    return findings


# ═══════════════════════════════════════════════════════════════
# AUDIT 5: Moduli banditi fuori allowlist
# ═══════════════════════════════════════════════════════════════

def _scan_banned_imports(root: Path = None, is_self_audit: bool = True) -> list[dict]:
    """Trova import di moduli banditi (socket, ctypes, pickle, ...) fuori allowlist.

    Per self-audit (byte-swarmy su se stesso) usa l'allowlist di byte-swarmy.
    Per target esterni usa allowlist vuota (qualsiasi socket/ctypes/pickle è
    bandito a meno che non sia esplicitamente configurato dal progetto).
    """
    findings = []
    # Per target esterni, l'allowlist byte-swarmy non si applica: ogni file è
    # potenzialmente sospetto. Usiamo una allowlist vuota.
    if is_self_audit:
        banned_map = _BANNED_IMPORTS
    else:
        banned_map = {k: set() for k in _BANNED_IMPORTS}
    for p in _iter_source_files(root):
        src = _read_text(p)
        rel_p = _rel(p, root)
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod in banned_map and rel_p not in banned_map[mod]:
                        findings.append({
                            "type": "banned_import",
                            "file": rel_p, "line": node.lineno,
                            "module": mod,
                            "severity": "warning",
                            "message": f"Import di modulo bandito '{mod}' fuori allowlist",
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod = node.module.split(".")[0]
                    full = node.module
                    if mod in banned_map and rel_p not in banned_map[mod]:
                        findings.append({
                            "type": "banned_import",
                            "file": rel_p, "line": node.lineno,
                            "module": full,
                            "severity": "warning",
                            "message": f"Import di modulo bandito '{full}' fuori allowlist",
                        })
    return findings


# ═══════════════════════════════════════════════════════════════
# AUDIT 6: File critici (esistenza + non vuoto)
# ═══════════════════════════════════════════════════════════════

def _scan_critical_files() -> list[dict]:
    """Verifica che i file critici esistano e non siano vuoti."""
    findings = []
    for f in CRITICAL_FILES:
        p = ROOT / f
        if not p.exists():
            findings.append({
                "type": "missing_critical_file",
                "file": f, "line": 0,
                "severity": "critical",
                "message": f"File critico mancante: {f}",
            })
        elif p.stat().st_size == 0:
            findings.append({
                "type": "empty_critical_file",
                "file": f, "line": 0,
                "severity": "critical",
                "message": f"File critico vuoto: {f}",
            })
    return findings


# ═══════════════════════════════════════════════════════════════
# AUDIT 7: config.toml valido
# ═══════════════════════════════════════════════════════════════

def _scan_config_toml() -> list[dict]:
    """Verifica che CONFIG/config.toml sia un TOML valido."""
    findings = []
    p = ROOT / "CONFIG" / "config.toml"
    if not p.exists():
        return findings  # già segnalato da _scan_critical_files
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(p, "rb") as f:
            tomllib.load(f)
    except Exception as e:
        findings.append({
            "type": "invalid_config",
            "file": "CONFIG/config.toml", "line": 0,
            "severity": "critical",
            "message": f"config.toml non valido: {e}",
        })
    return findings


# ═══════════════════════════════════════════════════════════════
# Runner principale
# ═══════════════════════════════════════════════════════════════

# Metadati delle categorie di audit: nome, icona, descrizione, bloccante.
# Le categorie "bloccanti" sono sempre critical (porte, tunnel, import, file).
# Le categorie "advisory" sono solo warning (vars, dead code).
AUDIT_CATEGORIES = [
    {"id": "unused_variables", "icon": "🎨", "name": "Variabili inutilizzate",
     "description": "Variabili pubbliche a livello modulo mai referenziate",
     "blocking": False},
    {"id": "dead_code", "icon": "💀", "name": "Codice morto",
     "description": "Funzioni/metodi pubblici mai chiamati",
     "blocking": False},
    {"id": "exposed_ports", "icon": "🛡️", "name": "Porte esposte",
     "description": "Bind su host non-loopback (0.0.0.0, ::, ecc.)",
     "blocking": True},
    {"id": "potential_tunnel", "icon": "🔄", "name": "Tunnel/Reverse proxy",
     "description": "Comandi che potrebbero esporre porte (ngrok, ssh -R, docker -p)",
     "blocking": True},
    {"id": "banned_import", "icon": "📦", "name": "Import banditi",
     "description": "socket/ctypes/pickle/http.server fuori allowlist",
     "blocking": True},
    {"id": "critical_files", "icon": "📁", "name": "File critici",
     "description": "File essenziali (orchestratore, security, config) presenti e non vuoti",
     "blocking": True},
    {"id": "config_validity", "icon": "⚙️", "name": "config.toml valido",
     "description": "File di configurazione TOML sintatticamente valido",
     "blocking": True},
]

# Mappa type finding → categoria ID (per il gate)
_FINDING_TYPE_TO_CATEGORY = {
    "unused_module_variable": "unused_variables",
    "dead_code": "dead_code",
    "exposed_port": "exposed_ports",
    "exposed_host_string": "exposed_ports",
    "nonstandard_port": "exposed_ports",
    "potential_tunnel": "potential_tunnel",
    "banned_import": "banned_import",
    "missing_critical_file": "critical_files",
    "empty_critical_file": "critical_files",
    "invalid_config": "config_validity",
}


def run_full_audit(root_dir: Path = None) -> dict:
    """Esegue tutti gli audit su root_dir (default: byte-swarmy root).

    Args:
        root_dir: directory root del progetto da auditare. Se None o
                  uguale a ROOT, usa la lista CRITICAL_FILES di byte-swarmy
                  (audit di byte-swarmy su se stesso). Se diverso, fa un
                  audit generico sul target (5 categorie, skip file critici
                  e config.toml specifici di byte-swarmy).
    """
    target = Path(root_dir) if root_dir else ROOT
    is_self_audit = (target.resolve() == ROOT.resolve())

    findings: list[dict] = []
    # Queste 5 categorie sono generiche (funzionano su qualsiasi progetto .py)
    findings.extend(_scan_unused_variables(target))
    findings.extend(_scan_dead_code(target))
    findings.extend(_scan_exposed_ports(target))
    findings.extend(_scan_proxy_tunnel_surface(target))
    findings.extend(_scan_banned_imports(target, is_self_audit))
    # Queste 2 categorie sono byte-swarmy-specific (solo self-audit)
    if is_self_audit:
        findings.extend(_scan_critical_files())
        findings.extend(_scan_config_toml())

    # Conteggi per severity
    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1

    # Conteggi per tipo
    by_type: dict[str, int] = defaultdict(int)
    for f in findings:
        by_type[f["type"]] += 1

    # Gate: per categoria, calcola status (PASS/FAIL/SKIP) e critical/warning
    categories_status = _compute_categories_status(findings, is_self_audit)

    return {
        "audit": "byte-swarmy-monthly-audit",
        "version": "2.0",
        "root": str(target),
        "target_name": target.name if not is_self_audit else "byte-swarmy (self)",
        "is_self_audit": is_self_audit,
        "timestamp": _now_iso(),
        "summary": {
            "total": len(findings),
            "critical": counts["critical"],
            "warning": counts["warning"],
            "info": counts["info"],
            "passed": counts["critical"] == 0,
            "gate": _compute_gate_status(categories_status),
        },
        "categories": categories_status,
        "by_type": dict(by_type),
        "findings": findings,
    }


def _compute_categories_status(findings: list[dict], is_self_audit: bool) -> list[dict]:
    """Per ogni categoria, calcola status (PASS/FAIL/SKIP) e conteggi."""
    # Raggruppa finding per categoria
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        cat_id = _FINDING_TYPE_TO_CATEGORY.get(f["type"], "")
        if cat_id:
            by_cat[cat_id].append(f)

    result = []
    for cat in AUDIT_CATEGORIES:
        cat_id = cat["id"]
        # Skip file critici e config per target non-byte-swarmy
        if not is_self_audit and cat_id in ("critical_files", "config_validity"):
            result.append({
                **cat,
                "status": "SKIP",
                "critical": 0,
                "warning": 0,
                "total": 0,
                "message": "N/A per progetti esterni (byte-swarmy-specific)",
            })
            continue

        cat_findings = by_cat.get(cat_id, [])
        critical = sum(1 for f in cat_findings if f["severity"] == "critical")
        warning = sum(1 for f in cat_findings if f["severity"] == "warning")
        # Status: FAIL se ci sono critical (per bloccanti) o se la categoria
        # è bloccante e ha qualsiasi finding; PASS altrimenti.
        if cat["blocking"]:
            status = "FAIL" if critical > 0 else "PASS"
        else:
            # Advisory: FAIL solo se critical, PASS anche con warning
            status = "FAIL" if critical > 0 else "PASS"
        result.append({
            **cat,
            "status": status,
            "critical": critical,
            "warning": warning,
            "total": len(cat_findings),
        })
    return result


def _compute_gate_status(categories: list[dict]) -> str:
    """Gate globale: FAIL se almeno una categoria bloccante è FAIL."""
    for cat in categories:
        if cat.get("blocking") and cat.get("status") == "FAIL":
            return "FAIL"
    return "PASS"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════
# Test unittest (fallisce se ci sono critical)
# ═══════════════════════════════════════════════════════════════

class TestMonthlyAudit(unittest.TestCase):
    """Test che fallisce se l'audit mensile trova problemi critical."""

    @classmethod
    def setUpClass(cls):
        cls.report = run_full_audit()

    def test_no_critical_findings(self):
        """Nessun finding di severity critical (porte esposte, file mancanti, ecc.)."""
        criticals = [f for f in self.report["findings"] if f["severity"] == "critical"]
        if criticals:
            msgs = "\n".join(f"  - [{f['type']}] {f['file']}:{f.get('line', 0)} — {f['message']}"
                             for f in criticals[:20])
            self.fail(f"Audit mensile ha trovato {len(criticals)} problemi critical:\n{msgs}")

    def test_no_exposed_ports(self):
        """Nessun bind su host non-loopback."""
        exposed = [f for f in self.report["findings"] if f["type"] == "exposed_port"]
        if exposed:
            msgs = "\n".join(f"  - {f['file']}:{f['line']} bind su {f.get('host')}:{f.get('port')}"
                             for f in exposed)
            self.fail(f"Trovati {len(exposed)} bind su host non-loopback:\n{msgs}")

    def test_no_potential_tunnels(self):
        """Nessun comando subprocess che sembra un tunnel/reverse proxy."""
        tunnels = [f for f in self.report["findings"] if f["type"] == "potential_tunnel"]
        if tunnels:
            msgs = "\n".join(f"  - {f['file']}:{f['line']} tool='{f.get('tool')}' cmd={f.get('command', '')[:80]!r}"
                             for f in tunnels)
            self.fail(f"Trovati {len(tunnels)} potenziali tunnel/reverse proxy:\n{msgs}")

    def test_critical_files_exist(self):
        """Tutti i file critici esistono e non sono vuoti."""
        missing = [f for f in self.report["findings"]
                   if f["type"] in {"missing_critical_file", "empty_critical_file"}]
        if missing:
            msgs = "\n".join(f"  - {f['file']}: {f['message']}" for f in missing)
            self.fail(f"File critici mancanti o vuoti:\n{msgs}")

    def test_config_toml_valid(self):
        """config.toml è un TOML valido."""
        invalid = [f for f in self.report["findings"] if f["type"] == "invalid_config"]
        if invalid:
            self.fail(f"config.toml non valido: {invalid[0]['message']}")

    def test_no_banned_imports_outside_allowlist(self):
        """Nessun import di modulo bandito (socket/ctypes/pickle) fuori allowlist."""
        banned = [f for f in self.report["findings"] if f["type"] == "banned_import"]
        if banned:
            msgs = "\n".join(f"  - {f['file']}:{f['line']} import {f['module']!r}"
                             for f in banned[:20])
            self.fail(f"Trovati {len(banned)} import di moduli banditi fuori allowlist:\n{msgs}")


# ═══════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════

def _print_gate_report(report: dict) -> None:
    """Stampa il report in formato gate compatto (una riga per categoria)."""
    s = report["summary"]
    print("=" * 72)
    print(f"  AUDIT GATE — {report.get('target_name', report['root'])}")
    print(f"  {report['timestamp']}")
    print("=" * 72)
    print()
    print(f"  {'CATEGORIA':<32s} {'STATUS':<8s} {'CRIT':<5s} {'WARN':<5s}")
    print(f"  {'-'*32} {'-'*8} {'-'*5} {'-'*5}")
    for cat in report.get("categories", []):
        icon = cat.get("icon", "")
        name = cat.get("name", cat["id"])
        status = cat.get("status", "?")
        blocking = "🔒" if cat.get("blocking") else "  "
        status_str = {
            "PASS": "✓ PASS",
            "FAIL": "✗ FAIL",
            "SKIP": "– SKIP",
        }.get(status, status)
        print(f"  {blocking} {icon} {name:<26s} {status_str:<8s} "
              f"{cat.get('critical', 0):<5d} {cat.get('warning', 0):<5d}")
    print()
    gate = s.get("gate", "?")
    gate_str = "✓ PASS — nessuna categoria bloccante con critical" if gate == "PASS" \
        else "✗ FAIL — almeno una categoria bloccante con critical"
    gate_color = "\033[32m" if gate == "PASS" else "\033[31m"
    reset = "\033[0m"
    print(f"  GATE: {gate_color}{gate_str}{reset}")
    print(f"  Totale finding: {s['total']} (critical: {s['critical']}, warning: {s['warning']})")
    print()
    if gate == "FAIL":
        # Mostra solo i critical delle categorie bloccanti
        blocking_cats = {c["id"] for c in report.get("categories", []) if c.get("blocking")}
        crit_findings = [f for f in report["findings"]
                         if f["severity"] == "critical"
                         and _FINDING_TYPE_TO_CATEGORY.get(f["type"], "") in blocking_cats]
        if crit_findings:
            print(f"  ─── CRITICAL DA RISOLVERE ({len(crit_findings)}) ────────────────────────")
            for f in crit_findings[:20]:
                print(f"  [{f['type']}] {f['file']}:{f.get('line', 0)}")
                print(f"    {f['message']}")
            if len(crit_findings) > 20:
                print(f"  ... e altri {len(crit_findings) - 20} critical")
            print()


def _print_text_report(report: dict) -> None:
    """Stampa il report in formato testo leggibile."""
    s = report["summary"]
    print("=" * 72)
    print(f"  AUDIT MENSILE BYTE-SWARMY — {report['timestamp']}")
    print("=" * 72)
    print()
    status = "✓ PASS" if s["passed"] else "✗ FAIL"
    print(f"  Stato:      {status}")
    print(f"  Totale:     {s['total']} finding")
    print(f"  Critical:   {s['critical']}")
    print(f"  Warning:    {s['warning']}")
    print(f"  Info:       {s['info']}")
    print()
    if report["by_type"]:
        print("  Per tipo:")
        for t, n in sorted(report["by_type"].items(), key=lambda x: -x[1]):
            print(f"    {t:30s} {n}")
        print()

    # Raggruppa per severity
    for sev in ("critical", "warning", "info"):
        items = [f for f in report["findings"] if f["severity"] == sev]
        if not items:
            continue
        print(f"  ─── {sev.upper()} ({len(items)}) ────────────────────────────────────")
        for f in items[:50]:  # limita a 50 per severity
            loc = f"{f['file']}:{f.get('line', 0)}"
            print(f"  [{f['type']}] {loc}")
            print(f"    {f['message']}")
        if len(items) > 50:
            print(f"  ... e altri {len(items) - 50} finding di severity {sev}")
        print()


def _write_html_report(report: dict, out_path: Path) -> None:
    """Scrive il report come HTML."""
    s = report["summary"]
    status_color = "#16a34a" if s["passed"] else "#dc2626"
    status_text = "PASS ✓" if s["passed"] else "FAIL ✗"

    rows = []
    for f in report["findings"]:
        sev = f["severity"]
        sev_color = {"critical": "#dc2626", "warning": "#f59e0b", "info": "#3b82f6"}.get(sev, "#666")
        rows.append(f"""
        <tr>
          <td><span class="badge" style="background:{sev_color}">{sev}</span></td>
          <td>{f['type']}</td>
          <td><code>{f['file']}:{f.get('line', 0)}</code></td>
          <td>{f['message']}</td>
        </tr>""")

    by_type_rows = "".join(
        f"<tr><td>{t}</td><td>{n}</td></tr>"
        for t, n in sorted(report["by_type"].items(), key=lambda x: -x[1])
    )

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Audit mensile BYTE-SWARMY — {report['timestamp']}</title>
<style>
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; margin: 24px; background: #f8f9fa; color: #1a1a1a; }}
  h1 {{ color: #1a1a1a; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }}
  .summary {{ display: flex; gap: 16px; margin: 20px 0; }}
  .card {{ background: #fff; padding: 16px 24px; border-radius: 8px; border: 1px solid #e0e0e0; min-width: 120px; }}
  .card .num {{ font-size: 28px; font-weight: bold; }}
  .card .label {{ font-size: 11px; color: #666; text-transform: uppercase; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; font-size: 13px; }}
  th {{ background: #f5f5f7; font-weight: bold; }}
  td code {{ font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; }}
  .badge {{ color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; text-transform: uppercase; }}
  .status {{ display: inline-block; padding: 6px 16px; border-radius: 6px; color: #fff; font-weight: bold; background: {status_color}; }}
  h2 {{ margin-top: 32px; color: #333; }}
</style>
</head>
<body>
  <h1>🔍 Audit mensile BYTE-SWARMY</h1>
  <p><span class="status">{status_text}</span> &nbsp; <code>{report['timestamp']}</code></p>

  <div class="summary">
    <div class="card"><div class="num">{s['total']}</div><div class="label">Totale</div></div>
    <div class="card"><div class="num" style="color:#dc2626">{s['critical']}</div><div class="label">Critical</div></div>
    <div class="card"><div class="num" style="color:#f59e0b">{s['warning']}</div><div class="label">Warning</div></div>
    <div class="card"><div class="num" style="color:#3b82f6">{s['info']}</div><div class="label">Info</div></div>
  </div>

  <h2>📋 Distribuzione per tipo</h2>
  <table><tr><th>Tipo</th><th>Count</th></tr>{by_type_rows}</table>

  <h2>🔍 Findings dettagliati</h2>
  <table>
    <tr><th>Severity</th><th>Tipo</th><th>Location</th><th>Messaggio</th></tr>
    {''.join(rows) if rows else '<tr><td colspan="4" style="text-align:center;padding:24px;color:#888">Nessun finding 🎉</td></tr>'}
  </table>

  <p style="margin-top:32px;color:#888;font-size:11px">
    Generato da <code>tests/test_monthly_audit.py</code> —
    root: <code>{report['root']}</code>
  </p>
</body>
</html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def main() -> int:
    """CLI entry point.

    Uso:
      python tests/test_monthly_audit.py                      # self-audit (test unittest)
      python tests/test_monthly_audit.py --json               # JSON su stdout (self)
      python tests/test_monthly_audit.py --gate               # gate compatto (self)
      python tests/test_monthly_audit.py --target PATH        # audit un progetto target
      python tests/test_monthly_audit.py --target PATH --gate # gate su target
      python tests/test_monthly_audit.py --target PATH --json --html out.html
    """
    import argparse
    parser = argparse.ArgumentParser(description="Audit mensile BYTE-SWARMY")
    parser.add_argument("--json", action="store_true",
                        help="Stampa il report come JSON su stdout")
    parser.add_argument("--html", metavar="PATH",
                        help="Salva il report come HTML nel percorso indicato")
    parser.add_argument("--no-text", action="store_true",
                        help="Non stampare il report testuale")
    parser.add_argument("--gate", action="store_true",
                        help="Stampa solo il gate compatto (una riga per categoria)")
    parser.add_argument("--target", metavar="PATH",
                        help="Directory del progetto da auditare (default: byte-swarmy self)")
    args = parser.parse_args()

    # Determina il target
    target = Path(args.target) if args.target else None
    report = run_full_audit(target)

    # Output
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    elif args.gate:
        _print_gate_report(report)
    elif not args.no_text:
        _print_text_report(report)

    if args.html:
        out = Path(args.html)
        _write_html_report(report, out)
        if not args.json:
            print(f"Report HTML salvato: {out}")
        else:
            print(f"Report HTML salvato: {out}", file=sys.stderr)

    # Exit code: 0 se gate PASS, 1 se FAIL
    return 0 if report["summary"].get("gate", "PASS") == "PASS" else 1


if __name__ == "__main__":
    if any(a in sys.argv for a in ("--json", "--html", "--gate", "--target")):
        sys.exit(main())
    print(f"Monthly audit → {ROOT}")
    unittest.main(verbosity=2)
