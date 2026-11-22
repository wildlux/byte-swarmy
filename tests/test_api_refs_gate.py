# -*- coding: utf-8 -*-
"""Gate di fedeltà API: firme e versioni dei cheat sheet (2026-11-22).

Nessuna rete e nessun LLM: modulo fake in tmp_path, confronto via
`inspect.signature` e `__version__`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_refs as vr  # noqa: E402
from CORE.tools import TOOL_SIGNATURES, ToolSet  # noqa: E402
from CORE.worker import Worker  # noqa: E402

_FAKE_MODULE = '''\
"""Modulo fake per i test di fedeltà API."""
__version__ = "1.0.0"


def greet(name, loud=False, prefix=""):
    return prefix + name
'''


def _ref(tmp_path, monkeypatch, header):
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    (tmp_path / "fake_api.py").write_text(_FAKE_MODULE, encoding="utf-8")
    path = tmp_path / "fake_api.md"
    path.write_text(f"# Modulo: fake_api\n{header}\n`greet()`\n",
                    encoding="utf-8")
    return path


def test_firma_corretta_passa(tmp_path, monkeypatch):
    ref = _ref(tmp_path, monkeypatch,
               "# Firma: `greet(name, loud=False, prefix='')`")
    report = vr.check_ref(ref)
    assert report["ok"], report
    assert report["signatures_checked"] == ["greet"]
    assert report["signature_mismatch"] == []


def test_firma_con_parametro_inventato_fails(tmp_path, monkeypatch):
    ref = _ref(tmp_path, monkeypatch, "# Firma: `greet(name, loud, extra)`")
    report = vr.check_ref(ref)
    assert not report["ok"]
    assert any("greet" in m for m in report["signature_mismatch"])


def test_versione_corretta_passa(tmp_path, monkeypatch):
    ref = _ref(tmp_path, monkeypatch, "# Versione: fake_api==1.0.0")
    report = vr.check_ref(ref)
    assert report["ok"], report
    assert report["declared_version"] == "fake_api==1.0.0"
    assert report["installed_version"] == "1.0.0"


def test_versione_disallineata_fails(tmp_path, monkeypatch):
    ref = _ref(tmp_path, monkeypatch, "# Versione: fake_api==9.9.9")
    report = vr.check_ref(ref)
    assert not report["ok"]
    assert any("9.9.9" in m for m in report["version_mismatch"])


def test_firma_e_versione_insieme(tmp_path, monkeypatch):
    ref = _ref(tmp_path, monkeypatch,
               "# Versione: fake_api==1.0.0\n"
               "# Firma: `greet(name, loud=False, prefix='')`")
    report = vr.check_ref(ref)
    assert report["ok"], report
    assert len(report["signatures_checked"]) == 1
    assert report["version_unverified"] == []


def test_modulo_senza_versione_non_fails(tmp_path, monkeypatch):
    """Backward compatibility: i ref esistenti senza header restano validi."""
    ref = _ref(tmp_path, monkeypatch, "")
    report = vr.check_ref(ref)
    assert report["ok"], report
    assert report["declared_version"] is None


def _lookup(module, symbol, strict):
    return ToolSet.api_lookup(SimpleNamespace(project_root=ROOT),
                              module, symbol, strict)


def test_api_lookup_strict_verifica_firma_reale():
    out = _lookup("json", "dumps", True)
    assert "firma: dumps" in out
    assert "VERIFICATO via inspect" in out


def test_api_lookup_strict_blocca_simbolo_inesistente():
    out = _lookup("json", "dumps_finto", True)
    assert out.startswith("ERROR")
    assert "API NON VERIFICATA" in out


def test_api_lookup_strict_rifiuta_elenco_generico():
    out = _lookup("json", "", True)
    assert out.startswith("ERROR")
    assert "specificare un simbolo" in out


def test_api_lookup_normale_resta_fail_open():
    """Senza strict il comportamento storico (elenco pubblico) resta."""
    out = _lookup("json", "", False)
    assert out.startswith("SIMBODI PUBBLICI")
    out = _lookup("modulo_inesistente_xyz", "foo", False)
    assert out.startswith("ERROR") and "NON VERIFICATA" not in out


def test_api_lookup_strict_registrato_nel_worker():
    assert "strict=True" in TOOL_SIGNATURES["api_lookup"]
    assert Worker.TOOL_CODE_MAP["api"] == "api_lookup"
