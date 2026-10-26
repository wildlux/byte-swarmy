"""
security.py — policy di sicurezza centralizzata per BYTE-SWARMY.

Due livelli, indipendenti:

1. Validazione strutturale dei comandi bash:
   - niente shell (`shell=False`), tokenizzazione con shlex;
   - nessun operatore di shell (pipe, redirect, ;, &, backtick, $(...));
   - comando in allowlist;
   - argomenti-path confinati in `project/`;
   - blacklist regex come secondo strato (difesa in profondità).

2. Confinamento dei path usati dai tool (`read_file`, `write_file`):
   - niente path assoluti, `~`, `..`;
   - niente escape tramite symlink;
   - niente file sensibili (`.ssh`, `.git-credentials`, `.env`, `.git/`, ...).

Ogni blocco viene registrato in `logs/security.log` (rotazione 1 MB x 5).

Il modulo non richiede root e non modifica il sistema.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Limiti
# ---------------------------------------------------------------------------

MAX_COMMAND_LEN = 2000
MAX_PATH_LEN = 512
MAX_PATTERN_LEN = 500

# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

_SECURITY_LOGGER: Optional[logging.Logger] = None


def get_security_logger(log_dir: str | Path | None = None) -> logging.Logger:
    """Logger dedicato, append + rotazione (1 MB, 5 file)."""
    global _SECURITY_LOGGER
    if _SECURITY_LOGGER is not None:
        return _SECURITY_LOGGER

    if log_dir is None:
        log_dir = os.environ.get("BYTE_SWARM_SECURITY_LOG_DIR", "./logs")

    logger = logging.getLogger("byte-swarmy.security")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        try:
            directory = Path(log_dir)
            directory.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                directory / "security.log",
                maxBytes=1_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))
            logger.addHandler(handler)
        except OSError:
            # Non deve mai bloccare l'esecuzione: se il log non è scrivibile,
            # il logger resta silenzioso ma la policy continua a funzionare.
            logger.addHandler(logging.NullHandler())

    _SECURITY_LOGGER = logger
    return logger


def log_security_event(event_type: str, details: str = "",
                       severity: str = "WARNING",
                       worker: str = "") -> None:
    """Scrive un evento di sicurezza. Non solleva mai eccezioni."""
    try:
        level = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
        }.get(str(severity).upper(), logging.WARNING)

        message = f"{event_type} worker={worker or '-'}"
        if details:
            message += f" {details}"
        get_security_logger().log(level, message)
    except Exception:
        pass


class SecurityError(Exception):
    """Violazione di una regola di sicurezza (path o comando)."""


# ---------------------------------------------------------------------------
# Pattern bloccati (secondo strato, sempre attivo)
# ---------------------------------------------------------------------------

BLOCKED_BASH_PATTERNS: Tuple[str, ...] = (
    # distruzione
    r"\brm\s+-[^\s]*[rRfF]",
    r"\brm\s+--(recursive|force)",
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bdd\b",
    r"\bshred\b",
    # privilegi / sistema
    r"\bsudo\b",
    r"\bsu\s",
    r"\bdoas\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bchgrp\b",
    r"\bsystemctl\b",
    r"\bservice\b",
    r"\bcrontab\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    r"\bkill(all)?\b",
    r"\bpkill\b",
    r"\bkill\b",
    r"\bmount\b",
    r"\bumount\b",
    r"\biptables\b",
    r"\bip6tables\b",
    r"\bnft\b",
    r"\bifconfig\b",
    r"\bip\b\s+(addr|link|route|rule)",
    # rete / esfiltrazione
    r"\bcurl\b",
    r"\bwget\b",
    r"\bssh\b",
    r"\bscp\b",
    r"\bsftp\b",
    r"\brsync\b",
    r"\bnc\b",
    r"\bncat\b",
    r"\bnetcat\b",
    r"\bsocat\b",
    r"\btelnet\b",
    r"/dev/tcp",
    # package manager / codice arbitrario
    r"\bapt(-get)?\b",
    r"\bpacman\b",
    r"\byum\b",
    r"\bdnf\b",
    r"\bzypper\b",
    r"\bpip3?\b",
    r"\bnpm\b",
    r"\byarn\b",
    r"\bcargo\b",
    r"\bgo\s+install\b",
    r"\bpython[0-9.]*\s+-c\b",
    r"\bpython[0-9.]*\s+-\s",
    r"\bperl\s+-e\b",
    r"\bruby\s+-e\b",
    r"\bnode\s+-e\b",
    r"\bbash\s+-c\b",
    r"\bsh\s+-c\b",
    # shell injection
    r"\$\(",
    r"`",
    r"\beval\b",
    r"\bexec\b",
    r"\bsource\b",
    # segreti / path di sistema
    r"/etc/",
    r"/var/",
    r"/root/",
    r"/boot/",
    r"/proc/",
    r"/sys/",
    r"/home/",
    r"/dev/",
    r"\.ssh\b",
    r"\.gnupg\b",
    r"\.aws\b",
    r"\.git-credentials\b",
    r"\.netrc\b",
    r"\.bashrc\b",
    r"\.bash_profile\b",
    r"\.profile\b",
    r"\.zshrc\b",
    r"\.env\b",
    r"id_rsa\b",
    r"id_ed25519\b",
    # git verso l'esterno
    r"\bgit\s+(push|pull|remote|clone|fetch|config|init)\b",
    # scrittura/lettura pericolosa con find
    r"-(exec|execdir|delete|ok|okdir|fprint|fprint0|fprintf|fls)\b",
)

_BLOCKED_RE = tuple(re.compile(p, re.IGNORECASE) for p in BLOCKED_BASH_PATTERNS)

# Comandi eseguibili dai worker (argv[0]).
ALLOWED_COMMANDS = frozenset({
    # esplorazione
    "pwd", "ls", "cat", "head", "tail", "wc", "file", "stat",
    "grep", "find", "diff", "cmp", "echo", "printf", "test", "[", "true", "false",
    # file (con path confinati)
    "mkdir", "touch", "rm", "rmdir", "cp", "mv",
    # build / test
    "gcc", "g++", "cc", "clang", "clang++", "make", "cmake",
    "python", "python3", "pytest",
    # git locale (sola lettura + commit)
    "git",
    # cwd (no-op: la cwd è già project/)
    "cd",
})

# Sottocomandi git ammessi. push/pull/remote non sono qui: usare ./sync.sh.
ALLOWED_GIT_SUBCOMMANDS = frozenset({"status", "diff", "log", "show", "add", "commit"})

# Flag git che possono leggere/scrivere fuori dal repo o eseguire comandi.
BLOCKED_GIT_FLAGS = frozenset({
    "-c", "--config", "--git-dir", "--work-tree", "--exec-path",
    "--upload-pack", "--receive-pack", "--namespace",
})

# Flag di find che eseguono comandi o cancellano.
BLOCKED_FIND_FLAGS = frozenset({
    "-exec", "-execdir", "-delete", "-ok", "-okdir",
    "-fprint", "-fprint0", "-fprintf", "-fls",
})

# Flag pericolosi per i compilatori (plugin, linker script, toolchain esterna).
BLOCKED_COMPILER_PREFIXES = (
    "-B", "-specs", "-wrapper", "-fplugin", "-Xlinker", "-Wl,", "-Wp,", "@",
)

# Nomi/parti di path sempre vietati ai tool, anche dentro project/.
SENSITIVE_PARTS = frozenset({".git", ".ssh", ".gnupg", ".aws", ".config"})
SENSITIVE_NAMES = frozenset({
    ".env", ".env.local", ".env.production", ".git-credentials", ".netrc",
    ".bashrc", ".bash_profile", ".profile", ".zshrc", ".zprofile",
    "id_rsa", "id_rsa.pub", "id_ed25519", "id_ed25519.pub",
    "id_ecdsa", "id_ecdsa.pub", "credentials", "credentials.json",
    "secrets.json", "secrets.yaml", "secrets.yml", "authorized_keys",
})

SHELL_OPERATORS = ("`", "$(", "${", "|", ";", "&", ">", "<", "\\", "\n", "\r", "\x00")


# ---------------------------------------------------------------------------
# Helper path
# ---------------------------------------------------------------------------

def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_sensitive_part(path: Path) -> bool:
    for part in path.parts:
        if part in SENSITIVE_PARTS:
            return True
    return path.name in SENSITIVE_NAMES


def _looks_like_path(token: str) -> bool:
    return (
        token.startswith(("./", "../", "~/", "/"))
        or "/" in token
        or token in (".", "..")
    )


def _strip_project_prefix(text: str) -> str:
    """Accetta sia 'project/x' sia 'x' come path dentro la project root.

    La cwd dei worker è già `project/`: scrivere `project/` due volte è
    l'errore più comune dei modelli piccoli. Qui lo normalizziamo.
    """
    if text in ("project", "./project", "project/", "./project/"):
        return "."
    for prefix in ("project/", "./project/"):
        if text.startswith(prefix):
            return text[len(prefix):] or "."
    return text


def safe_project_path(path: str, project_root: str | Path,
                      *, for_write: bool = False,
                      must_exist: bool = False) -> Path:
    """Risolve un path confinandolo in `project_root`.

    Solleva SecurityError per path assoluti, `~`, `..`, symlink che escono
    dalla root e file sensibili. Non crea nulla.
    """
    if not isinstance(path, (str, os.PathLike)):
        raise SecurityError("path non valido")
    text = os.fspath(path).strip()
    if not text:
        raise SecurityError("path vuoto")
    if len(text) > MAX_PATH_LEN:
        raise SecurityError("path troppo lungo")
    if "\x00" in text:
        raise SecurityError("path contiene NUL")
    if text.startswith("~"):
        raise SecurityError("path con '~' non consentito")
    if text.startswith("/") or Path(text).is_absolute():
        raise SecurityError("path assoluto non consentito")
    text = _strip_project_prefix(text)
    if ".." in Path(text).parts:
        raise SecurityError("path con '..' non consentito")

    root = Path(project_root).resolve()
    raw = root / text
    if for_write and raw.is_symlink():
        raise SecurityError("scrittura su symlink non consentita")
    full = raw.resolve()

    if not _is_within(full, root):
        raise SecurityError("path fuori da project/")
    if _has_sensitive_part(full):
        raise SecurityError("path sensibile bloccato")
    if full == root and for_write:
        raise SecurityError("impossibile scrivere sulla root del progetto")
    if must_exist and not full.exists():
        raise SecurityError("file non trovato")

    # Un symlink interno che punta fuori è già stato intercettato da resolve();
    # un symlink come target di scrittura viene rifiutato esplicitamente.
    if for_write and full.is_symlink():
        raise SecurityError("scrittura su symlink non consentita")

    return full


def _check_token_path(token: str, root: Path) -> None:
    """Valida un token che sembra un path (o che contiene un path)."""
    if token.startswith("-"):
        # Flag: controlla solo l'eventuale valore dopo '=' (es. --output=/tmp/x)
        if "=" in token:
            value = token.split("=", 1)[1]
            if value and _looks_like_path(value):
                _check_path_value(value, root)
        return
    if not _looks_like_path(token):
        return
    _check_path_value(token, root)


def _check_path_value(value: str, root: Path) -> None:
    if value.startswith("~"):
        raise SecurityError("'~' non consentito")
    if value.startswith("/") or Path(value).is_absolute():
        raise SecurityError("path assoluto non consentito")
    value = _strip_project_prefix(value)
    if ".." in Path(value).parts:
        raise SecurityError("'..' non consentito")
    full = (root / value).resolve()
    if not _is_within(full, root):
        raise SecurityError("path fuori da project/")
    if _has_sensitive_part(full):
        raise SecurityError("path sensibile bloccato")


# ---------------------------------------------------------------------------
# Validazione comandi
# ---------------------------------------------------------------------------

def _block(reason: str) -> Tuple[bool, str]:
    return False, reason


def _ok() -> Tuple[bool, str]:
    return True, ""


def _next_value(argv: Sequence[str], index: int) -> Optional[str]:
    return argv[index + 1] if index + 1 < len(argv) else None


def _validate_git(argv: Sequence[str], root: Path) -> Tuple[bool, str]:
    if len(argv) < 2:
        return _block("git richiede un sottocomando")
    sub = argv[1].lower()
    if sub.startswith("-"):
        return _block("git: opzioni globali non consentite")
    if sub not in ALLOWED_GIT_SUBCOMMANDS:
        return _block(
            f"git {sub} non consentito: usa i tool git_* o ./sync.sh come utente reale"
        )

    for token in argv[2:]:
        if token in BLOCKED_GIT_FLAGS:
            return _block(f"git: flag {token} non consentito")
        if token.startswith("-") and "=" in token:
            flag = token.split("=", 1)[0]
            if flag in BLOCKED_GIT_FLAGS:
                return _block(f"git: flag {flag} non consentito")

    if sub == "commit":
        if "-m" not in argv and "--message" not in argv:
            return _block("git commit richiede -m \"messaggio\"")
        if "--amend" in argv:
            return _block("git commit --amend non consentito")

    return _ok()


def _validate_find(argv: Sequence[str], root: Path) -> Tuple[bool, str]:
    for token in argv[1:]:
        if token in BLOCKED_FIND_FLAGS:
            return _block(f"find {token} non consentito")
        if token in ("-delete",):
            return _block("find -delete non consentito: usa rm project/file")
        if token.startswith("-") and "=" in token:
            flag = token.split("=", 1)[0]
            if flag in BLOCKED_FIND_FLAGS:
                return _block(f"find {flag} non consentito")

    # La root di find deve essere il progetto.
    for token in argv[1:]:
        if token.startswith("-"):
            continue
        _check_path_value(token, root)
        break
    return _ok()


def _validate_python(argv: Sequence[str], root: Path) -> Tuple[bool, str]:
    if len(argv) < 2:
        return _block("python richiede lo script da eseguire (es. project/main.py)")
    target = argv[1]
    if target in ("-c", "-"):
        return _block("python -c non consentito: scrivi un file in project/ ed eseguilo")
    if target.startswith("-m"):
        if target != "-m":
            return _block("usa 'python -m pytest|unittest' oppure esegui project/file.py")
        module = _next_value(argv, 1)
        if module not in ("pytest", "unittest"):
            return _block("python -m: solo pytest e unittest sono consentiti")
        for token in argv[3:]:
            _check_token_path(token, root)
        return _ok()
    if target.startswith("-"):
        return _block(f"python: opzione {target} non consentita")
    target = _strip_project_prefix(target)
    _check_path_value(target, root)
    full = (root / target).resolve()
    if not full.is_file():
        return _block(f"file non trovato: {target}")
    if full.suffix != ".py":
        return _block("python: eseguibile solo file .py dentro project/")
    return _ok()


def _validate_compiler(argv: Sequence[str], root: Path) -> Tuple[bool, str]:
    for i, token in enumerate(argv[1:], start=1):
        for prefix in BLOCKED_COMPILER_PREFIXES:
            if token == prefix or token.startswith(prefix):
                return _block(f"compilatore: {prefix} non consentito")
        if token in ("-o", "-MF", "-MJ"):
            value = _next_value(argv, i)
            if value is None:
                return _block(f"compilatore: {token} richiede un path")
            _check_path_value(value, root)
        elif token.startswith(("-specs=", "-wrapper=")):
            return _block("compilatore: flag non consentito")
        else:
            _check_token_path(token, root)
    return _ok()


def _validate_make(argv: Sequence[str], root: Path) -> Tuple[bool, str]:
    for i, token in enumerate(argv[1:], start=1):
        if token in ("-C", "--directory", "-f", "--file", "--makefile"):
            value = _next_value(argv, i)
            if value is None:
                return _block(f"make: {token} richiede un path")
            _check_path_value(value, root)
        elif token.startswith(("-C=", "--directory=", "-f=", "--makefile=")):
            _check_token_path(token, root)
        elif token.startswith("--directory=") or token.startswith("--file="):
            _check_token_path(token, root)
    return _ok()


def _validate_rm(argv: Sequence[str], root: Path) -> Tuple[bool, str]:
    for token in argv[1:]:
        if token.startswith("-") and token != "-":
            return _block(
                "rm con opzioni non consentito (niente -r/-f): usa 'rm project/file'"
            )
    if len(argv) < 2:
        return _block("rm richiede un file: 'rm project/file'")
    return _ok()


def _validate_cd(argv: Sequence[str]) -> Tuple[bool, str]:
    if len(argv) == 1:
        return _ok()
    if len(argv) == 2 and argv[1] in ("project", "./project", "project/"):
        return _ok()
    return _block("cd consentito solo nella project root (la cwd è già project/)")


def validate_bash_command(cmd: str,
                          project_root: str | Path = ".") -> Tuple[bool, str]:
    """Valida un comando prima dell'esecuzione.

    Ritorna `(True, "")` se il comando è ammesso, `(False, motivo)` altrimenti.
    Il motivo è pensato per essere mostrato direttamente al worker LLM.

    Nota: il comando viene poi eseguito con `shell=False`; quindi pipe,
    redirezioni e concatenazioni non funzionano nemmeno se non bloccate qui.
    """
    if not isinstance(cmd, str):
        return _block("comando non valido (deve essere una stringa)")
    text = cmd.strip()
    if not text:
        return _block("comando vuoto")
    if len(text) > MAX_COMMAND_LEN:
        return _block(f"comando troppo lungo (max {MAX_COMMAND_LEN} caratteri)")

    for operator in SHELL_OPERATORS:
        if operator in text:
            return _block(
                f"operatore di shell {operator!r} non consentito: esegui un solo comando semplice"
            )

    # Blacklist regex (secondo strato).
    for pattern, regex in zip(BLOCKED_BASH_PATTERNS, _BLOCKED_RE):
        if regex.search(text):
            return _block(f"pattern bloccato: {pattern}")

    try:
        argv = shlex.split(text, posix=True)
    except ValueError as exc:
        return _block(f"comando non tokenizzabile: {exc}")
    if not argv:
        return _block("comando vuoto")

    root = Path(project_root).resolve()
    name = argv[0]
    base = os.path.basename(name)

    if name.startswith(("project/", "./project/")):
        full = (root / _strip_project_prefix(name)).resolve()
        if not _is_within(full, root):
            return _block("eseguibile fuori da project/")
        if _has_sensitive_part(full):
            return _block("eseguibile in path sensibile")
        if not full.is_file() or not os.access(full, os.X_OK):
            return _block(f"eseguibile non trovato o non eseguibile: {name}")
        for token in argv[1:]:
            try:
                _check_token_path(token, root)
            except SecurityError as exc:
                return _block(str(exc))
        return _ok()

    if "/" in name:
        return _block("percorso del comando non consentito (usa il nome del comando)")

    if base not in ALLOWED_COMMANDS:
        return _block(
            f"comando '{base}' non in allowlist. Comandi ammessi: "
            "ls, cat, head, tail, wc, grep, find, diff, mkdir, touch, rm, cp, mv, "
            "gcc, g++, make, python, pytest, git (solo locale)"
        )

    try:
        for token in argv[1:]:
            _check_token_path(token, root)
    except SecurityError as exc:
        return _block(str(exc))

    # Regole specifiche.
    try:
        if base == "git":
            return _validate_git(argv, root)
        if base == "find":
            return _validate_find(argv, root)
        if base in ("python", "python3"):
            return _validate_python(argv, root)
        if base in ("gcc", "g++", "cc", "clang", "clang++"):
            return _validate_compiler(argv, root)
        if base in ("make", "cmake"):
            return _validate_make(argv, root)
        if base == "rm":
            return _validate_rm(argv, root)
        if base == "cd":
            return _validate_cd(argv)
        if base == "rmdir":
            for token in argv[1:]:
                if token.startswith("-"):
                    return _block("rmdir con opzioni non consentito")
    except SecurityError as exc:
        return _block(str(exc))

    return _ok()


# ---------------------------------------------------------------------------
# Utility per prompt / diagnostica
# ---------------------------------------------------------------------------

def normalize_bash_argv(argv: Sequence[str]) -> List[str]:
    """Normalizza i path `project/...` prima dell'esecuzione.

    La cwd dei worker è già `project/`. Accettiamo sia `project/x` sia `x`
    e li eseguiamo entrambi come `x`, così il comportamento coincide con
    `write_file`/`read_file`. Non tocca i flag (tranne il valore dopo `=`).
    """
    if not argv:
        return []
    result: List[str] = []
    for index, token in enumerate(argv):
        if index == 0:
            if token.startswith(("./project/", "project/")):
                token = _strip_project_prefix(token)
                if not token.startswith(("/", ".")):
                    token = f"./{token}"
            result.append(token)
            continue

        if token.startswith(("-", "--")) and "=" in token:
            flag, value = token.split("=", 1)
            if value.startswith(("./project/", "project/")) or value in ("project", "./project"):
                token = f"{flag}={_strip_project_prefix(value)}"
        elif token in ("project", "./project", "project/", "./project/"):
            token = "."
        elif token.startswith(("./project/", "project/")):
            token = _strip_project_prefix(token)
        result.append(token)
    return result


def allowed_commands_text() -> str:
    """Testo breve, adatto al system prompt di un piccolo LLM."""
    return (
        "Comandi shell ammessi (uno alla volta, senza pipe/redirect): "
        "ls, cat, head, tail, wc, grep, find, diff, mkdir, touch, rm file, "
        "cp, mv, gcc, g++, make, python project/file.py, pytest, "
        "git status|diff|log|add|commit. "
        "Vietati: sudo, curl, wget, ssh, nc, rm -r/-f, chmod, path assoluti, '..', '~'."
    )


def is_sensitive_path(path: str | Path) -> bool:
    """True se il path contiene un componente sensibile."""
    try:
        return _has_sensitive_part(Path(path))
    except Exception:
        return True
