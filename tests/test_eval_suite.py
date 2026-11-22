"""test_eval_suite.py — lock offline della eval suite (Fase A).

Verifica che `evals/cases.json` e `tools/run_eval.py` espongano lo slice
deterministico già realizzato: ≥12 casi validi, 8 assi, 3 granularità e
dry-run JSON utilizzabile senza LLM. Nessun modello, rete o scrittura.

Il verdetto pass@1 resta fuori: richiede `--live` e il gate termico.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from tools.run_eval import (  # noqa: E402
    CASES,
    VALID_AXES,
    VALID_GRAN,
    load_cases,
    main,
    summarize,
    validate_cases,
)


def test_cases_json_caricabile_e_valido():
    cases = load_cases()
    assert validate_cases(cases) == []
    assert len(cases) >= 12


def test_copertura_assi_e_granularita():
    summary = summarize(load_cases())
    assert set(summary["by_axis"]) == VALID_AXES
    assert set(summary["by_granularity"]) == VALID_GRAN
    assert summary["total"] >= 12


def test_validazione_rileva_casi_corrotti():
    cases = load_cases()
    bad = [dict(cases[0]), dict(cases[0])]
    bad[1]["id"] = bad[0]["id"]
    errors = validate_cases(bad)
    assert any("duplicato" in e for e in errors)
    assert any("axis sconosciuto" in e for e in validate_cases(
        [{**cases[0], "axis": "inesistente"}]))


def test_dry_run_json_e_deterministico():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        rc = main(["--dry-run", "--json"])
    assert rc == 0
    payload = json.loads(buffer.getvalue())
    assert payload["valid"] is True
    assert payload["errors"] == []
    assert payload["summary"]["total"] == len(load_cases())
    assert payload["summary"]["by_axis"] == summarize(load_cases())["by_axis"]


def test_file_cases_sotto_versione():
    assert CASES.is_file()
    assert len(CASES.read_text(encoding="utf-8")) > 100
