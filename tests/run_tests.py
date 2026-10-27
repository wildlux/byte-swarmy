#!/usr/bin/env python3
"""
tests/run_tests.py — runner unico con output JSON per la GUI.

Esegue:
  1. la suite unitaria `tests/` (unittest, senza root);
  2. il self-test del sandbox eseguito *dentro* bubblewrap.

Uso:
    python tests/run_tests.py            # riepilogo leggibile
    python tests/run_tests.py --json     # JSON su stdout (per la GUI)
    python tests/run_tests.py --json --no-sandbox

Exit code: 0 se tutti i test passano e il sandbox è operativo, 1 altrimenti.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sandbox  # noqa: E402


class RecordingResult(unittest.TextTestResult):
    """TextTestResult che registra esito e durata di ogni singolo test."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records: list[dict] = []
        self._started: dict[str, float] = {}

    def startTest(self, test):
        self._started[test.id()] = time.monotonic()
        super().startTest(test)

    def _elapsed(self, test) -> float:
        start = self._started.pop(test.id(), None)
        return round(time.monotonic() - start, 3) if start else 0.0

    def _add(self, test, status: str, detail: str = "") -> None:
        self.records.append({
            "name": test.id(),
            "status": status,
            "duration_s": self._elapsed(test),
            "detail": (detail or "").strip()[:800],
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._add(test, "PASS")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._add(test, "SKIP", reason)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._add(test, "FAIL", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._add(test, "ERROR", self._exc_info_to_string(err, test))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._add(test, "PASS", "expected failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._add(test, "FAIL", "unexpected success")


def run_unit_tests(verbosity: int = 1) -> list[dict]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    stream = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=verbosity,
        resultclass=RecordingResult,
    )
    result = runner.run(suite)
    # unittest può segnalare errori di setup senza record: non perdere nulla.
    recorded = {r["name"] for r in result.records}
    for test, err in list(result.errors) + list(result.failures):
        if test.id() not in recorded:
            result.records.append({
                "name": test.id(),
                "status": "ERROR",
                "duration_s": 0.0,
                "detail": str(err)[:800],
            })
    return result.records


def sandbox_records(timeout: int = 60) -> tuple[list[dict], dict]:
    info = sandbox.backend_info()
    result = sandbox.run_selftest(ROOT / "project", timeout=timeout)
    records: list[dict] = []
    checks = result.get("checks") or []
    for check in checks:
        records.append({
            "name": check.get("name", "sandbox.unknown"),
            "status": check.get("status", "FAIL"),
            "duration_s": 0.0,
            "detail": str(check.get("detail", ""))[:800],
        })
    if not checks:
        detail = result.get("error") or info.get("error") or "nessun check eseguito"
        records.append({
            "name": "sandbox.selftest",
            "status": "FAIL" if not info.get("available") else "ERROR",
            "duration_s": 0.0,
            "detail": str(detail)[:800],
        })
    return records, info


def build_report(include_sandbox: bool, verbosity: int = 1) -> dict:
    started = time.monotonic()
    tests = run_unit_tests(verbosity=verbosity)
    info = sandbox.backend_info()
    if include_sandbox:
        s_records, info = sandbox_records()
        tests.extend(s_records)
    elif not info.get("available"):
        tests.append({
            "name": "sandbox.selftest",
            "status": "SKIP",
            "duration_s": 0.0,
            "detail": "self-test disattivato (--no-sandbox)",
        })

    passed = sum(1 for t in tests if t["status"] == "PASS")
    failed = sum(1 for t in tests if t["status"] == "FAIL")
    errors = sum(1 for t in tests if t["status"] == "ERROR")
    skipped = sum(1 for t in tests if t["status"] == "SKIP")
    sandbox_ok = (bool(info.get("available")) and bool(info.get("hardened"))) \
        if include_sandbox else True

    report = {
        "ok": failed == 0 and errors == 0 and sandbox_ok,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "sandbox": {
            "available": bool(info.get("available")),
            "hardened": bool(info.get("hardened")),
            "complete": sandbox_ok,
            "backend": info.get("backend", "bubblewrap"),
            "bwrap": info.get("bwrap", ""),
            "version": info.get("version"),
            "error": info.get("error", ""),
            "selftest": include_sandbox,
        },
        "summary": {
            "total": len(tests),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "duration_s": round(time.monotonic() - started, 2),
        },
        "tests": tests,
    }
    return report


def print_human(report: dict) -> None:
    s = report["sandbox"]
    print("BYTE-SWARMY · Test & Sandbox")
    print("=" * 62)
    if s["available"] and s["hardened"]:
        print(f"Sandbox: {s['backend']} {s['version'] or ''} · OK (completo)")
    elif s["available"]:
        print("Sandbox: MODALITÀ RIDOTTA — bubblewrap non supporta "
              "--disable-userns (serve >= 0.11)")
    else:
        print(f"Sandbox: NON DISPONIBILE — {s['error']}")
    print("=" * 62)
    for test in report["tests"]:
        print(f"[{test['status']:<5}] {test['name']}")
        if test["status"] in ("FAIL", "ERROR") and test["detail"]:
            for line in test["detail"].splitlines()[-4:]:
                print(f"        {line}")
    summary = report["summary"]
    print("-" * 62)
    print(
        f"Totale: {summary['total']}  "
        f"PASS: {summary['passed']}  "
        f"FAIL: {summary['failed']}  "
        f"ERROR: {summary['errors']}  "
        f"SKIP: {summary['skipped']}  "
        f"({summary['duration_s']}s)"
    )
    print("RISULTATO:", "TUTTO OK" if report["ok"] else "NON COMPLETATO")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test runner BYTE-SWARMY")
    parser.add_argument("--json", action="store_true",
                        help="stampa solo JSON (per la GUI)")
    parser.add_argument("--no-sandbox", action="store_true",
                        help="salta il self-test del sandbox")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="verbosità unittest")
    args = parser.parse_args(argv)

    try:
        report = build_report(
            include_sandbox=not args.no_sandbox,
            verbosity=2 if args.verbose else 1,
        )
    except Exception:
        report = {
            "ok": False,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0],
            "sandbox": {"available": False, "backend": "bubblewrap",
                        "bwrap": "", "version": None,
                        "error": "runner crash", "selftest": not args.no_sandbox},
            "summary": {"total": 1, "passed": 0, "failed": 0, "errors": 1,
                        "skipped": 0, "duration_s": 0.0},
            "tests": [{
                "name": "runner.crash",
                "status": "ERROR",
                "duration_s": 0.0,
                "detail": traceback.format_exc()[-800:],
            }],
        }

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
