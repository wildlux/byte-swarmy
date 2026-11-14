#!/usr/bin/env python3
"""Verifica completa del progetto in autonomia (un solo comando).

Esegue in sequenza i controlli che storicamente beccano le regressioni
silent (variabili mai definite, metodi cancellati) che py_compile e i
test con mock NON vedono:

1. compile    — py_compile di tutti i .py (CORE, GUI, tools, tests)
2. tests      — suite pytest completa (tests/)
3. boot       — avvio reale dell'orchestratore con state/pause.flag
                (grace period; verifica shutdown pulito e no traceback)
4. bench      — benchmark worker ReAct con Ollama reale e confronto con
                la baseline (tools/bench_worker.py). Auto-SKIP se Ollama
                non è raggiungibile. Disabilitabile con --no-bench.

Usage:
    .venv/bin/python tools/verify_all.py             # tutto (bench se Ollama up)
    .venv/bin/python tools/verify_all.py --no-bench  # solo compile+tests+boot
Exit code: 0 se tutto ok (bench skip non fa fallire), 1 altrimenti.
"""

import argparse
import py_compile
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = str(ROOT / ".venv" / "bin" / "python")
PAUSE_FLAG = ROOT / "state" / "pause.flag"

# Test LIVE: toccano la coda/orchestratore REALI dell'utente
# (tasks/queue.db) e aspettano processing veri fino a 120-180s per task.
# Vanno eseguiti solo deliberatamente col sistema attivo, MAI in una
# verifica autonoma: qui li escludiamo sempre.
LIVE_TESTS = ("test_e2e.py", "test_functional_swarm.py")

STAGES: list = []  # (nome, stato, dettaglio)


def record(name: str, ok: bool, detail: str = "") -> None:
    """Registra l'esito di uno stage per il riepilogo finale."""
    STAGES.append((name, ok, detail))


