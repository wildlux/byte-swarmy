"""Test della pipeline SLOT: gate per-slot, assembler, import-check.

Zero LLM. Copre:
- SLOT-1: `gate_slot` (sintassi, nomi indefiniti, refs, self implicito);
- SLOT-2: `assemble_slots` (anchor, import sollevati e dedupe, indentazione);
- P1-2: `import_check` (backend pyflakes + fallback AST).
"""

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE import import_check  # noqa: E402
from CORE.import_check import check_path, check_source, format_report  # noqa: E402
from CORE.slot_assembler import (  # noqa: E402
    AssemblerError,
    assemble_slots,
    assemble_to_file,
    slot_anchors,
)
from CORE.slot_gate import gate_slot, names_from_refs  # noqa: E402


class TestImportCheck(unittest.TestCase):
    def test_pyflakes_trova_nome_indefinito(self):
        issues = check_source("def f():\n    return missing_api(1)\n")
        self.assertTrue(any("missing_api" in i.message for i in issues))
        self.assertEqual(issues[0].kind, "undefined_name")

    def test_nomi_known_non_segnalati(self):
        issues = check_source("def f():\n    return known_api()\n",
                              known={"known_api"})
        self.assertEqual(issues, [])

    def test_scope_locali_senza_falsi_positivi(self):
        source = textwrap.dedent('''
            def outer(items):
                total = 0
                for item in items:
                    total += item
                squares = [x * x for x in items]
                return total, squares, len(items)
        ''')
        self.assertEqual(check_source(source), [])

    def test_classe_con_self(self):
        source = textwrap.dedent('''
            class A:
                def run(self, value):
                    return self.helper(value)
                def helper(self, value):
                    return value + 1
        ''')
        self.assertEqual(check_source(source), [])

    def test_syntax_error(self):
        issues = check_source("def broken(:\n    pass\n")
        self.assertTrue(issues)
        self.assertEqual(issues[0].kind, "syntax")

    def test_check_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.py"
            p.write_text("def f():\n    return nope\n", encoding="utf-8")
            issues = check_path(p)
            self.assertTrue(any("nope" in i.message for i in issues))
            self.assertIn("m.py", str(issues[0]))

    def test_format_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.py"
            p.write_text("def f():\n    return ghost\n", encoding="utf-8")
            report = format_report({"bad.py": check_path(p)})
            self.assertIn("bad.py", report)
            self.assertIn("ghost", report)

    def test_fallback_ast_copre_scope(self):
        source = textwrap.dedent('''
            def outer(arg):
                local = arg + 1
                return local + global_missing
        ''')
        issues = import_check._ast_issues(source, "<f>")
        self.assertEqual([i.message for i in issues],
                         ["undefined name 'global_missing'"])

    def test_fallback_ast_builtins_e_classi(self):
        source = textwrap.dedent('''
            class A:
                value = 1
                def run(self):
                    return len([self.value])
        ''')
        self.assertEqual(import_check._ast_issues(source, "<f>"), [])


class TestSlotGate(unittest.TestCase):
    def test_frammento_valido(self):
        verdict = gate_slot(
            "def greet(name):\n    return f'hi {name}'\n",
            refs=[], kind="function")
        self.assertTrue(verdict.ok, verdict.detail())
        self.assertEqual(verdict.errors, [])

    def test_nome_indefinito_rifiutato(self):
        verdict = gate_slot("def f():\n    return hallucinated_api()\n")
        self.assertFalse(verdict.ok)
        self.assertIn("hallucinated_api", verdict.detail())
        self.assertEqual(len(verdict.undefined), 1)

    def test_refs_rendono_lecito_il_nome(self):
        refs = ["QTimer.singleShot(ms, slot)  # firma PyQt6",
                "class QWidget: ..."]
        verdict = gate_slot(
            "def arm(self, ms):\n"
            "    QTimer.singleShot(ms, self.close)\n",
            refs=refs, kind="method")
        self.assertTrue(verdict.ok, verdict.detail())

    def test_self_implicito_nei_metodi(self):
        verdict = gate_slot(
            "def closeEvent(self, event):\n    self.hide()\n",
            refs=["def hide(self): ..."], kind="method")
        self.assertTrue(verdict.ok, verdict.detail())

    def test_sintassi_invalida(self):
        verdict = gate_slot("def broken(:\n    pass\n")
        self.assertFalse(verdict.ok)
        self.assertTrue(verdict.syntax)
        self.assertIn("sintassi", verdict.summary())

    def test_frammento_vuoto(self):
        verdict = gate_slot("   \n")
        self.assertFalse(verdict.ok)
        self.assertIn("vuoto", verdict.detail())

    def test_kind_sconosciuto(self):
        with self.assertRaises(ValueError):
            gate_slot("x = 1\n", kind="boh")

    def test_names_from_refs(self):
        names = names_from_refs([
            "import os\nclass Widget:\n    pass\n",
            "QPushButton('ok')  # prosa",
        ])
        self.assertIn("os", names)
        self.assertIn("Widget", names)
        self.assertIn("QPushButton", names)


