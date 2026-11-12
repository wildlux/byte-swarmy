"""
test_relevant_symbols.py — Test unit di F2 (contesto per modulo).

Senza LLM: simbodo rilevanti per un modulo target.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.code_map import relevant_symbols  # noqa: E402


class TestRelevantSymbols(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _make_proj(self, files: dict[str, str]) -> Path:
        proj = self.tmp / "proj"
        proj.mkdir()
        for name, code in files.items():
            (proj / name).write_text(code, encoding="utf-8")
        return proj

    def test_modulo_stesso(self):
        proj = self._make_proj({
            "utils.py": "def helper(): return 42\n",
        })
        syms = relevant_symbols(proj, "utils.py")
        names = [s["name"] for s in syms]
        self.assertIn("helper", names)

    def test_dipendenti_diretti(self):
        proj = self._make_proj({
            "utils.py": "def helper(): return 42\n",
            "main.py": "from utils import helper\n\ndef run(): return helper()\n",
        })
        syms = relevant_symbols(proj, "utils.py")
        files = {s["file"] for s in syms}
        self.assertIn("utils.py", files)
        self.assertIn("main.py", files)  # chiamante diretto

    def test_dipendenze_del_target(self):
        proj = self._make_proj({
            "utils.py": "def helper(): return 42\n",
            "main.py": "from utils import helper\n\ndef run(): return helper()\n",
        })
        syms = relevant_symbols(proj, "main.py")
        files = {s["file"] for s in syms}
        self.assertIn("main.py", files)
        self.assertIn("utils.py", files)  # dipendenza

    def test_modulo_isolato(self):
        proj = self._make_proj({
            "a.py": "def f(): pass\n",
            "b.py": "def g(): pass\n",
        })
        syms = relevant_symbols(proj, "a.py")
        files = {s["file"] for s in syms}
        self.assertEqual(files, {"a.py"})  # b.py non è rilevante

    def test_fail_open(self):
        syms = relevant_symbols(self.tmp / "nope", "main.py")
        self.assertEqual(syms, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
