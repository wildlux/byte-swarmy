"""
tests/test_sandbox.py — verifica del sandbox bubblewrap.

I test che eseguono processi sono saltati (SKIP) se bubblewrap non è
disponibile, ma il test "fail closed" verifica che in quel caso i tool
rifiutino comunque di eseguire comandi sull'host.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BYTE_SWARM_SECURITY_LOG_DIR",
                      tempfile.mkdtemp(prefix="bswarm-sbx-"))

from CORE import sandbox  # noqa: E402
from CORE.tools import ToolSet  # noqa: E402

PROJECT = ROOT / "project"

BWRAP_OK = sandbox.is_available()
NO_BWRAP = "bubblewrap non disponibile o user namespace disabilitati"

EXPECTED_CHECKS = {
    "sandbox.workspace",
    "sandbox.project_write",
    "sandbox.host_home_hidden",
    "sandbox.outside_write_blocked",
    "sandbox.network_blocked",
    "sandbox.etc_minimized",
    "sandbox.host_pid_hidden",
    "sandbox.sensitive_env_absent",
    "sandbox.capabilities_dropped",
    "sandbox.nested_userns_blocked",
    "sandbox.process_isolation",
}


def _run_in_sandbox(argv, project_root: Path, timeout: int = 30):
    cmd, env = sandbox.build_command(argv, project_root)
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )


class TestSandboxBackend(unittest.TestCase):
    """Configurazione del comando bwrap e sua disponibilità."""

    def test_backend_info_is_complete(self):
        info = sandbox.backend_info()
        self.assertEqual(info["backend"], "bubblewrap")
        self.assertIn("available", info)
        self.assertIn("error", info)
        if not info["available"]:
            self.skipTest(f"{NO_BWRAP}: {info['error']}")
        self.assertTrue(info["version"], info)

    def test_command_has_required_isolation_flags(self):
        if not BWRAP_OK:
            self.skipTest(NO_BWRAP)
        cmd, env = sandbox.build_command(["true"], PROJECT)
        joined = " ".join(cmd)
        required = [
            "--unshare-all",
            "--unshare-user",
            "--cap-drop ALL",
            "--die-with-parent",
            "--clearenv",
            "--remount-ro /opt",
        ]
        if sandbox.supports_disable_userns():
            required.append("--disable-userns")
        for flag in required:
            with self.subTest(flag=flag):
                self.assertIn(flag, joined)
        self.assertEqual(env["HOME"], sandbox.SANDBOX_HOME)
        self.assertEqual(env["TMPDIR"], "/tmp")
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("SSH_AUTH_SOCK", env)

    def test_workdir_outside_project_is_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="bswarm-workdir-"))
        project = tmp / "project"
        sub = project / "sub"
        sub.mkdir(parents=True)
        with self.assertRaises(sandbox.SandboxError):
            sandbox.sandbox_workdir("/etc", project)
        with self.assertRaises(sandbox.SandboxError):
            sandbox.sandbox_workdir(tmp, project)
        self.assertEqual(sandbox.sandbox_workdir(project, project),
                         sandbox.WORKSPACE)
        self.assertEqual(sandbox.sandbox_workdir(sub, project),
                         f"{sandbox.WORKSPACE}/sub")

    def test_missing_project_root_is_rejected(self):
        missing = Path(tempfile.mkdtemp(prefix="bswarm-missing-")) / "nope"
        with self.assertRaises(sandbox.SandboxError):
            sandbox.build_command(["true"], missing)

    def test_empty_command_is_rejected(self):
        with self.assertRaises(sandbox.SandboxError):
            sandbox.build_command([], PROJECT)


class TestSandboxSelfTest(unittest.TestCase):
    """Esecuzione reale del self-test dentro il sandbox."""

    @unittest.skipUnless(BWRAP_OK, NO_BWRAP)
    def test_all_isolation_checks_pass(self):
        result = sandbox.run_selftest(PROJECT, timeout=60)
        self.assertTrue(result["ok"], result.get("error") or result)
        self.assertTrue(result["available"])
        names = {c["name"] for c in result["checks"]}
        self.assertEqual(names, EXPECTED_CHECKS)
        statuses = {c["name"]: c["status"] for c in result["checks"]}
        for name, status in statuses.items():
            with self.subTest(check=name):
                if name == "sandbox.nested_userns_blocked" and \
                        not sandbox.supports_disable_userns():
                    self.assertEqual(status, "SKIP", f"{name}: {status}")
                else:
                    self.assertEqual(status, "PASS", f"{name}: {status}")

    @unittest.skipUnless(BWRAP_OK, NO_BWRAP)
    def test_writes_persist_only_in_project(self):
        marker = PROJECT / ".pytest-sandbox-write.tmp"
        marker.unlink(missing_ok=True)
        script = (
            "from pathlib import Path\n"
            "Path('/workspace/.pytest-sandbox-write.tmp').write_text('ok')\n"
            "print('written')\n"
        )
        proc = _run_in_sandbox(
            [sandbox.python_executable(), "-c", script], PROJECT
        )
        try:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("written", proc.stdout)
            self.assertTrue(marker.exists())
            self.assertEqual(marker.read_text(), "ok")
        finally:
            marker.unlink(missing_ok=True)
        # Nessun file di escape deve comparire accanto al progetto.
        self.assertFalse((PROJECT.parent / ".pytest-sandbox-write.tmp").exists())

    @unittest.skipUnless(BWRAP_OK, NO_BWRAP)
    def test_network_is_not_available(self):
        script = (
            "import socket\n"
            "s = socket.socket()\n"
            "s.settimeout(1)\n"
            "raise SystemExit(0 if s.connect_ex(('1.1.1.1', 80)) else 3)\n"
        )
        proc = _run_in_sandbox(
            [sandbox.python_executable(), "-c", script], PROJECT
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestToolsetFailClosed(unittest.TestCase):
    """I tool non devono mai eseguire nulla se il sandbox non è disponibile."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-failclosed-"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.cfg = {
            "paths": {
                "project_root": str(self.project),
                "state_dir": str(self.tmp / "state"),
            },
            "routing": {
                "max_file_size_readable": 50_000,
                "timeout_bash": 5,
            },
            "security": {
                "enabled": True,
                "max_output_chars": 2_000,
                "max_file_size_write": 10_000,
                "max_file_size_bytes": 1_000_000,
                "max_memory_mb": 512,
            },
        }
        logger = logging.getLogger(f"sandbox-failclosed-{id(self)}")
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        self.tools = ToolSet(self.cfg, logger)

    def test_run_bash_does_not_execute_without_bwrap(self):
        marker = self.project / "executed.marker"
        self.tools.write_file(
            "boom.py",
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('x')\n",
        )

        saved = (sandbox._available, sandbox._probe_error, sandbox.BWRAP)
        try:
            sandbox._available = False
            sandbox._probe_error = "bwrap disattivato per test"
            sandbox.BWRAP = ""
            out = self.tools.run_bash("python boom.py")
        finally:
            sandbox._available, sandbox._probe_error, sandbox.BWRAP = saved

        self.assertIn("sandbox non disponibile", out.lower())
        self.assertIn("fail closed", out.lower())
        self.assertFalse(marker.exists(), "il comando è stato eseguito sull'host")

    def test_missing_bwrap_returns_instructive_error(self):
        saved = (sandbox._available, sandbox._probe_error)
        try:
            sandbox._available = False
            sandbox._probe_error = "bwrap non installato"
            out = self.tools.git_status()
        finally:
            sandbox._available, sandbox._probe_error = saved
        self.assertIn("sudo apt install bubblewrap", out)
        self.assertNotIn("fatal:", out)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
