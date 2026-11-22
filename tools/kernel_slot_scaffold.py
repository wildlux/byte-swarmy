#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scaffold deterministico a SLOT per driver platform Linux (todokernel SLOT).

Il planner genera scheletro C, Makefile e mappa degli slot; il modello 3b
riempie SOLO i blocchi `SLOT_*`. Nessuna API viene inventata: Prima della
scrittura ogni simbolo chiamato è verificato contro la whitelist estratta dagli
header del kernel target; le macro indispensabili sono verificate cercando il
`#define` negli header reali. Se la verifica non è possibile, il tool si ferma.

Uso:
    .venv/bin/python tools/kernel_slot_scaffold.py --name demo --out project/driver_demo
    .venv/bin/python tools/kernel_slot_scaffold.py --check project/driver_demo/demo.c
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.kernel_api_whitelist import check_source  # noqa: E402

TEMPLATES = ROOT / "GUI" / "refs" / "templates"
C_TEMPLATE = TEMPLATES / "kernel_platform.c.tpl"
MK_TEMPLATE = TEMPLATES / "kernel_makefile.tpl"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

# Macro necessarie allo scheletro: non sono prototipi, quindi la whitelist
# (che estrae firme di funzione) non le contiene. Verifichiamo il #define
# direttamente negli header della versione target.
MACRO_HEADERS = {
    "module_init": "include/linux/module.h",
    "module_exit": "include/linux/module.h",
    "MODULE_LICENSE": "include/linux/module.h",
}

SLOTS = (
    ("SLOT_READ", "read: copia dati verso l'utente",
     "copy_to_user", "restituire il numero di byte copiati o -EFAULT"),
    ("SLOT_WRITE", "write: copia dati dall'utente",
     "copy_from_user", "restituire il numero di byte copiati o -EFAULT"),
    ("SLOT_IOCTL", "ioctl: solo comandi semplici",
     "(nessuna API obbligatoria)", "comando non supportato → -ENOTTY"),
)


def validate_name(name: str) -> str:
    if not NAME_RE.match(name or ""):
        raise ValueError(
            "nome non valido: servono [a-z][a-z0-9_]{0,31} "
            "(nessun trattino, spazio o percorso)")
    return name


def header_root(version: str) -> Path:
    return Path("/lib/modules") / version / "build"


def macro_defined(symbol: str, version: str) -> bool:
    rel = MACRO_HEADERS.get(symbol)
    if not rel:
        return False
    path = header_root(version) / rel
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return re.search(r"^\s*#\s*define\s+" + re.escape(symbol) + r"\b",
                     text, re.MULTILINE) is not None


def verified_macros(version: str) -> set[str]:
    """Macro ammesse solo se il #define esiste negli header target."""
    return {sym for sym in MACRO_HEADERS if macro_defined(sym, version)}


def local_symbols(name: str) -> set[str]:
    """Funzioni definite nello scheletro: non sono API kernel."""
    stem = validate_name(name)
    return {
        f"{stem}_read", f"{stem}_write", f"{stem}_ioctl",
        f"{stem}_probe", f"{stem}_remove", f"{stem}_init", f"{stem}_exit",
    }


def check_api(source: str, name: str, version: str | None = None) -> list[str]:
    """Simboli sconosciuti: lista vuota = scaffold sicuro."""
    version = version or os.uname().release
    macros = verified_macros(version)
    missing = sorted(set(MACRO_HEADERS) - macros)
    if missing:
        raise RuntimeError(
            "header kernel non disponibili per verificare: " + ", ".join(missing)
            + f" (versione {version}) — generazione bloccata")
    return check_source(source, version,
                        known=local_symbols(name) | macros)


def slots_markdown(name: str) -> str:
    lines = [
        f"# SLOT driver `{name}`",
        "",
        "> Scheletro generato: probe/remove/file_operations/Makefile sono",
        "> deterministici. Il modello riempie SOLO i blocchi qui sotto.",
        "",
        "| SLOT | Contenuto | API da verificare | Criterio |",
        "|---|---|---|---|",
    ]
    for key, desc, api, criterion in SLOTS:
        lines.append(f"| `{key}` | {desc} | `{api}` | {criterion} |")
    lines += [
        "",
        "## Regole",
        "",
        "- Un solo slot per turno, max 40 righe per slot.",
        "- Ogni simbolo kernel usato deve passare `CORE/kernel_api_whitelist`.",
        "- Dopo ogni slot: `make`, `checkpatch.pl` e `sparse` prima del successivo.",
        "- Nessun `insmod` senza gate statici verdi.",
        "",
    ]
    return "\n".join(lines)


def generate(name: str, out: Path, version: str | None = None) -> dict:
    """Genera lo scaffold solo se tutte le API sono verificate."""
    name = validate_name(name)
    version = version or os.uname().release
    source = C_TEMPLATE.read_text(encoding="utf-8").format(name=name)
    makefile = MK_TEMPLATE.read_text(encoding="utf-8").format(name=name)
    unknown = check_api(source, name, version)
    if unknown:
        raise ValueError("API non verificate nello scheletro: " + ", ".join(unknown))
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "source": out / f"{name}.c",
        "makefile": out / "Makefile",
        "slots": out / "SLOTS.md",
    }
    files["source"].write_text(source, encoding="utf-8")
    files["makefile"].write_text(makefile, encoding="utf-8")
    files["slots"].write_text(slots_markdown(name), encoding="utf-8")
    return {
        "name": name,
        "version": version,
        "files": {k: str(v) for k, v in files.items()},
        "unknown_api": unknown,
        "slots": [s[0] for s in SLOTS],
        "compilato": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold SLOT driver kernel")
    parser.add_argument("--name", help="nome modulo: [a-z][a-z0-9_]{0,31}")
    parser.add_argument("--out", type=Path, help="cartella di output")
    parser.add_argument("--check", type=Path, help="verifica API di un .c riempito")
    parser.add_argument("--version", default=None, help="versione kernel target")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args(argv)

    if args.check:
        source = args.check.read_text(encoding="utf-8")
        try:
            unknown = check_api(source, args.check.stem, args.version)
        except (RuntimeError, ValueError) as exc:
            print(f"BLOCCATO: {exc}")
            return 1
        if unknown:
            print("API NON VERIFICATE: " + ", ".join(unknown))
            return 1
        print("OK: nessuna API allucinata")
        return 0

    if not args.name or not args.out:
        parser.error("--name e --out sono obbligatori (oppure --check FILE)")
    try:
        result = generate(args.name, args.out, args.version)
    except (RuntimeError, ValueError) as exc:
        print(f"BLOCCATO: {exc}")
        return 1
    if args.json:
        print(__import__("json").dumps(result, indent=2, ensure_ascii=False))
    else:
        for label, path in result["files"].items():
            print(f"{label}: {path}")
        print(f"API verificate: {len(result['unknown_api'])} sconosciute")
    return 0


if __name__ == "__main__":
    sys.exit(main())
