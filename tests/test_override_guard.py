"""
test_override_guard.py — B3: validatore deterministico degli override
auto-skill/auto-tool. Nessun LLM, nessuna rete, file temporanei.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE import auto_skill, auto_tool  # noqa: E402
from CORE.override_guard import (  # noqa: E402
    MAX_KEYWORDS,
    load_validated,
    validate_overrides,
)


class TestOverrideGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / "override.json"
        self.known = {"git-expert", "read_file"}

    def _write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return load_validated(self.path, self.known)

    def test_override_valido(self):
        r = self._write({"git-expert": ["rebase", "tag"]})
        self.assertTrue(r.ok)
        self.assertEqual(r.issues, ())
        self.assertEqual(r.overrides, {"git-expert": ["rebase", "tag"]})

    def test_quattro_invalidi_con_codici_chiari(self):
        cases = [
            ({"sconosciuto_xyz": ["rebase"]}, "unknown_key"),
            ({"git-expert": ["a", "b", "c", "d", "e"]}, "too_many"),
            ({"git-expert": "rebase"}, "bad_type"),
            ({"git-expert": ["x\u0001y"]}, "bad_keyword"),
        ]
        for data, expected in cases:
            with self.subTest(expected=expected):
                r = self._write(data)
                self.assertFalse(r.ok)
                self.assertEqual(r.issues[0].code, expected)
                self.assertTrue(r.issues[0].message)
                self.assertEqual(r.overrides, {})

    def test_duplicati_normalizzati_vengono_dedupati(self):
        r = self._write({"git-expert": ["caffe", "caffè", "rebase"]})
        self.assertFalse(r.ok)
        self.assertEqual(r.issues[0].code, "duplicate")
        self.assertEqual(r.overrides, {"git-expert": ["caffe", "rebase"]})

    def test_cap_di_quattro_keyword(self):
        r = self._write({"git-expert": ["a", "b", "c", "d"]})
        self.assertTrue(r.ok)
        self.assertEqual(len(r.overrides["git-expert"]), MAX_KEYWORDS)

    def test_file_mancante_fail_open_senza_issues(self):
        r = load_validated(self.tmp / "inesistente.json", self.known)
        self.assertTrue(r.ok)
        self.assertEqual(r.overrides, {})
        self.assertEqual(r.issues, ())

    def test_json_invalido_blocca_solo_la_voce(self):
        self.path.write_text("{non json", encoding="utf-8")
        r = load_validated(self.path, self.known)
        self.assertFalse(r.ok)
        self.assertEqual(r.issues[0].code, "invalid_json")

    def test_radice_non_dizionario(self):
        r = validate_overrides(["rebase"], self.known)
        self.assertEqual(r.issues[0].code, "root_type")

    def test_report_markdown(self):
        r = self._write({"sconosciuto_xyz": ["rebase"]})
        md = r.markdown()
        self.assertIn("INVALIDO", md)
        self.assertIn("unknown_key", md)
        self.assertIn("sconosciuto_xyz", md)

    def test_wiring_auto_skill(self):
        self.path.write_text(json.dumps({"git-expert": ["rebase"]}),
                             encoding="utf-8")
        with mock.patch.object(auto_skill, "OVERRIDES_FILE", self.path):
            self.assertEqual(auto_skill._load_overrides(),
                             {"git-expert": ["rebase"]})
            self.assertIn("rebase", auto_skill.keywords_for("git-expert"))
            # voce invalida → non entra nelle keyword
            self.path.write_text(json.dumps({"git-expert": ["a", "b", "c",
                                                            "d", "e"]}),
                                 encoding="utf-8")
            self.assertEqual(auto_skill._load_overrides(), {})
            self.assertNotIn("e", auto_skill.keywords_for("git-expert"))

    def test_wiring_auto_tool(self):
        self.path.write_text(json.dumps({"read_file": ["apri il file"]}),
                             encoding="utf-8")
        with mock.patch.object(auto_tool, "OVERRIDES_FILE", self.path):
            self.assertEqual(auto_tool._load_overrides(),
                             {"read_file": ["apri il file"]})
            self.assertIn("apri il file", auto_tool.keywords_for("read_file"))
            self.path.write_text(json.dumps({"tool_inesistente": ["x"]}),
                                 encoding="utf-8")
            self.assertEqual(auto_tool._load_overrides(), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
