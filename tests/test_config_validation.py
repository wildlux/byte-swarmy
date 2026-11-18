"""Test Robustezza #3 — validazione fail-fast della config (CORE/orchestrator)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.orchestrator import (  # noqa: E402
    ConfigError,
    load_config,
    validate_config,
)

VALID = {
    "paths": {
        "project_root": "./project",
        "state_dir": "./state",
        "tasks_dir": "./tasks",
        "logs_dir": "./logs",
        "backups_dir": "./backups",
    },
    "orchestrator": {
        "max_task_retries": 3,
        "retry_cooldown_sec": 30,
        "sticky_models": True,
        "best_of_n": 1,
    },
    "security": {
        "max_output_chars": 1000,
        "max_file_size_write": 1000,
        "max_file_size_bytes": 1000,
        "max_memory_mb": 512,
    },
    "routing": {
        "max_file_size_readable": 1000,
        "timeout_bash": 5,
    },
    "logging": {"level": "INFO"},
}


class TestValidateConfig(unittest.TestCase):
    def test_valida_ok(self):
        self.assertEqual(validate_config(VALID), [])

    def test_sezione_mancante(self):
        cfg = dict(VALID)
        del cfg["paths"]
        errs = validate_config(cfg)
        self.assertTrue(any("paths" in e for e in errs))

    def test_tipo_errato(self):
        cfg = dict(VALID)
        cfg["orchestrator"] = dict(VALID["orchestrator"])
        cfg["orchestrator"]["max_task_retries"] = "tre"
        errs = validate_config(cfg)
        self.assertTrue(any("max_task_retries" in e for e in errs))

    def test_range_errato(self):
        cfg = dict(VALID)
        cfg["orchestrator"] = dict(VALID["orchestrator"])
        cfg["orchestrator"]["max_task_retries"] = 0
        errs = validate_config(cfg)
        self.assertTrue(any(">=" in e for e in errs))

    def test_bool_come_int_rifiutato(self):
        cfg = dict(VALID)
        cfg["orchestrator"] = dict(VALID["orchestrator"])
        cfg["orchestrator"]["sticky_models"] = 1
        errs = validate_config(cfg)
        self.assertTrue(any("sticky_models" in e for e in errs))

    def test_fail_fast_load_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.toml"
            p.write_text("[paths]\nproject_root = 42\n", encoding="utf-8")
            with self.assertRaises(ConfigError) as ctx:
                load_config(str(p))
            self.assertTrue(ctx.exception.errors)

    def test_load_config_valida(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ok.toml"
            # minimal valid-ish config (paths + orchestrator + security + routing + logging)
            real = (ROOT / "CONFIG" / "config.toml").read_text()
            p.write_text(real, encoding="utf-8")
            cfg = load_config(str(p))
            self.assertIsInstance(cfg, dict)


if __name__ == "__main__":
    unittest.main()
