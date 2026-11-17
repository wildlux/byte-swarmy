"""Test Cycle 79 — Gate di sicurezza del ToolSet (file protetti + shrink).

Regressione sul danno Cycle 76: il worker ha sovrascritto requirements.txt
(203 righe -> 9 byte) perché la gate precedente non copriva i file di
infrastruttura. Questi test bloccano la regressione.
"""

import logging
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from CORE.tools import ToolSet, PROTECTED_FILES  # noqa: E402


def _make_tools(tmp: Path):
    project = tmp / "project"
    project.mkdir()
    (tmp / "state").mkdir()
    cfg = {
        "paths": {
            "project_root": str(project),
            "state_dir": str(tmp / "state"),
        },
        "routing": {
            "max_file_size_readable": 50_000,
            "timeout_bash": 2,
        },
        "security": {
            "enabled": True,
            "max_output_chars": 500,
            "max_file_size_write": 10_000,
            "max_file_size_bytes": 1_000_000,
            "max_memory_mb": 512,
        },
    }
    logger = logging.getLogger(f"test-gates-{id(tmp)}")
    logger.addHandler(logging.NullHandler())
    tools = ToolSet(cfg, logger)
    tools.set_worker("test-worker")
    return tools, project


class TestProtectedFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-gates-"))
        self.tools, self.project = _make_tools(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_file_su_file_protetto_esistente_bloccato(self):
        """requirements.txt esistente: write_file deve essere bloccato."""
        (self.project / "requirements.txt").write_text(
            "numpy==1.0\n" * 50, encoding="utf-8")
        res = self.tools.write_file("requirements.txt", "junk")
        self.assertTrue(res.startswith("ERROR"))
        self.assertIn("protetto", res.lower())
        # file intatto
        self.assertEqual(
            (self.project / "requirements.txt").read_text().count("numpy"), 50)

    def test_write_file_su_file_protetto_inesistente_consentito(self):
        """Creare un nuovo requirements.txt (progetto fresco) è legittimo."""
        res = self.tools.write_file("requirements.txt", "numpy==1.0\n")
        self.assertTrue(res.startswith("OK:"))

    def test_delete_file_su_file_protetto_bloccato(self):
        (self.project / "requirements.txt").write_text("x\n", encoding="utf-8")
        res = self.tools.delete_file("requirements.txt")
        self.assertTrue(res.startswith("ERROR"))
        self.assertTrue((self.project / "requirements.txt").exists())

    def test_patch_code_su_file_protetto_consentito(self):
        """patch_code è il percorso sicuro (edit mirato)."""
        (self.project / "requirements.txt").write_text(
            "numpy==1.0\n", encoding="utf-8")
        res = self.tools.patch_code("requirements.txt", "numpy==1.0",
                                    "numpy==2.0")
        self.assertTrue(res.startswith("OK:"))
        self.assertIn("numpy==2.0",
                      (self.project / "requirements.txt").read_text())

    def test_move_file_verso_file_protetto_bloccato(self):
        (self.project / "src.txt").write_text("x\n", encoding="utf-8")
        (self.project / "requirements.txt").write_text("y\n", encoding="utf-8")
        res = self.tools.move_file("src.txt", "requirements.txt")
        self.assertTrue(res.startswith("ERROR"))
        # destinazione intatta
        self.assertEqual((self.project / "requirements.txt").read_text(), "y\n")

    def test_protected_files_contiene_infrastruttura_critica(self):
        for name in ("requirements.txt", ".gitignore", "config.toml",
                     "pyproject.toml", "makefile"):
            self.assertIn(name, PROTECTED_FILES,
                          "%s deve essere protetto" % name)


class TestSuspiciousShrink(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-shrink-"))
        self.tools, self.project = _make_tools(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_shrink_sospetto_bloccato(self):
        """File grande (>=500 byte) -> contenuto <20%: bloccato."""
        big = "x" * 1000 + "\n"
        (self.project / "data.py").write_text(big, encoding="utf-8")
        res = self.tools.write_file("data.py", "y\n")
        self.assertTrue(res.startswith("ERROR"))
        self.assertIn("shrink", res.lower())
        # file intatto
        self.assertEqual((self.project / "data.py").read_text(), big)

    def test_shrink_legittimo_consentito(self):
        """Riduzione moderata (<80%) è consentita."""
        (self.project / "data.py").write_text("x" * 600 + "\n",
                                               encoding="utf-8")
        res = self.tools.write_file("data.py", "x" * 400 + "\n")
        self.assertTrue(res.startswith("OK:"))

    def test_file_piccolo_nessun_blocco_shrink(self):
        """File <500 byte: nessuna guardia shrink (troppo rumore)."""
        (self.project / "small.py").write_text("x" * 100, encoding="utf-8")
        res = self.tools.write_file("small.py", "y\n")
        self.assertTrue(res.startswith("OK:"))

    def test_file_nuovo_nessun_blocco_shrink(self):
        """File che non esiste: nessuna guardia shrink."""
        res = self.tools.write_file("brandnew.py", "y\n")
        self.assertTrue(res.startswith("OK:"))


class TestBasicGates(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-basic-"))
        self.tools, self.project = _make_tools(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_path_traversal_bloccato(self):
        res = self.tools.write_file("../escape.py", "x\n")
        self.assertTrue(res.startswith("ERROR"))

    def test_ast_scanner_blocca_codice_pericoloso(self):
        res = self.tools.write_file("evil.py", "import os\nos.system('id')\n")
        self.assertTrue(res.startswith("ERROR"))
        self.assertIn("Security Violation", res)

    def test_write_file_normale_consentito(self):
        res = self.tools.write_file("ok.py", "print('hi')\n")
        self.assertTrue(res.startswith("OK:"))
        self.assertEqual((self.project / "ok.py").read_text(),
                         "print('hi')\n")

    def test_read_file_path_traversal_bloccato(self):
        res = self.tools.read_file("../etc/passwd")
        self.assertTrue(res.startswith("ERROR"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
