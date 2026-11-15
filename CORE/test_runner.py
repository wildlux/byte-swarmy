"""
test_runner.py — Runner di test programmabile (CLI + GUI) per byte-swarmy.

Esegue le suite di test raggruppate per categoria e restituisce risultati
strutturati in JSON. Può essere usato:
  - da CLI:     .venv/bin/python -m CORE.test_runner --categoria sicurezza
  - da GUI:     import CORE.test_runner as tr; tr.run_categoria("sicurezza")
  - da pytest:  i singoli file restano eseguibili con pytest normalmente.

Categorie disponibili (vedi TEST_CATEGORIES):
  - sicurezza      : test_security, test_security_hardcore, test_dotfile_security, test_escape_gate
  - fuzz           : tests/fuzz_security.py (fuzzing mirato sicurezza)
  - benchmark      : test_external_benchmark, test_cycle56_risk_runtime, test_cycle57_test_generation
  - sandbox        : test_sandbox
  - ciclo56        : test_cycle56_risk_runtime (risk gate + runtime verifier)
  - ciclo57        : test_cycle57_test_generation (test generation)
  - diary          : test_diary_llm_tool (tool diario di bordo)
  - scheduler      : test_scheduler, test_task_scheduler_project_path, test_task_atomizer
  - tutti          : tutti i test top-level (escluso e2e/LLM di default)
  - e2e            : solo test e2e/LLM (richiedono Ollama)

I risultati vengono salvati in state/test_runner/results_<categoria>.json
e restituiti come dict per l'integrazione GUI.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / "state" / "test_runner"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Timeout per categoria (secondi).
DEFAULT_TIMEOUT_S = 120
E2E_TIMEOUT_S = 600

# Ogni categoria: lista di file test (senza percorso, solo nome).
TEST_CATEGORIES: dict[str, list[str]] = {
    "sicurezza": [
        "test_security.py",
        "test_security_hardcore.py",
        "test_dotfile_security.py",
        "test_escape_gate.py",
    ],
    "fuzz": ["fuzz_security.py"],
    "benchmark": [
        "test_external_benchmark.py",
        "test_cycle56_risk_runtime.py",
        "test_cycle57_test_generation.py",
    ],
    "sandbox": ["test_sandbox.py"],
    "ciclo56": ["test_cycle56_risk_runtime.py"],
    "ciclo57": ["test_cycle57_test_generation.py"],
    "diary": ["test_diary_llm_tool.py"],
    "scheduler": [
        "test_scheduler.py",
        "test_task_scheduler_project_path.py",
        "test_task_atomizer.py",
    ],
    "tutti": [],  # riempito sotto: tutti i test_*.py top-level
    "e2e": [
        "test_e2e.py",
        "test_mcp_e2e.py",
        "test_timestral_e2e.py",
        "test_timestral_full.py",
        "test_functional_swarm.py",
    ],
}

# Riempi "tutti" con tutti i test_*.py top-level (esclusi archiviati/legacy).
_TESTS_DIR = ROOT / "tests"
_ALL_FILES = sorted(
    p.name for p in _TESTS_DIR.glob("test_*.py")
    if p.is_file()
)
# Escludi file che non sono test standard o che richiedono setup speciale.
_TESTS_DIR / "run_tests.py"  # esiste ma non è un test standard
TEST_CATEGORIES["tutti"] = [
    f for f in _ALL_FILES
    if not f.startswith("TEST_")
    and f not in ("run_tests.py",)
]


def _pytest_args(file_path: Path, timeout_s: int) -> list[str]:
    return [
        sys.executable, "-m", "pytest", "-q", "--no-header",
        "-p", "no:cacheprovider", "--tb=short",
        str(file_path),
    ]


_PX_PASSED = re.compile(r"(\d+) passed")
_PX_FAILED = re.compile(r"(\d+) failed")
_PX_ERROR = re.compile(r"(\d+) error")
_PX_SKIPPED = re.compile(r"(\d+) skipped")


def _parse_pytest_output(text: str, exit_code: int) -> dict:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for pat, key in (
        (_PX_PASSED, "passed"), (_PX_FAILED, "failed"),
        (_PX_ERROR, "errors"), (_PX_SKIPPED, "skipped"),
    ):
        m = pat.search(text)
        if m:
            counts[key] = int(m.group(1))
    if exit_code == 0:
        status = "PASS"
    elif exit_code == 5:  # pytest: nessun test raccolto
        status = "SKIP"
    else:
        status = "FAIL"
    return {"status": status, "counts": counts}


def run_single_file(file_path: Path, timeout_s: int = DEFAULT_TIMEOUT_S) -> dict:
    """Esegue UN file di test con pytest in subprocess.

    Ritorna un dict con chiavi: file, status, counts, duration_s, detail.
    Non solleva eccezioni: tutto viene catturato nel dict.
    """
    name = file_path.name
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            _pytest_args(file_path, timeout_s),
            cwd=str(ROOT),
            capture_output=True, text=True, timeout=timeout_s,
        )
        dur = round(time.monotonic() - t0, 1)
        out = proc.stdout + "\n" + proc.stderr
        parsed = _parse_pytest_output(out, proc.returncode)
        return {
            "file": name,
            "status": parsed["status"],
            "counts": parsed["counts"],
            "duration_s": dur,
            "detail": out[-4000:] if out else "(nessun output)",
        }
    except subprocess.TimeoutExpired:
        dur = round(time.monotonic() - t0, 1)
        return {
            "file": name,
            "status": "ERROR",
            "counts": {"passed": 0, "failed": 0, "errors": 0, "skipped": 0},
            "duration_s": dur,
            "detail": f"[TIMEOUT] processo terminato dopo {timeout_s}s.",
        }
    except Exception as exc:  # noqa: BLE001
        dur = round(time.monotonic() - t0, 1)
        return {
            "file": name,
            "status": "ERROR",
            "counts": {"passed": 0, "failed": 0, "errors": 0, "skipped": 0},
            "duration_s": dur,
            "detail": f"[CRASH] {type(exc).__name__}: {exc}",
        }


def run_categoria(categoria: str,
                  timeout_s: Optional[int] = None) -> dict:
    """Esegue tutti i file di una categoria.

    Args:
        categoria: chiave di TEST_CATEGORIES (es. "sicurezza", "fuzz", "tutti").
        timeout_s: timeout per file (secondi). None = default della categoria.

    Ritorna un dict con timestamp, categoria, summary e lista file.
    Salva il JSON in state/test_runner/results_<categoria>.json.
    """
    if categoria not in TEST_CATEGORIES:
        raise ValueError(
            f"Categoria sconosciuta: {categoria}. "
            f"Disponibili: {sorted(TEST_CATEGORIES)}"
        )

    files = TEST_CATEGORIES[categoria]
    if not files and categoria != "tutti":
        # categoria vuota: nessun file da eseguire
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "categoria": categoria,
            "timeout_s": timeout_s or DEFAULT_TIMEOUT_S,
            "summary": {
                "files_total": 0, "files_ok": 0, "files_ko": 0,
                "files_skipped": 0,
                "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
                "duration_s": 0.0,
            },
            "files": [],
        }
        _save_report(categoria, report)
        return report

    if categoria == "tutti":
        # per "tutti" risolviamo la lista dinamicamente (include fuzz, ecc.)
        files = TEST_CATEGORIES["tutti"]

    timeout = timeout_s or DEFAULT_TIMEOUT_S
    results: list[dict] = []
    tot = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    dur = 0.0

    for fname in files:
        fpath = _TESTS_DIR / fname
        if not fpath.exists():
            results.append({
                "file": fname,
                "status": "ERROR",
                "counts": {"passed": 0, "failed": 0, "errors": 0, "skipped": 0},
                "duration_s": 0.0,
                "detail": f"[NOT FOUND] file {fname} non presente in tests/.",
            })
            continue
        r = run_single_file(fpath, timeout)
        results.append(r)
        for k in tot:
            tot[k] += r["counts"].get(k, 0)
        dur += r["duration_s"]

    files_ok = sum(1 for r in results if r["status"] == "PASS")
    files_ko = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    files_skipped = sum(1 for r in results if r["status"] == "SKIP")

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "categoria": categoria,
        "timeout_s": timeout,
        "summary": {
            "files_total": len(results), "files_ok": files_ok,
            "files_ko": files_ko, "files_skipped": files_skipped,
            "passed": tot["passed"], "failed": tot["failed"],
            "errors": tot["errors"], "skipped": tot["skipped"],
            "duration_s": round(dur, 1),
        },
        "files": results,
    }
    _save_report(categoria, report)
    return report


def _save_report(categoria: str, report: dict) -> None:
    """Salva il report JSON in state/test_runner/."""
    safe_name = re.sub(r"[^a-z0-9]+", "_", categoria.lower())
    path = RESULTS_DIR / f"results_{safe_name}.json"
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_report(categoria: str) -> Optional[dict]:
    """Carica l'ultimo report salvato per una categoria."""
    safe_name = re.sub(r"[^a-z0-9]+", "_", categoria.lower())
    path = RESULTS_DIR / f"results_{safe_name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_categorie() -> list[str]:
    """Ritorna le categorie disponibili in ordine stabile."""
    return ["sicurezza", "fuzz", "benchmark", "sandbox", "ciclo56",
            "ciclo57", "diary", "scheduler", "tutti", "e2e"]


