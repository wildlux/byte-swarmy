#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase E — distill occasionale: ingestione gate-verificata nel corpus.

Il modello più grande (7b/14b) NON gira qui: il tool riceve una soluzione
già prodotta esternamente e la accetta solo se supera gate deterministici
offline. Nessun client LLM, nessuna rete, nessuna GPU.

Gate (tutti prima della scrittura):
  1. file esistente, non vuoto, <= MAX_LINES righe;
  2. sintassi Python valida (AST);
  3. pyflakes: 0 finding;
  4. security_scan sul solo file: 0 errori;
  5. expected_marker del caso eval presente nella soluzione;
  6. per `--commit`, fan_verified.json valido (fan_rpm > 0, temp_c <= 60)
     perché la soluzione dichiarata viene da un run LLM live.

Uso:
    .venv/bin/python tools/distill_task.py --task eval-slot-01 \
        --solution /tmp/sol.py --model qwen2.5-coder:14b
    .venv/bin/python tools/distill_task.py ... --commit   # scrive il corpus
    .venv/bin/python tools/distill_task.py ... --json

Criterio done Fase E: tool + >=3 esempi REALI nel corpus. Il dry-run e i test
usano soluzioni sintetiche e NON contano come esempi.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import feedback_corpus as fc  # noqa: E402
from tools import security_scan  # noqa: E402

CASES = ROOT / "evals" / "cases.json"
FAN_FILE = ROOT / "data" / "state" / "fan_verified.json"
MAX_LINES = 200
MAX_TEMP_C = 60.0


def load_case(task_id: str, path: Path = CASES) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for case in data:
        if case.get("id") == task_id:
            if not case.get("expected_marker"):
                raise ValueError(f"caso {task_id} senza expected_marker: "
                                 "pass@1 non verificabile")
            return case
    raise ValueError(f"caso eval sconosciuto: {task_id}")


def thermal_ok() -> bool:
    try:
        data = json.loads(FAN_FILE.read_text(encoding="utf-8"))
        return (float(data.get("fan_rpm", 0)) > 0
                and float(data.get("temp_c", 999)) <= MAX_TEMP_C)
    except (OSError, ValueError, TypeError):
        return False


def _pyflakes_messages(source: str, name: str) -> list[str]:
    from pyflakes.api import check
    from pyflakes.reporter import Reporter

    out, err = io.StringIO(), io.StringIO()
    check(source, name, Reporter(out, err))
    return [line for line in (out.getvalue() + err.getvalue()).splitlines()
            if line.strip()]


def _security_findings(source: str, name: str) -> list[dict]:
    """Scansiona il solo file in una copia temporanea sotto data/state/tmp.

    security_scan richiede path sotto la radice del repo; la copia è
    gitignored (`state/`) e viene rimossa in `finally`, anche in caso di errore.
    """
    tmpdir = ROOT / "data" / "state" / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    probe = tmpdir / f"distill_{name}"
    probe.write_text(source, encoding="utf-8")
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            security_scan.main([str(probe), "--json"])
        findings = json.loads(buffer.getvalue())
        rel = str(probe.relative_to(ROOT))
        return [f for f in findings if f.get("path") == rel
                and f.get("level") == "error"]
    finally:
        probe.unlink(missing_ok=True)


def verify_solution(path: Path, case: dict) -> dict:
    """Restituisce gate + esito senza scrivere nulla."""
    gates: dict[str, bool] = {}
    detail: dict[str, object] = {}

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"ok": False, "gates": {"leggibile": False},
                "detail": {"errore": str(exc)}, "lines": 0}
    lines = source.splitlines()
    gates["leggibile"] = bool(source.strip())
    gates["dimensione"] = 0 < len(lines) <= MAX_LINES
    detail["lines"] = len(lines)

    try:
        ast.parse(source, filename=str(path))
        gates["sintassi"] = True
    except SyntaxError as exc:
        gates["sintassi"] = False
        detail["syntax_error"] = f"riga {exc.lineno}: {exc.msg}"

    pyflakes = _pyflakes_messages(source, path.name)
    gates["pyflakes"] = not pyflakes
    if pyflakes:
        detail["pyflakes"] = pyflakes[:5]

    findings = _security_findings(source, path.name) if gates["sintassi"] else []
    gates["security_scan"] = not findings
    if findings:
        detail["security"] = findings[:5]

    marker = str(case["expected_marker"])
    gates["marker"] = marker in source
    detail["marker"] = marker

    return {"ok": all(gates.values()), "gates": gates,
            "detail": detail, "lines": len(lines)}


