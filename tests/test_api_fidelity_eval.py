"""
test_api_fidelity_eval.py — E2: fedeltà API su librerie fuori cheat sheet.
Nessun LLM, rete o GPU: introspezione runtime + AST + ref validati.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.api_fidelity_eval as ev  # noqa: E402
import tools.gen_api_refs as gen  # noqa: E402
import tools.validate_refs as vr  # noqa: E402
from CORE.tools import ToolSet  # noqa: E402


def _lookup(module, symbol):
    return ToolSet.api_lookup(SimpleNamespace(project_root=ROOT),
                              module, symbol, True)


def test_due_librerie_fuori_cheat_sheet_passano():
    report = ev.evaluate()
    assert report["ok"], report
    assert report["undefined_total"] == 0
    assert {c["module"] for c in report["cases"]} == {"json", "csv"}
    assert all(c["symbols"] for c in report["cases"])


def test_ref_generati_sono_validi_e_con_firme():
    for module in ("json", "csv"):
        ref = ev.REFS_DIR / f"{module}_api.md"
        assert ref.exists(), ref
        r = vr.check_ref(ref)
        assert r["ok"], r
        assert r["signatures_checked"], r


def test_generatore_produce_header_compatibile_e_is_deterministico():
    text = gen.generate("csv", max_items=50)
    assert "# Modulo: csv" in text
    assert "# Firma: `reader(" in text
    assert gen.generate("csv", max_items=50) == text


def test_simbolo_inventato_blocca():
    cases = [{"id": "fake", "module": "json",
              "code": "import json\njson.dumps_finto({})\n"}]
    report = ev.evaluate(cases=cases, refs=False)
    assert not report["ok"]
    assert report["undefined_total"] == 1
    assert "dumps_finto" in report["cases"][0]["undefined"][0]


def test_sintassi_invalida_blocca():
    cases = [{"id": "bad", "module": "json",
              "code": "import json\njson.dumps({\n"}]
    report = ev.evaluate(cases=cases, refs=False)
    assert not report["ok"]
    assert report["cases"][0]["error"]


def test_ref_assente_blocca():
    report = ev.evaluate(cases=[{"id": "fake", "module": "modulo_xxx_inesistente",
                                 "code": "import modulo_xxx_inesistente\n"}],
                         refs=True)
    assert not report["ok"]
    assert report["bad_refs"] == 1


def test_api_lookup_strict_verifica_costante_reale():
    out = _lookup("csv", "QUOTE_MINIMAL")
    assert "VERIFICATO via inspect" in out
    assert "costante:" in out
    assert not out.startswith("ERROR")


def test_report_markdown_deterministico():
    a = ev.markdown(ev.evaluate())
    b = ev.markdown(ev.evaluate())
    assert a == b
    assert "0 simboli indefiniti" in a
    assert "json_api.md" in a
