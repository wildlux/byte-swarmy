"""
test_mobile_scaffold.py — F1: scaffold iOS/Android verificato offline.

Nessun LLM, SDK, emulatore o rete: solo struttura dei template e ref curati.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import auto_skill  # noqa: E402
from tools import mobile_scaffold_check as msc  # noqa: E402


def test_template_e_ref_esistono():
    for key, spec in msc.SPECS.items():
        assert (msc.TEMPLATES / spec["template"]).is_file(), key
        assert (msc.MOBILE_REFS / spec["ref"]).is_file(), key


def test_gate_strutturale_pass():
    result = msc.check_all()
    assert result["ok"] is True, result
    for key, row in result["platforms"].items():
        assert row["ok"], (key, row["issues"])
        assert row["has_slot"] is True
        assert row["timestamp_free"] is True


def test_gate_rileva_marker_e_simbolo_inventato():
    spec = msc.SPECS["ios"]
    src = (msc.TEMPLATES / spec["template"]).read_text(encoding="utf-8")
    ref = (msc.MOBILE_REFS / spec["ref"]).read_text(encoding="utf-8")
    bad_src = src.replace("var body: some View", "var body: Int")
    bad_ref = ref.replace("`Button`", "`ButtonFinto`")
    assert "costrutto mancante" in " ".join(
        msc.check_source("ios", bad_src, ref)["issues"])
    assert "simbolo senza ref" in " ".join(
        msc.check_source("ios", src, bad_ref)["issues"])


def test_report_deterministico_e_dichiara_build_non_verificata():
    first = msc.markdown(msc.check_all())
    second = msc.markdown(msc.check_all())
    assert first == second
    assert "Non compila Swift/Kotlin" in first
    assert "2/4" in first
    assert "iOS / SwiftUI" in first
    assert "Android / Jetpack Compose" in first


def test_skill_e_keyword_auto_registrati():
    skill = ROOT / ".opencode" / "skill" / "mobile-scaffold" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: mobile-scaffold" in text
    assert "## " in text
    hits = auto_skill.detect_names("crea una app iOS in SwiftUI")
    assert "mobile-scaffold" in hits, hits
    assert "mobile-scaffold" in auto_skill.detect_names(
        "crea una app Android in Kotlin")


def test_modulo_non_importa_client_llm_o_sdk():
    src = (ROOT / "tools" / "mobile_scaffold_check.py").read_text(
        encoding="utf-8")
    for forbidden in ("import requests", "import urllib", "from CORE.models",
                      "OllamaClient", "generate_response", "import swift"):
        assert forbidden not in src
