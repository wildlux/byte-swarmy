"""test_hardening_paths.py — lock offline della radice usata da hardening.sh.

Dopo il riordino delle cartelle, `hardening.sh` risiede in `scripts/setup/`:
`--apply` deve copiare la radice del repo, non la cartella dello script.
I test leggono lo script ed eseguono solo `--check` (diagnostica read-only,
senza root): nessuna modifica a utenti, slice, firewall o filesystem.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "setup" / "hardening.sh"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _check_output() -> str:
    cp = subprocess.run(["bash", str(SCRIPT), "--check"], cwd=ROOT,
                        capture_output=True, text=True, check=True)
    return ANSI.sub("", cp.stdout + cp.stderr)


def test_check_riporta_la_radice_del_repo():
    lines = [line.strip() for line in _check_output().splitlines()
             if "Progetto:" in line]
    assert len(lines) == 1
    assert lines[0].split("Progetto:", 1)[1].strip() == str(ROOT)


def test_rsync_copia_la_radice_non_la_cartella_script():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"' in text
    assert '"$PROJECT_DIR"/ "$TARGET_DIR"/' in text
    assert 'rsync -a --delete' in text


def test_rsync_esclude_lo_stato_runtime_con_credenziali():
    """`state/` è un symlink: la rsync deve escludere anche la destinazione.

    Altrimenti `data/state/cloud_api.json` verrebbe copiato nell'utente
    isolato insieme al resto dello stato runtime.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--exclude 'state/'" in text
    assert "--exclude 'data/state/'" in text


def test_script_setup_sintatticamente_validi():
    for script in sorted((ROOT / "scripts" / "setup").glob("*.sh")):
        cp = subprocess.run(["bash", "-n", str(script)], cwd=ROOT,
                            capture_output=True, text=True)
        assert cp.returncode == 0, f"{script.name}: {cp.stderr}"