def stage_compile() -> bool:
    """Stage 1: compila tutti i sorgenti Python del progetto."""
    bad = []
    n = 0
    for sub in ("CORE", "GUI", "tools", "tests"):
        for p in sorted((ROOT / sub).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            n += 1
            try:
                py_compile.compile(str(p), doraise=True)
            except Exception as e:
                bad.append(f"{p.relative_to(ROOT)}: {e}")
    if bad:
        print("\n".join(bad))
    record("compile", not bad, f"{n} file, {len(bad)} errori")
    return not bad


def stage_tests(file_timeout: int, single_run: bool, total_timeout: int) -> bool:
    """Stage 2: suite pytest — per-file (default) o single-run.

    Per-file: un processo pytest per file con timeout individuale. Un file
    lento/hanging non blocca gli altri e la mappa finale dice ESATTAMENTE
    quale file è lento o rotto (i test GUI/Qt sono lenti ma leciti).
    Single-run: un solo processo pytest — più fedele all'ordinamento
    reale (pollution tra file), ma senza per-file timeout.
    In entrambi i modi i test LIVE sono esclusi.
    """
    all_files = sorted((ROOT / "tests").glob("test_*.py"))
    files = [f for f in all_files if f.name not in LIVE_TESTS]
    skipped_live = [f.name for f in all_files if f.name in LIVE_TESTS]
    ignore_args = [f"--ignore=tests/{n}" for n in LIVE_TESTS]

    def parse_last(out: str) -> str:
        lines = [ln for ln in (out or "").strip().splitlines() if ln.strip()]
        return lines[-1] if lines else ""

    if single_run:
        try:
            r = subprocess.run(
                [VENV_PY, "-m", "pytest", "tests", "-q", "--tb=line",
                 "-p", "no:cacheprovider"] + ignore_args,
                cwd=ROOT, capture_output=True, text=True,
                timeout=total_timeout)
            summary = parse_last(r.stdout)
            ok = r.returncode == 0
            if not ok:
                fails = [ln for ln in r.stdout.splitlines()
                         if ln.startswith("FAILED")][:10]
                summary += "\n" + "\n".join(fails)
        except subprocess.TimeoutExpired:
            ok, summary = False, f"timeout dopo {total_timeout}s"
        detail = f"{summary}\n(esclusi live: {', '.join(skipped_live)})"
        record("tests", ok, detail)
        return ok

    # --- modalità per-file ---
    results = []  # (nome, stato, secondi, ultima riga)
    for f in files:
        t0 = time.perf_counter()
        try:
            r = subprocess.run(
                [VENV_PY, "-m", "pytest", str(f.relative_to(ROOT)), "-q",
                 "--tb=line", "-p", "no:cacheprovider"],
                cwd=ROOT, capture_output=True, text=True,
                timeout=file_timeout)
            state = "OK" if r.returncode == 0 else "FAIL"
            info = parse_last(r.stdout)
        except subprocess.TimeoutExpired:
            state, info = "TIMEOUT", f"> {file_timeout}s"
        results.append((f.name, state, time.perf_counter() - t0, info))

    bad = [(n, s, i) for (n, s, _, i) in results if s != "OK"]
    n_ok = sum(1 for (_, s, _, _) in results if s == "OK")
    detail_lines = [f"{len(files)} file: {n_ok} ok, "
                    f"{sum(1 for x in results if x[1]=='FAIL')} fail, "
                    f"{sum(1 for x in results if x[1]=='TIMEOUT')} timeout",
                    f"esclusi live: {', '.join(skipped_live)}"]
    for n, s, i in bad:
        detail_lines.append(f"  {s}: {n} — {i[:120]}")
    record("tests", not bad, "\n".join(detail_lines))
    return not bad


def stage_boot(boot_timeout: int) -> bool:
    """Stage 3: boot reale dell'orchestratore con pausa (grace period).

    Il comando `timeout` manda SIGTERM: l'orchestratore spegne lo swarm
    con grazia → exit atteso 124 con 'swarm stopped' nel log e nessun
    traceback.
    """
    PAUSE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    try:
        PAUSE_FLAG.touch()
        r = subprocess.run(
            ["timeout", str(boot_timeout), VENV_PY, "-m", "CORE.orchestrator",
             "CONFIG/config.toml"],
            cwd=ROOT, capture_output=True, text=True, timeout=boot_timeout + 30)
        out = (r.stdout or "") + (r.stderr or "")
        stopped = "swarm stopped" in out
        tb = "Traceback (most recent call last)" in out
        ok = r.returncode in (0, 124) and stopped and not tb
        detail = (f"exit={r.returncode} stopped={'sì' if stopped else 'NO'}"
                  + (" TRACEBACK!" if tb else ""))
        if not ok:
            detail += "\n" + "\n".join(out.strip().splitlines()[-12:])
    except subprocess.TimeoutExpired:
        ok, detail = False, f"hard-timeout dopo {boot_timeout + 30}s"
    finally:
        PAUSE_FLAG.unlink(missing_ok=True)
    record("boot", ok, detail)
    return ok


def stage_bench(task_timeout: int) -> bool:
    """Stage 4: benchmark worker con Ollama reale (auto-skip se offline)."""
    try:
        from tools.bench_worker import ollama_reachable
        from CORE.orchestrator import load_config
        cfg = load_config(str(ROOT / "CONFIG" / "config.toml"))
        if not ollama_reachable(cfg["ollama"]["host"]):
            record("bench", True, "SKIP — Ollama non raggiungibile")
            return True
    except Exception as e:
        record("bench", True, f"SKIP — check fallito: {e}")
        return True
    print()
    try:
        r = subprocess.run(
            [VENV_PY, "tools/bench_worker.py",
             "--task-timeout", str(task_timeout)],
            cwd=ROOT, timeout=task_timeout * 2 + 300)
        ok = r.returncode == 0
        detail = f"exit={r.returncode}"
    except subprocess.TimeoutExpired:
        ok, detail = False, "hard-timeout bench"
    record("bench", ok, detail)
    return ok


def main() -> None:
    """Entry point CLI della verifica completa."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-bench", action="store_true",
                    help="salta il benchmark con Ollama")
    ap.add_argument("--single-run", action="store_true",
                    help="un solo processo pytest (niente timeout per file)")
    ap.add_argument("--file-timeout", type=int, default=240,
                    help="timeout per singolo file di test (default 240s)")
    ap.add_argument("--tests-timeout", type=int, default=2700,
                    help="timeout totale in single-run (default 2700s)")
    ap.add_argument("--boot-timeout", type=int, default=15,
                    help="grace period boot (default 15s, come da convenzione)")
    ap.add_argument("--task-timeout", type=int, default=600)
    args = ap.parse_args()

    print(f"=== verify_all — {datetime.now().isoformat(timespec='seconds')} ===")
    t0 = time.perf_counter()
    ok = True
    ok &= stage_compile()
    ok &= stage_tests(args.file_timeout, args.single_run, args.tests_timeout)
    ok &= stage_boot(args.boot_timeout)
    if not args.no_bench:
        ok &= stage_bench(args.task_timeout)

    print("\n=== RIEPILOGO ===")
    for name, good, detail in STAGES:
        icon = "✅" if good else "❌"
        first = detail.splitlines()[0] if detail else ""
        print(f"{icon} {name:<8} {first}")
        for ln in detail.splitlines()[1:]:
            print(f"           {ln}")
    print(f"\ntotale: {time.perf_counter() - t0:.0f}s — "
          f"{'TUTTO OK' if ok else 'FALLIMENTI PRESENTI'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
