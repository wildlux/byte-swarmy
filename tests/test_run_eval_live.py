"""test_run_eval_live.py — gate e wiring del runner live della eval suite.

Nessun LLM, rete o GPU: il worker è un fake che scrive file su tmp_path.
I test bloccano il rifiuto senza gate valido, l'assenza di import CORE a
livello di modulo, il formato dei risultati accettato da eval_by_slot,
la registrazione dei fallimenti e l'interruzione termica.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.eval_by_slot as es  # noqa: E402
import tools.run_eval as reval  # noqa: E402


class FakeWorker:
    """Worker deterministico: scrive il marker in un file 'toccato'."""

    def __init__(self, case, tmp_path, *, write_marker=True, error=None,
                 attempts=1):
        self.last_attempts = attempts
        self._error = error
        rel = f"{case['id']}.py"
        full = tmp_path / rel
        body = "x = 1\n"
        if write_marker:
            body += f"{case['expected_marker']}()\n"
        full.write_text(body, encoding="utf-8")
        self.tools = SimpleNamespace(touched_python={rel: str(full)})

    def execute(self, task):
        return self._error or "done"


def fake_factory(tmp_path, **kwargs):
    def factory(case):
        return FakeWorker(case, tmp_path, **kwargs)
    return factory


def gate(tmp_path, rpm=1800):
    path = tmp_path / "fan_verified.json"
    path.write_text(json.dumps({
        "fan_rpm": rpm,
        "temp_c": 45.0,
        "measured_at": "2026-11-23T00:00:00+00:00",
        "sources": {"temperature": "coretemp", "fan_rpm": "tachometro"},
    }), encoding="utf-8")
    return path


def test_modulo_non_importa_core_a_livello_di_modulo():
    src = (ROOT / "tools" / "run_eval.py").read_text(encoding="utf-8")
    assert not re.search(r"^(from|import) CORE\b", src, re.MULTILINE)
    assert "build_default_worker_factory" in src


def test_gate_assente_o_freddo_rifiuta():
    with pytest.raises(reval.GateError) as exc:
        reval.require_gate(Path("/inesistente/fan_verified.json"),
                           temp_fn=lambda: 44)
    assert "NON VALIDO" in str(exc)

    path = gate(Path("/tmp"))
    with pytest.raises(reval.GateError) as hot:
        reval.require_gate(path, temp_fn=lambda: 65)
    assert "temperatura live" in str(hot)


def test_run_live_produce_records_live_e_wiring_con_eval_by_slot(tmp_path):
    cases = reval.load_cases()
    out = tmp_path / "results.json"
    g = reval.require_gate(gate(tmp_path), temp_fn=lambda: 44, interval=0)

    data = reval.run_live(cases, g, fake_factory(tmp_path),
                          temp_fn=lambda: 46, out_path=out, interval=0)

    assert data["source"] == "live"
    assert data["aborted"] is False
    assert data["executed_cases"] == 11
    assert len(data["excluded_cases"]) == 2
    assert all(r["passed"] for r in data["records"])
    assert all(r["error"] is None for r in data["records"])
    assert all(r["output_lines"] > 0 for r in data["records"])
    assert data["thermal"]["fan_rpm"] == 1800
    # La media include anche il campione del pre-flight (44 °C).
    assert data["thermal"]["temp_c"] == 45.8
    assert data["thermal"]["temp_max_c"] == 46
    assert data["thermal"]["temp_policy"] == "media_con_picco_le_60"
    assert g["temp_samples"] == [44.0] * 5

    # il file è davvero accettato dal reporter SLOT-5, senza surrogati
    loaded, live = es.load_results(out, es.load_cases())
    assert live is True
    assert loaded["source"] == "live"


def test_fallimento_worker_e_error_non_diventa_pass(tmp_path):
    cases = reval.load_cases()
    g = reval.require_gate(gate(tmp_path), temp_fn=lambda: 44, interval=0)
    out = tmp_path / "fail.json"

    data = reval.run_live(cases[:1], g,
                          fake_factory(tmp_path, write_marker=False,
                                       error="ERROR: boom"),
                          temp_fn=lambda: 44, out_path=out, interval=0)
    row = data["records"][0]
    assert row["passed"] is False
    assert row["marker_found"] is False
    assert "ERROR: boom" in row["error"]

    data = reval.run_live(cases[:1], g,
                          lambda case: (_ for _ in ()).throw(ValueError("nope")),
                          temp_fn=lambda: 44, out_path=out, interval=0)
    assert data["records"][0]["passed"] is False
    assert "ValueError: nope" in data["records"][0]["error"]


def test_retry_interno_non_e_primo_colpo(tmp_path):
    cases = reval.load_cases()
    g = reval.require_gate(gate(tmp_path), temp_fn=lambda: 44, interval=0)
    out = tmp_path / "retry.json"
    data = reval.run_live(cases[:1], g,
                          fake_factory(tmp_path, attempts=3),
                          temp_fn=lambda: 44, out_path=out, interval=0)
    assert data["records"][0]["marker_found"] is True
    assert data["records"][0]["passed"] is False


def test_surriscaldamento_interrompe_e_non_puo_essere_accettato(tmp_path):
    cases = reval.load_cases()
    g = reval.require_gate(gate(tmp_path), temp_fn=lambda: 44, interval=0)
    out = tmp_path / "hot.json"
    # 5 campioni per caso: il primo giro è freddo, il secondo ha un picco.
    temps = iter([44.0] * 5 + [44.0, 45.0, 61.0, 46.0, 45.0])

    data = reval.run_live(cases, g, fake_factory(tmp_path),
                          temp_fn=lambda: next(temps), out_path=out,
                          interval=0, cooldown_max_s=0)
    assert data["aborted"] is True
    assert "61.0" in data["abort_reason"]
    assert "picco" in data["abort_reason"]
    assert data["executed_cases"] == 1
    # Il PICCO finisce in temp_c: il reporter deve rifiutare il risultato.
    assert data["thermal"]["temp_c"] == 61.0
    assert data["thermal"]["temp_max_c"] == 61.0
    # Campioni coerenti con il picco che ha interrotto il run.
    assert data["thermal"]["temp_samples"] == [44.0, 45.0, 61.0, 46.0, 45.0]
    assert data["abort_thermal"]["temp_max_c"] == 61.0
    with pytest.raises(ValueError) as exc:
        es.load_results(out, es.load_cases())
    assert "surrogato" in str(exc)


def test_cooldown_attende_e_fa_partire_il_caso(tmp_path):
    """Se la CPU è calda tra due casi, si attende: la soglia non cambia."""
    g = reval.require_gate(gate(tmp_path), temp_fn=lambda: 44, interval=0)
    out = tmp_path / "cooldown.json"
    temps = iter([65.0] * 5 + [50.0] * 5)
    sleeps: list[float] = []

    data = reval.run_live(
        reval.load_cases()[:1], g, fake_factory(tmp_path),
        temp_fn=lambda: next(temps), out_path=out, interval=0,
        sleep_fn=sleeps.append, cooldown_max_s=30, cooldown_poll_s=10)

    assert data["aborted"] is False
    assert data["executed_cases"] == 1
    assert data["records"][0]["passed"] is True
    assert sleeps == [10.0]
    assert data["thermal"]["cooldown_waited_s"] == 10.0
    # La media include anche il campione freddo del pre-flight (44 °C).
    assert data["thermal"]["temp_c"] == 47.0
    # Nessun campione sopra 60 può entrare nell'evidenza finale.
    assert data["thermal"]["temp_max_c"] == 50.0
    es.load_results(out, es.load_cases())


def test_cooldown_esaurito_interrompe_e_reporter_rifiuta(tmp_path):
    """Attesa limitata: se non raffredda, il run resta non misurato."""
    g = reval.require_gate(gate(tmp_path), temp_fn=lambda: 44, interval=0)
    out = tmp_path / "cooldown_hot.json"
    sleeps: list[float] = []

    data = reval.run_live(
        reval.load_cases(), g, fake_factory(tmp_path),
        temp_fn=lambda: 66, out_path=out, interval=0,
        sleep_fn=sleeps.append, cooldown_max_s=20, cooldown_poll_s=10)

    assert data["aborted"] is True
    assert data["executed_cases"] == 0
    assert "esaurita" in data["abort_reason"]
    assert sleeps == [10.0, 10.0]
    assert data["thermal"]["temp_c"] == 66.0
    with pytest.raises(ValueError) as exc:
        es.load_results(out, es.load_cases())
    assert "surrogato" in str(exc)


def test_media_sotto_60_con_picco_sopra_60_blocca_comunque(tmp_path):
    """La media non deve poter mascherare un picco termico."""
    values = iter([48.0, 49.0, 68.0, 50.0, 49.0])
    sample = reval.sample_thermal(lambda: next(values), interval=0)
    assert sample["temp_c"] == 52.8
    assert sample["temp_max_c"] == 68.0
    assert reval.thermal_ok(sample) is False

    vals = iter([48.0, 49.0, 68.0, 50.0, 49.0])
    with pytest.raises(reval.GateError) as exc:
        reval.require_gate(gate(tmp_path), temp_fn=lambda: next(vals),
                           interval=0)
    assert "picco 68.0" in str(exc)


def test_media_e_picco_entro_60_accetta(tmp_path):
    values = iter([52.0, 55.0, 54.0, 53.0, 56.0])
    sample = reval.sample_thermal(lambda: next(values), interval=0)
    assert sample["temp_c"] == 54.0
    assert sample["temp_max_c"] == 56.0
    assert reval.thermal_ok(sample) is True
    vals = iter([52.0, 55.0, 54.0, 53.0, 56.0])
    g = reval.require_gate(gate(tmp_path), temp_fn=lambda: next(vals),
                           interval=0)
    assert g["temp_c"] == 54.0
    assert g["temp_max_c"] == 56.0


def test_cli_live_senza_gate_rifiuta_con_exit_2(tmp_path, capsys,
                                                monkeypatch):
    monkeypatch.chdir(ROOT)
    rc = reval.main(["--live", "--fan-file",
                     str(tmp_path / "assente.json")])
    assert rc == 2
    assert "RIFIUTO" in capsys.readouterr().err


def test_dry_run_resta_invariante_e_non_tocca_il_gate(tmp_path, capsys):
    rc = reval.main(["--dry-run", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["summary"]["total"] >= 12
