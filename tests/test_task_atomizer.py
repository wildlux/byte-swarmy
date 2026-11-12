"""
test_task_atomizer.py — Test unit di C1 (atomizzatore) e C2 (ordine topologico).

Senza LLM: parse AST + grafo delle chiamate.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.code_map import decompose_module, dependency_order  # noqa: E402


class TestDecomposeModule(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, code: str) -> Path:
        p = self.tmp / "mod.py"
        p.write_text(code, encoding="utf-8")
        return p

    def test_funzioni_top_level(self):
        p = self._write("def foo(): pass\n\ndef bar(x): return x\n")
        tasks = decompose_module(p)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["symbol"], "foo")
        self.assertEqual(tasks[1]["symbol"], "bar")
        self.assertEqual(tasks[0]["scope"], "function")
        self.assertEqual(tasks[0]["kind"], "function")

    def test_classi(self):
        p = self._write("class A:\n    pass\n\nclass B(A):\n    pass\n")
        tasks = decompose_module(p)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["symbol"], "A")
        self.assertEqual(tasks[1]["symbol"], "B")
        self.assertEqual(tasks[0]["scope"], "class")

    def test_misto(self):
        p = self._write("def f(): pass\n\nclass C: pass\n\ndef g(): pass\n")
        tasks = decompose_module(p)
        self.assertEqual(len(tasks), 3)
        self.assertEqual([t["symbol"] for t in tasks], ["f", "C", "g"])

    def test_file_vuoto(self):
        p = self._write("")
        self.assertEqual(decompose_module(p), [])

    def test_file_non_parsabile(self):
        p = self._write("def f(\n")
        self.assertEqual(decompose_module(p), [])

    def test_file_inesistente(self):
        self.assertEqual(decompose_module(self.tmp / "no.py"), [])

    def test_task_ha_campi(self):
        p = self._write("def foo(): pass\n")
        t = decompose_module(p)[0]
        self.assertIn("title", t)
        self.assertIn("description", t)
        self.assertIn("target_file", t)
        self.assertIn("symbol", t)


class TestDependencyOrder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _make_proj(self, files: dict[str, str]) -> Path:
        proj = self.tmp / "proj"
        proj.mkdir()
        for name, code in files.items():
            (proj / name).write_text(code, encoding="utf-8")
        return proj

    def test_ordine_alfabetico_senza_chiamate(self):
        proj = self._make_proj({"a.py": "x = 1\n", "b.py": "y = 2\n"})
        order = dependency_order(proj)
        self.assertEqual(order, ["a.py", "b.py"])

    def test_dipendenza_semplice(self):
        proj = self._make_proj({
            "utils.py": "def helper(): return 42\n",
            "main.py": "from utils import helper\n\ndef run(): return helper()\n",
        })
        order = dependency_order(proj)
        self.assertLess(order.index("utils.py"), order.index("main.py"))

    def test_catena(self):
        proj = self._make_proj({
            "c.py": "def c(): pass\n",
            "b.py": "from c import c\ndef b(): return c()\n",
            "a.py": "from b import b\ndef a(): return b()\n",
        })
        order = dependency_order(proj)
        self.assertLess(order.index("c.py"), order.index("b.py"))
        self.assertLess(order.index("b.py"), order.index("a.py"))

    def test_progetto_vuoto(self):
        proj = self._make_proj({})
        self.assertEqual(dependency_order(proj), [])

    def test_fail_open_progetto_inesistente(self):
        self.assertEqual(dependency_order(self.tmp / "nope"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