def run(task_id: str, solution: Path, model: str, commit: bool = False,
        state_dir: Path | None = None) -> dict:
    if not model.strip():
        raise ValueError("--model obbligatorio: dichiara chi ha prodotto "
                         "la soluzione (nessuna attribuzione anonima)")
    case = load_case(task_id)
    result = verify_solution(solution, case)
    result.update({"task_id": task_id, "model": model,
                   "source": "commit" if commit else "dry-run",
                   "written": False})
    if not result["ok"]:
        return result
    if not commit:
        return result
    if not thermal_ok():
        result["ok"] = False
        result["detail"]["thermal"] = (
            "fan_verified.json assente o non valido: serve fan_rpm > 0 "
            "e temp_c <= 60 per una soluzione da modello live")
        return result

    triple = fc.Triple(
        task_id=task_id,
        kind="code",
        title=str(case.get("title", "")),
        description=str(case.get("description", "")),
        refs=tuple(case.get("refs") or ()),
        output=solution.read_text(encoding="utf-8"),
        verdict="done",
        first_try=True,
        attempts=1,
        model=model,
        reason="distill Fase E: gate deterministico verificato",
        ts=0.0,  # nessun timestamp: l'ingestione resta deterministica
    )
    existing = fc.load_task(task_id, state_dir=state_dir)
    if any(t.dedup_key() == triple.dedup_key() for t in existing):
        result["detail"]["duplicate"] = "già presente nel corpus, skip"
        return result
    path = fc.append_triple(triple, state_dir=state_dir)
    result["written"] = True
    result["detail"]["corpus"] = str(path)
    return result


def markdown(result: dict) -> str:
    lines = [
        "# Fase E — distill task",
        "",
        f"Task: `{result['task_id']}` — modello dichiarato: `{result['model']}`",
        f"Modalità: **{result['source'].upper()}**",
        "",
        "| Gate | Esito |",
        "|---|---|",
    ]
    for gate, ok in result["gates"].items():
        lines.append(f"| {gate} | {'✅' if ok else '❌'} |")
    lines += ["", f"Verdetto: **{'PASS' if result['ok'] else 'BLOCK'}**", ""]
    if result["detail"]:
        lines.append("```json")
        lines.append(json.dumps(result["detail"], indent=2,
                                ensure_ascii=False))
        lines.append("```")
        lines.append("")
    if result["source"] == "dry-run":
        lines += [
            "> ⚠️ Dry-run: **nessuna riga scritta**. Una soluzione sintetica "
            "di test NON è un esempio di distillazione reale.",
            "> Criterio done Fase E: `tools/distill_task.py` + **≥3 esempi "
            "reali** nel corpus, prodotti da un modello più grande con gate "
            "termico verificato.",
            "",
        ]
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True, help="id del caso in evals/cases.json")
    p.add_argument("--solution", required=True, type=Path,
                   help="file Python con la soluzione da verificare")
    p.add_argument("--model", required=True,
                   help="modello che ha prodotto la soluzione (dichiarazione)")
    p.add_argument("--commit", action="store_true",
                   help="scrive nel corpus (richiede gate termico)")
    p.add_argument("--state-dir", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", type=Path, help="scrive il report Markdown")
    args = p.parse_args(argv)

    try:
        result = run(args.task, args.solution, args.model,
                     commit=args.commit, state_dir=args.state_dir)
    except (ValueError, OSError) as exc:
        print(f"BLOCCATO: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, ensure_ascii=False) if args.json \
        else markdown(result)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Report scritto: {args.out}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
