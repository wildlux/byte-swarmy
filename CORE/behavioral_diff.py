"""
CORE/behavioral_diff.py — A2: diff semantico (snapshot pre/post refactoring).

Idea: prima di revisionare un modulo, catturare il suo output su un set
di input noti (snapshot in state/snapshots/). Dopo la revisione,
rieseguire gli stessi input e confrontare. Se differisce → reject
automatico con diff.

Fail-open ovunque: un errore qui non blocca mai la pipeline.

API:
  snapshot(path, inputs, timeout=15) -> dict
      Esegue il programma con ogni input via stdin, cattura stdout.
      Ritorna {"inputs": [...], "outputs": [...], "created_at": ts}.

  save_snapshot(path, snap) -> None
      Salva su state/snapshots/<hash_del_path>.json.

  load_snapshot(path) -> Optional[dict]
      Carica lo snapshot se esiste.

  verify(path, snap, timeout=15) -> (ok: bool, diff: str)
      Riesegue il programma con gli stessi input; confronta gli output.
      Ritorna (True, "") se identici, (False, diff_leggibile) altrimenti.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

SNAPSHOTS_DIR = Path("state") / "snapshots"
RUNTIME_TIMEOUT_S = 15


def _snapshot_path(target: Path) -> Path:
    """Path del file snapshot per un dato modulo."""
    key = hashlib.sha1(str(target.resolve()).encode()).hexdigest()[:12]
    return SNAPSHOTS_DIR / f"{target.stem}_{key}.json"


def _run_once(target: Path, stdin_input: str, timeout: int,
              python: Optional[str] = None) -> tuple[int, str, str]:
    """Esegue il programma con stdin_input. Ritorna (rc, stdout, stderr)."""
    env = dict(__import__("os").environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    cmd = [python or sys.executable, str(target.resolve())]
    try:
        proc = subprocess.run(
            cmd, input=stdin_input, capture_output=True, text=True,
            errors="replace", timeout=timeout,
            cwd=str(target.parent), env=env)
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout dopo {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def snapshot(target: str | Path, inputs: list[str],
             timeout: int = RUNTIME_TIMEOUT_S,
             python: Optional[str] = None) -> dict:
    """Cattura il comportamento del programma su un set di input.

    `inputs`: lista di stringhe da passare via stdin (una per esecuzione).
    Stringa vuota "" = esecuzione senza input (programma con valori hard-coded).
    """
    target = Path(target)
    outputs: list[str] = []
    for inp in inputs:
        rc, stdout, stderr = _run_once(target, inp, timeout, python)
        if rc != 0 or "Traceback" in stderr:
            outputs.append(f"__ERROR__: {stderr.strip()[:200]}")
        else:
            outputs.append(stdout)
    return {
        "target": str(target),
        "inputs": list(inputs),
        "outputs": outputs,
        "created_at": time.time(),
    }


def save_snapshot(target: str | Path, snap: dict) -> None:
    """Salva lo snapshot su disco (best-effort)."""
    try:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        p = _snapshot_path(Path(target))
        p.write_text(json.dumps(snap, indent=2, ensure_ascii=False),
                     encoding="utf-8")
    except Exception:
        pass


def load_snapshot(target: str | Path) -> Optional[dict]:
    """Carica lo snapshot se esiste, altrimenti None."""
    try:
        p = _snapshot_path(Path(target))
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def verify(target: str | Path, snap: dict,
           timeout: int = RUNTIME_TIMEOUT_S,
           python: Optional[str] = None) -> tuple[bool, str]:
    """Verifica che il programma produca gli STESSI output dello snapshot.

    Ritorna (True, "") se identici, (False, diff_leggibile) altrimenti.
    Fail-open: se lo snapshot è malformato → (True, "") (non blocca).
    """
    if not snap or "inputs" not in snap or "outputs" not in snap:
        return True, ""
    target = Path(target)
    inputs = snap["inputs"]
    expected = snap["outputs"]
    diffs: list[str] = []
    for i, (inp, exp) in enumerate(zip(inputs, expected)):
        rc, stdout, stderr = _run_once(target, inp, timeout, python)
        if rc != 0 or "Traceback" in stderr:
            got = f"__ERROR__: {stderr.strip()[:200]}"
        else:
            got = stdout
        if got != exp:
            # Diff compatto: mostra le prime differenze
            exp_lines = exp.splitlines()
            got_lines = got.splitlines()
            diff_lines = []
            for j, (e, g) in enumerate(zip(exp_lines, got_lines)):
                if e != g:
                    diff_lines.append(f"  riga {j+1}: atteso '{e}' → ottenuto '{g}'")
            if len(exp_lines) != len(got_lines):
                diff_lines.append(
                    f"  numero righe: atteso {len(exp_lines)}, "
                    f"ottenuto {len(got_lines)}")
            diffs.append(
                f"input #{i+1} ({inp!r}):\n" + "\n".join(diff_lines))
    if diffs:
        return False, "COMPORTAMENTO CAMBIATO:\n" + "\n---\n".join(diffs)
    return True, ""


def check_refactor_regression(target: str | Path,
                             inputs: Optional[list[str]] = None,
                             timeout: int = RUNTIME_TIMEOUT_S) -> tuple[bool, str]:
    """A3 — Verifica regressione comportamentale dopo un refactoring.

    Crea uno snapshot se non esiste (dal codice attuale), poi verifica
    che il comportamento sia preservato. Usato nel Refactor-Loop
    (Mappatura → Analisi → Intervento → Validazione → Comportamento?).

    Ritorna (True, "") se il comportamento è preservato, (False, diff)
    se è cambiato. Fail-open: errore → (True, "").

    `inputs`: lista di input per stdin. Se None o vuota, usa [""] (una
    esecuzione senza input).
    """
    if inputs is None:
        inputs = [""]
    target = Path(target)
    if not target.exists():
        return True, ""
    try:
        snap = load_snapshot(target)
        if snap is None:
            snap = snapshot(target, inputs, timeout=timeout)
            save_snapshot(target, snap)
            return True, ""  # primo run: nessun confronto possibile
        return verify(target, snap, timeout=timeout)
    except Exception:
        return True, ""  # fail-open
