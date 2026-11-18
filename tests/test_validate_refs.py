"""Test P2-5 — validate_refs.py (validazione simbodo dei cheat sheet)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.validate_refs as vr  # noqa: E402


class TestValidateRefs(unittest.TestCase):
    def test_refs_real_validi(self):
        reports = [vr.check_ref(p) for p in sorted((ROOT / "GUI" / "refs").glob("*.md"))]
        self.assertTrue(all(r["ok"] for r in reports),
                        [r for r in reports if not r["ok"]])
        self.assertEqual(sum(len(r["missing"]) for r in reports), 0)

    def test_modulo_inesistente(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.md"
            p.write_text("# Modulo: CORE.non_esiste\n`Foo.bar()`\n", encoding="utf-8")
            r = vr.check_ref(p)
            self.assertFalse(r["ok"])
            self.assertIn("<modulo non importabile>", r["missing"])

    def test_simbodo_inesistente_segnalato(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.md"
            p.write_text("# Modulo: CORE.debt_ledger\n`add()` `add.finto_simbodo()`\n",
                         encoding="utf-8")
            r = vr.check_ref(p)
            self.assertFalse(r["ok"])
            self.assertIn("add.finto_simbodo", r["missing"])
            self.assertNotIn("add", r["missing"])

    def test_esterno_non_validato(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ext.md"
            p.write_text("# Modulo: external\n`QualsiasiCosa()`\n", encoding="utf-8")
            r = vr.check_ref(p)
            self.assertTrue(r["ok"])
            self.assertEqual(r["checked"], [])

    def test_resolve_module_fallback(self):
        # file senza header: fallback CORE.<stem senza _api>
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "debt_ledger.md"
            p.write_text("`add()`\n", encoding="utf-8")
            mod, _ = vr.resolve_module(p)
            self.assertIsNotNone(mod)
            self.assertEqual(mod.__name__, "CORE.debt_ledger")


if __name__ == "__main__":
    unittest.main()
