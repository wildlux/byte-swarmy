"""Test per il gate anti-escape (todo 9c/M1) in CORE/tools.py."""
import logging
import os
import tempfile
import unittest
from pathlib import Path

from CORE.tools import ToolSet


def make_tools(root: Path):
    cfg = {
        "paths": {"project_root": str(root)},
        "security": {},
        "routing": {"timeout_bash": 10, "max_file_size_readable": 100000},
    }
    log = logging.Logger("t")
    log.addHandler(logging.NullHandler())
    return ToolSet(cfg, log)


class ArtifactGateTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="bswarm-gate-"))
        (self.base / "project").mkdir()
        self.tools = make_tools(self.base / "project")

    def test_write_file_accepts_clean_text(self):
        r = self.tools.write_file("notes.txt", "riga un\nriga due\n")
        self.assertFalse(r.startswith("ERROR"), r)
        self.assertTrue((self.base / "project" / "notes.txt").exists())

    def test_write_file_rejects_escape_artifacts(self):
        corrupted = 'def f():\n    return "ok"' + "\n\\\"\\n\\\"\\n"
        r = self.tools.write_file("notes2.txt", corrupted)
        self.assertTrue(r.startswith("ERROR"), r)
        self.assertIn("artefatti", r)
        # il file NON deve esistere
        self.assertFalse((self.base / "project" / "notes2.txt").exists())

    def test_patch_rejects_corrupted_new_text(self):
        tools = self.tools
        tools.write_file("lib.py", "def f():\n    return 1\n")
        artifact = "return 2  # ok"
        corrupted_new = artifact + "\n\\\" stray"
        r = tools.patch_code("lib.py", "return 1", corrupted_new)
        self.assertTrue(r.startswith("ERROR"), r)
        self.assertIn("artefatti", r)
        # il file originale resta integro
        content = (self.base / "project" / "lib.py").read_text()
        self.assertIn("return 1", content)


if __name__ == "__main__":
    unittest.main()
