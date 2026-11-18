"""Test Robustezza #5 — rotazione log (RotatingFileHandler 10MB×5)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.orchestrator import setup_logger  # noqa: E402
import logging.handlers  # noqa: E402


class TestLogRotation(unittest.TestCase):
    def test_handlers_are_rotating(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "paths": {"logs_dir": tmp},
                "logging": {"level": "INFO", "file": str(Path(tmp) / "x.log"),
                            "jsonl": str(Path(tmp) / "x.jsonl")},
            }
            logger = setup_logger(cfg)
            rotating = [h for h in logger.handlers
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
            self.assertEqual(len(rotating), 2)
            for h in rotating:
                self.assertEqual(h.maxBytes, 10 * 1024 * 1024)
                self.assertEqual(h.backupCount, 5)


if __name__ == "__main__":
    unittest.main()
