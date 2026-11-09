"""
path_utils.py — Utilità e validazione dei path (centrale).

Motivazione: oggi il controllo path è frammentato tra
``SAFETY/security.py`` (``safe_project_path``, ``is_sensitive_path``) e
controlli sparsi in ``CORE/tools.py``. Questo modulo centralizza:

1. Ri-esporta le funzioni di sicurezza esistenti (per non rompere import).
2. Aggiunge funzioni pure (nessuna eccezione di sicurezza, solo booleani /
   stringhe pulite) per validare e costruire path in modo sicuro.

Tutte le funzioni qui sono "passive": non bloccano l'esecuzione, solo
restituiscono informazioni o stringhe sanificate. Il blocco effettivo
resta a ``safe_project_path`` (security).
"""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional, Sequence

from SAFETY.security import (  # noqa: F401 — ri-esportate per comodità
    is_sensitive_path,
    safe_project_path,
)

# Caratteri mai ammessi in un nome di file/cartella (cross-platform)
_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|\?\x00-\x1f\x7f]')
# Riservati Windows (anche con estensione, es. NUL.txt)
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}
_MAX_COMPONENT_LEN = 255
_TRAVERSAL_RE = re.compile(r"(^|/|\\)\.\.(/|\\|$)|^\.\.$")


def is_relative_safe(path: str | Path) -> bool:
    """True se il path è relativo, non assoluto, senza `~`, senza `..`."""
    try:
        text = os.fspath(path)
    except TypeError:
        return False
    if not text or text.strip() != text:
        return False
    if "\x00" in text:
        return False
    if text.startswith("~"):
        return False
    try:
        p = Path(text)
    except (ValueError, TypeError):
        return False
    if p.is_absolute():
        return False
    parts = PurePosixPath(text.replace("\\", "/")).parts
    return ".." not in parts and "." not in parts[1:-1] if len(parts) > 1 else ".." not in parts


def has_traversal(path: str | Path) -> bool:
    """True se il path contiene componenti `..` (directory traversal)."""
    try:
        text = os.fspath(path)
    except TypeError:
        return True
    return bool(_TRAVERSAL_RE.search(text.replace("\\", "/")))


def sanitize_filename(name: str, maxlen: int = _MAX_COMPONENT_LEN,
                      fallback: str = "file") -> str:
    """Rende un nome file sicuro: rimuove caratteri proibiti, spazi finali,
    nomi riservati Windows e tronca a ``maxlen``. Mai restituisce stringa
    vuota (usa ``fallback``).

    Non tocca l'estensione: se l'input finisce con punto/spazio, li rimuove
    (Windows non li ammette in fondo al nome).
    """
    if not name:
        return fallback
    # Togli percorso eventuale (tieni solo l'ultimo componente)
    base = os.path.basename(str(name).replace("\\", "/"))
    base = _FORBIDDEN_CHARS.sub("_", base).strip(" .")
    # Nomi riservati Windows (anche con estensione, es. CON.txt, NUL.log)
    stem, ext = os.path.splitext(base)
    if stem.upper() in _RESERVED_NAMES:
        base = f"{stem}__{ext}"
    if not base or base in _RESERVED_NAMES or base.upper() in _RESERVED_NAMES:
        base = fallback
    if len(base) > maxlen:
        stem, ext = os.path.splitext(base)
        keep = maxlen - len(ext)
        base = (stem[:keep] if keep > 0 else fallback) + ext[: max(0, maxlen - len(fallback))]
    return base or fallback


def join_safe(base: str | Path, *parts: str | Path) -> Path:
    """Unisce ``base`` con i ``parts`` restituendo un Path normalizzato.

    Solleva ValueError se qualche parte contiene traversal `..` o è assoluta.
    Non risolve symlink né controlla l'esistenza sul disco.
    """
    result = Path(base)
    for part in parts:
        part_str = os.fspath(part)
        if has_traversal(part_str):
            raise ValueError(f"traversal in path part: {part_str!r}")
        p = Path(part_str)
        if p.is_absolute():
            raise ValueError(f"absolute path part not allowed: {part_str!r}")
        result = result / part_str
    return result.resolve(strict=False)


def normalize_separators(path: str | Path) -> str:
    """Ritorna il path con separatori ``/`` (utile per confronti cross-platform)."""
    return str(Path(path).as_posix()).replace("\\", "/")


def path_depth(path: str | Path) -> int:
    """Numero di componenti del path (es. ``a/b/c`` → 3)."""
    return len(PurePosixPath(str(path).replace("\\", "/")).parts)


def is_within_project(path: str | Path, project_root: str | Path) -> bool:
    """True se il path risolto è dentro ``project_root`` (senza sollevare
    eccezioni; restituisce False in caso di errore)."""
    try:
        return safe_project_path(path, project_root) is not None
    except Exception:
        return False


def split_safe(path: str | Path) -> list:
    """Divide il path in componenti (senza sollevare eccezioni per path strani)."""
    try:
        return [p for p in PurePosixPath(str(path).replace("\\", "/")).parts if p not in (".", "")]
    except Exception:
        return [str(path)]


__all__ = [
    "safe_project_path",      # ri-esportato da SAFETY.security
    "is_sensitive_path",      # ri-esportato da SAFETY.security
    "is_relative_safe",
    "has_traversal",
    "sanitize_filename",
    "join_safe",
    "normalize_separators",
    "path_depth",
    "is_within_project",
    "split_safe",
]