class TestSlotAssembler(unittest.TestCase):
    TEMPLATE = textwrap.dedent('''\
        """Template demo."""
        import os
        # @@imports
        # @@slot: greet
        # @@slot: main
        ''')

    SLOTS = [
        {"anchor": "greet",
         "code": "def greet(name):\n    return f'hi {name}'\n"},
        {"anchor": "main",
         "code": ("from pathlib import Path\n\n"
                  "def main():\n"
                  "    print(greet(Path('.').name), os.getcwd())\n")},
    ]

    def test_assembla_e_compila(self):
        out = assemble_slots(self.TEMPLATE, self.SLOTS)
        compile(out, "<assembled>", "exec")
        self.assertNotIn("@@slot", out)
        self.assertIn("def greet(name)", out)
        self.assertIn("from pathlib import Path", out)
        # import sollevato fuori dallo slot (a livello modulo, una volta)
        self.assertEqual(out.count("from pathlib import Path"), 1)
        self.assertLess(out.index("from pathlib import Path"),
                        out.index("def greet"))

    def test_import_duplicati_deduppati(self):
        # due slot importano lo stesso simbolo
        base = textwrap.dedent('''\
            # @@imports
            # @@slot: a
            # @@slot: b
            ''')
        out = assemble_slots(base, [
            {"anchor": "a", "code": "import json\nx = 1\n"},
            {"anchor": "b", "code": "import json\ny = 2\n"},
        ])
        self.assertEqual(out.count("import json"), 1)
        self.assertIn("x = 1", out)
        self.assertIn("y = 2", out)

    def test_anchor_mancante(self):
        with self.assertRaises(AssemblerError) as ctx:
            assemble_slots(self.TEMPLATE, [
                {"anchor": "nope", "code": "x = 1\n"}])
        self.assertIn("nope", str(ctx.exception))

    def test_slot_duplicato(self):
        with self.assertRaises(AssemblerError):
            assemble_slots(self.TEMPLATE, [
                {"anchor": "greet", "code": "x = 1\n"},
                {"anchor": "greet", "code": "y = 2\n"},
            ])

    def test_slot_non_fornito_mantiene_marker(self):
        out = assemble_slots(self.TEMPLATE, [self.SLOTS[0]])
        self.assertIn("# @@slot: main", out)

    def test_indentazione_dentro_classe(self):
        base = textwrap.dedent('''\
            class A:
                # @@slot: run
            ''')
        out = assemble_slots(base, [{
            "anchor": "run",
            "code": "def run(self):\n    return 1\n"}])
        self.assertIn("    def run(self):\n        return 1", out)
        compile(out, "<assembled>", "exec")

    def test_import_senza_marker(self):
        base = textwrap.dedent('''\
            \"\"\"doc\"\"\"
            import os
            # @@slot: f
            ''')
        out = assemble_slots(base, [{
            "anchor": "f",
            "code": "from pathlib import Path\n\ndef f():\n    return Path('.')\n",
        }])
        self.assertIn("from pathlib import Path", out)
        self.assertLess(out.index("import os"),
                        out.index("from pathlib import Path"))
        compile(out, "<assembled>", "exec")

    def test_slot_con_sintassi_invalida(self):
        with self.assertRaises(AssemblerError):
            assemble_slots(self.TEMPLATE, [
                {"anchor": "greet", "code": "def x(:\n    pass\n"}])

    def test_scheletro_invalido(self):
        with self.assertRaises(AssemblerError):
            assemble_slots("def broken(:\n# @@slot: a\n", [
                {"anchor": "a", "code": "x = 1\n"}])

    def test_future_import_rifiutato(self):
        with self.assertRaises(AssemblerError):
            assemble_slots(self.TEMPLATE, [{
                "anchor": "greet",
                "code": "from __future__ import annotations\nx = 1\n"}])

    def test_anchor_duplicato_nello_scheletro(self):
        base = "# @@slot: a\n# @@slot: a\n"
        with self.assertRaises(AssemblerError):
            assemble_slots(base, [{"anchor": "a", "code": "x = 1\n"}])

    def test_slot_anchors(self):
        self.assertEqual(slot_anchors(self.TEMPLATE), ["greet", "main"])

    def test_assemble_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "template.py"
            base.write_text(self.TEMPLATE, encoding="utf-8")
            out = Path(tmp) / "out.py"
            written = assemble_to_file(base, self.SLOTS, out)
            self.assertEqual(written, out)
            compile(out.read_text(encoding="utf-8"), str(out), "exec")
            # il template originale non viene toccato
            self.assertIn("@@slot", base.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
