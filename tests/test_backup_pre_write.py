"""Test Robustezza #2 — snapshot pre-write nel ToolSet (backup deterministico)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.tools import ToolSet  # noqa: E402


def _make_tools(tmp: Path):
    project = tmp / "project"
    project.mkdir()
    (tmp / "state").mkdir()
    (tmp / "backups").mkdir()
    cfg = {
        "paths": {
            "project_root": str(project),
            "state_dir": str(tmp / "state"),
            "backups_dir": str(tmp / "backups"),
        },
        "routing": {"max_file_size_readable": 50_000, "timeout_bash": 2},
        "security": {
            "enabled": True,
            "max_output_chars": 500,
            "max_file_size_write": 10_000,
            "max_file_size_bytes": 1_000_000,
            "max_memory_mb": 512,
        },
        "backup": {"retention_sessions": 2},
    }
    logger = __import__("logging").getLogger(f"test-backup-{id(tmp)}")
    logger.addHandler(__import__("logging").NullHandler())
    tools = ToolSet(cfg, logger)
    tools.set_worker("test-worker")
    return tools, project


class TestBackupPreWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-backup-"))
        self.tools, self.project = _make_tools(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_snapshot_su_file_esistente(self):
        (self.project / "a.py").write_text("ORIGINALE\n", encoding="utf-8")
        snap = self.tools.snapshot_before_write("a.py")
        self.assertTrue(snap)
        self.assertTrue(Path(snap).exists())
        self.assertEqual(Path(snap).read_text(), "ORIGINALE\n")

    def test_snapshot_su_file_inesistente(self):
        snap = self.tools.snapshot_before_write("nope.py")
        self.assertEqual(snap, "")

    def test_write_file_crea_backup(self):
        (self.project / "b.py").write_text("VECCHIO\n", encoding="utf-8")
        res = self.tools.write_file("b.py", "NUOVO\n")
        self.assertTrue(res.startswith("OK:"))
        # il file è stato sovrascritto
        self.assertEqual((self.project / "b.py").read_text(), "NUOVO\n")
        # esiste un backup con il contenuto vecchio
        backups = list((self.tmp / "backups").rglob("b.py"))
        self.assertTrue(backups)
        self.assertEqual(backups[0].read_text(), "VECCHIO\n")

    def test_patch_code_crea_backup(self):
        (self.project / "c.py").write_text("x = 1\n", encoding="utf-8")
        res = self.tools.patch_code("c.py", "x = 1", "x = 2")
        self.assertTrue(res.startswith("OK:"))
        self.assertEqual((self.project / "c.py").read_text(), "x = 2\n")
        backups = list((self.tmp / "backups").rglob("c.py"))
        self.assertTrue(backups)
        self.assertEqual(backups[0].read_text(), "x = 1\n")

    def test_restore_roundtrip(self):
        (self.project / "d.py").write_text("ORIGINALE\n", encoding="utf-8")
        self.tools.write_file("d.py", "SOVRASCRITTO\n")
        self.assertEqual((self.project / "d.py").read_text(), "SOVRASCRITTO\n")
        res = self.tools.restore_from_backup("d.py")
        self.assertTrue(res.startswith("OK:"))
        self.assertEqual((self.project / "d.py").read_text(), "ORIGINALE\n")

    def test_restore_sessione_inesistente(self):
        res = self.tools.restore_from_backup("nope.py", session_ts=999999)
        self.assertTrue(res.startswith("ERROR:"))

    def test_retention_prune(self):
        # crea 3 sessioni (retention=2) scrivendo su file diversi
        for i in range(3):
            (self.project / f"f{i}.py").write_text(f"v{i}\n", encoding="utf-8")
            self.tools._backup_session_ts = 1000 + i
            self.tools.snapshot_before_write(f"f{i}.py")
        sessions = sorted((self.tmp / "backups").glob("prewrite-*"))
        self.assertLessEqual(len(sessions), 2)

    def test_nuovo_file_no_backup(self):
        res = self.tools.write_file("nuovo.py", "nuovo\n")
        self.assertTrue(res.startswith("OK:"))
        # nessun backup per file nuovo
        backups = list((self.tmp / "backups").rglob("nuovo.py"))
        self.assertEqual(backups, [])


if __name__ == "__main__":
    unittest.main()