# ═════════════════════════════════════════════════════════════════════
# Entry point CLI
# ═════════════════════════════════════════════════════════════════════

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Runner di test byte-swarmy (eseguibile anche da GUI)"
    )
    parser.add_argument(
        "--categoria", "-c", default="tutti",
        help="Categoria di test da eseguire (default: tutti). "
             f"Disponibili: {', '.join(list_categorie())}.",
    )
    parser.add_argument(
        "--timeout", "-t", type=int, default=None,
        help="Timeout per file in secondi (default: 120).",
    )
    parser.add_argument(
        "--lista", action="store_true",
        help="Elenca le categorie disponibili ed esce.",
    )
    args = parser.parse_args()

    if args.lista:
        print("Categorie disponibili:")
        for cat in list_categorie():
            files = TEST_CATEGORIES.get(cat, [])
            print(f"  - {cat}: {len(files)} file")
        return 0

    try:
        report = run_categoria(args.categoria, args.timeout)
    except ValueError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 2

    s = report["summary"]
    print(f"\n=== Test runner — categoria: {report['categoria']} ===")
    print(f"File totali:  {s['files_total']}")
    print(f"File OK:      {s['files_ok']}")
    print(f"File KO:      {s['files_ko']}")
    print(f"Test pass:    {s['passed']}")
    print(f"Test fail:    {s['failed']}")
    print(f"Test error:   {s['errors']}")
    print(f"Test skip:    {s['skipped']}")
    print(f"Durata:       {s['duration_s']}s")
    print(f"Report JSON:  state/test_runner/results_{args.categoria}.json\n")

    # Codice uscita: 0 se tutto OK, 1 se ci sono fallimenti.
    return 0 if s["files_ko"] == 0 and s["files_total"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
