"""
test_behavioral_diff.py — Test unit di A2 (diff semantico pre/post).

Senza LLM: snapshot/verify su programmi temporanei.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.behavioral_diff import (  # noqa: E402
    load_snapshot,
    save_snapshot,
    snapshot,
    verify,
)


class TestBehavioralDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, code: str) -> Path:
        p = self.tmp / "main.py"
        p.write_text(code, encoding="utf-8")
        return p

    def test_snapshot_crea_output(self):
        p = self._write('print("hello")\n')
        snap = snapshot(p, [""])
        self.assertEqual(len(snap["outputs"]), 1)
        self.assertIn("hello", snap["outputs"][0])

    def test_snapshot_con_input(self):
        p = self._write('import sys\nprint("echo:", sys.stdin.read().strip())\n')
        snap = snapshot(p, ["42", "abc"])
        self.assertEqual(len(snap["outputs"]), 2)
        self.assertIn("42", snap["outputs"][0])
        self.assertIn("abc", snap["outputs"][1])

    def test_save_load_roundtrip(self):
        p = self._write('print("x")\n')
        snap = snapshot(p, [""])
        save_snapshot(p, snap)
        loaded = load_snapshot(p)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["outputs"], snap["outputs"])

    def test_verify_ok(self):
        code = 'print("hello")\n'
        p = self._write(code)
        snap = snapshot(p, [""])
        ok, diff = verify(p, snap)
        self.assertTrue(ok)
        self.assertEqual(diff, "")

    def test_verify_divergenza(self):
        p = self._write('print("hello")\n')
        snap = snapshot(p, [""])
        # Modifica il codice → output diverso
        p.write_text('print("goodbye")\n', encoding="utf-8")
        ok, diff = verify(p, snap)
        self.assertFalse(ok)
        self.assertIn("COMPORTAMENTO CAMBIATO", diff)
        self.assertIn("hello", diff)
        self.assertIn("goodbye", diff)

    def test_verify_crash(self):
        p = self._write('print("hello")\n')
        snap = snapshot(p, [""])
        # Codice che crasha
        p.write_text('raise ValueError("boom")\n', encoding="utf-8")
        ok, diff = verify(p, snap)
        self.assertFalse(ok)
        self.assertIn("__ERROR__", diff)

    def test_verify_snapshot_malformato_fail_open(self):
        p = self._write('print("hello")\n')
        ok, diff = verify(p, {"garbage": True})
        self.assertTrue(ok)
        self.assertEqual(diff, "")

    def test_load_snapshot_inesistente(self):
        p = self._write('print("x")\n')
        # cancella lo snapshot se esiste
        from CORE.behavioral_diff import _snapshot_path
        sp = _snapshot_path(p)
        if sp.exists():
            sp.unlink()
        self.assertIsNone(load_snapshot(p))


if __name__ == "__main__":
    unittest.main(verbosity=2)
