"""test_distill_task.py — Fase E: distill gate-verificato, preparazione offline.

Nessun LLM, rete o GPU: le soluzioni sono file temporanei sintetici. I test
bloccano i gate deterministici, il rifiuto del commit senza evidenza termica,
la deduplicazione del corpus e l'onestà del report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.distill_task as dt  # noqa: E402

VALID = '''def greet(name):
    """Saluta l'utente."""
    return f"Hello, {name}!"
'''


def _solution(tmp_path: Path, text: str = VALID) -> Path:
    path = tmp_path / "solution.py"
    path.write_text(text, encoding="utf-8")
    return path


def test_caso_eval_caricato_e_marker_obbligatorio():
    case = dt.load_case("eval-minimal-02")
    assert case["expected_marker"] == "def greet"
    with pytest.raises(ValueError) as exc:
        dt.load_case("inesistente")
    assert "sconosciuto" in str(exc)
    with pytest.raises(ValueError):
        dt.load_case("eval-gate-01")  # expected_fail, senza marker


def test_gate_verde_su_soluzione_valida_senza_scrivere(tmp_path):
    result = dt.run("eval-minimal-02", _solution(tmp_path), "test:14b",
                    state_dir=tmp_path / "state")
    assert result["ok"] is True
    assert all(result["gates"].values())
    assert result["source"] == "dry-run" and result["written"] is False
    assert not (tmp_path / "state").exists()


def test_gate_blocca_sintassi_pyflakes_security_marker_e_dimensione(tmp_path):
    case = dt.load_case("eval-minimal-02")
    bad = {
        "sintassi": "def greet(:\n",
        "pyflakes": "def greet(name):\n    return undefined_name\n",
        "security_scan": VALID + '\neval("1+1")\n',
        "marker": "def other():\n    pass\n",
        "dimensione": "def greet(name):\n" + "# padding\n" * 250
                      + "    return 1\n",
    }
    for label, text in bad.items():
        result = dt.verify_solution(_solution(tmp_path, text), case)
        assert result["ok"] is False, label
        assert result["gates"][label] is False, (label, result["gates"])


def test_file_vuoto_rifiutato(tmp_path):
    case = dt.load_case("eval-minimal-02")
    result = dt.verify_solution(_solution(tmp_path, "   \n"), case)
    assert result["ok"] is False
    assert result["gates"]["leggibile"] is False


def test_modello_obbligatorio():
    with pytest.raises(ValueError) as exc:
        dt.run("eval-minimal-02", Path("noop.py"), "  ")
    assert "--model" in str(exc.value)


def test_commit_bloccato_senza_gate_termico(tmp_path, monkeypatch):
    monkeypatch.setattr(dt, "FAN_FILE", tmp_path / "assente.json")
    state = tmp_path / "state"
    result = dt.run("eval-minimal-02", _solution(tmp_path), "test:14b",
                    commit=True, state_dir=state)
    assert result["ok"] is False
    assert "fan_rpm" in result["detail"]["thermal"]
    assert result["written"] is False
    assert not state.exists()


def test_commit_scrive_tripla_e_deduplica(tmp_path, monkeypatch):
    fan = tmp_path / "fan.json"
    fan.write_text(json.dumps({"fan_rpm": 1800, "temp_c": 50}),
                   encoding="utf-8")
    monkeypatch.setattr(dt, "FAN_FILE", fan)
    state = tmp_path / "state"
    sol = _solution(tmp_path)

    first = dt.run("eval-minimal-02", sol, "test:14b", commit=True,
                   state_dir=state)
    assert first["ok"] is True and first["written"] is True
    triples = dt.fc.load_task("eval-minimal-02", state_dir=state)
    assert len(triples) == 1
    assert triples[0].verdict == "done"
    assert triples[0].model == "test:14b"
    assert triples[0].ts == 0.0  # nessun timestamp inventato

    second = dt.run("eval-minimal-02", sol, "test:14b", commit=True,
                    state_dir=state)
    assert second["ok"] is True and second["written"] is False
    assert "duplicate" in second["detail"]
    assert len(dt.fc.load_task("eval-minimal-02", state_dir=state)) == 1


def test_report_dichiara_sintetico_e_deterministico(tmp_path):
    result = dt.run("eval-minimal-02", _solution(tmp_path), "test:14b")
    text = dt.markdown(result)
    assert "DRY-RUN" in text
    assert "NON è un esempio di distillazione reale" in text
    assert "≥3 esempi reali" in text
    assert dt.markdown(result) == text
    assert "PASS" in text


def test_cli_json_e_exit_code(tmp_path, capsys):
    sol = _solution(tmp_path)
    assert dt.main(["--task", "eval-minimal-02", "--solution", str(sol),
                    "--model", "test:14b", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True and payload["written"] is False

    bad = _solution(tmp_path, "def greet(:\n")
    assert dt.main(["--task", "eval-minimal-02", "--solution", str(bad),
                    "--model", "test:14b", "--json"]) == 1


def test_modulo_non_importa_client_llm_e_non_lascia_residui(tmp_path):
    src = (ROOT / "tools" / "distill_task.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response"):
        assert forbidden not in src
    dt.verify_solution(_solution(tmp_path), dt.load_case("eval-minimal-02"))
    assert not list((ROOT / "data" / "state" / "tmp").glob("distill_*"))
