"""
tests/test_dotfile_security.py — test di sicurezza sui dotfile ("dot").

Il tema: i file nascosti (`.ssh`, `.git`, `.gnupg`, `.aws`, `.config`,
`.env`, `.bashrc`, `id_rsa`, ...) sono il bersaglio classico di esfiltration
e persistenza. Verifica che:

  1. `safe_project_path` blocchi LETTURA e SCRITTURA su ogni parte/dotfile
     sensibile, anche annidati, con prefisso `project/`, con varianti di
     maiuscole (`.SSH`) e via traversing `..`;
  2. i percorsi dotfile legittimi (`.gitignore`, file nascosti generici)
     restino consentiti (nessun over-blocking);
  3. i symlink non permettano di aggirare il confine né scrivere su un
     dotfile reale fuori da `project/`;
  4. `validate_bash_command` blocchi i comandi che toccano dotfile sensibili
     (cat, grep, ...) e permetta quelli innocui;
  5. `is_sensitive_path` esponga lo stesso verdetto del gate dei tool.

Eseguibile senza root (usa una project root temporanea):

    python -m unittest tests.test_dotfile_security -v
    python tests/test_dotfile_security.py       # report leggibile
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Log di sicurezza dei test in una directory temporanea.
os.environ.setdefault(
    "BYTE_SWARM_SECURITY_LOG_DIR", tempfile.mkdtemp(prefix="bswarm-dot-")
)

from SAFETY import security  # noqa: E402
from SAFETY.security import (  # noqa: E402
    SecurityError,
    is_sensitive_path,
    safe_project_path,
    validate_bash_command,
)

_SECRET_PATHS = (
    # directory sensibili (SENSITIVE_PARTS), dirette e annidate
    "project/.ssh/authorized_keys",
    ".ssh/id_rsa",
    "sub/repo/.git/config",
    ".gnupg/pubring.kbx",
    ".aws/credentials",
    "nested/.config/ollama/config.toml",
    "project/project/.ssh/known_hosts",   # doppio prefisso non foola nulla
    # dotfile sensibili (SENSITIVE_NAMES), incluse varianti di casing
    "project/.env",
    ".env.local",
    ".env.production",
    ".git-credentials",
    ".netrc",
    ".bashrc",
    ".bash_profile",
    ".profile",
    ".zshrc",
    "keys/id_rsa",
    "keys/id_ed25519.pub",
    "config/credentials.json",
    "config/secrets.json",
    "config/secrets.yaml",
    "ssh/authorized_keys",
    # varianti di maiuscole/minuscole: il matching deve essere case-fold
    "project/.SSH/authorized_keys",
    ".SSH/id_rsa",
    ".Git/config",
    ".ENV.local",
    ".Bashrc",
    "keys/ID_RSA",
    "Config/SECRETS.json",
)

_SAFE_DOT_PATHS = (
    # dotfile legit: il blocco non deve essere generico su tutto ciò che
    # inizia col punto
    ".gitignore",
    "src/.keep",
    ".hidden.txt",
    "project/.editorconfig",
)


def _assert_blocked(test: unittest.TestCase, path: str,
                    root: Path, mode: str = "both") -> None:
    """Il path DEVE sollevare SecurityError, in lettura e/o scrittura."""
    if mode in ("both", "read"):
        with test.assertRaises(SecurityError, msg=f"read: {path}"):
            safe_project_path(path, root)
    if mode in ("both", "write"):
        with test.assertRaises(SecurityError, msg=f"write: {path}"):
            safe_project_path(path, root, for_write=True)


# ---------------------------------------------------------------------------
# 1. Dotfile sensibili sotto `safe_project_path`
# ---------------------------------------------------------------------------
class TestSensitiveDotPaths(unittest.TestCase):

    def setUp(self) -> None:
        # progetti con interni già visitati: `.ssh/`, `.git/` ecc. esistono
        # davvero (come succederebbe nella home reale\modules)
        self.root = Path(tempfile.mkdtemp(prefix="bswarm-proj-"))
        (self.root / "sub" / "repo").mkdir(parents=True)
        (self.root / "nested").mkdir()
        (self.root / "keys").mkdir()
        (self.root / "config").mkdir()
        (self.root / "ssh").mkdir()
        (self.root / ".ssh").mkdir()
        (self.root / ".git").mkdir()
        (self.root / ".gitignore").write_text("*.tmp\n", encoding="utf-8")

    def test_secret_dot_paths_blocked_for_read(self):
        for p in _SECRET_PATHS:
            _assert_blocked(self, p, self.root, mode="read")

    def test_secret_dot_paths_blocked_for_write(self):
        for p in _SECRET_PATHS:
            _assert_blocked(self, p, self.root, mode="write")

    def test_legit_dot_paths_still_allowed(self):
        """Nessun over-blocking: dotfile innocui devono passare."""
        for p in _SAFE_DOT_PATHS:
            full = safe_project_path(p, self.root)
            self.assertTrue(full.is_relative_to(self.root.resolve()),
                            msg=f"fuori dalla root: {p}")

    def test_write_on_legit_dotfile_accepted(self):
        full = safe_project_path(".gitignore", self.root, for_write=True)
        self.assertEqual(full, self.root.resolve() / ".gitignore")


# ---------------------------------------------------------------------------
# 2. Traversing verso dotfile reali fuori dal sandbox
# ---------------------------------------------------------------------------
class TestDotfileTraversal(unittest.TestCase):

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="bswarm-trv-"))
        (self.root / "work").mkdir()

    def test_traversal_to_real_dotfiles_blocked(self):
        """`..` verso fora è bloccato comunque; verso `.ssh` soprattutto."""
        blocked = (
            "../.ssh/authorized_keys",      # la .ssh reale di un utente
            "work/../../.bashrc",
            "work/../.env",
            "./../.aws/credentials",
        )
        for p in blocked:
            _assert_blocked(self, p, self.root)

    def test_read_of_symlinked_project_shadow(self):
        # un symlink dentro al progetto verso la .ssh reale
        real_ssh = Path(tempfile.mkdtemp(prefix="bswarm-ssh-"))
        shadow = self.root / "work" / "dot_link"
        shadow.symlink_to(real_ssh, target_is_directory=True)
        with self.assertRaises(SecurityError):
            safe_project_path("work/dot_link/id_rsa", self.root)

    def test_tilde_and_absolute_are_not_dotfile_but_still_blocked(self):
        for p in ("~/.ssh/id_rsa", "/home/user/.bashrc",
                  "~/.env", "/root/.aws/credentials"):
            _assert_blocked(self, p, self.root)


# ---------------------------------------------------------------------------
# 3. Symlink come vettore di bypass (scrittura)
# ---------------------------------------------------------------------------
class TestDotfileSymlinkWrite(unittest.TestCase):

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="bswarm-sym-"))
        (self.root / "real.txt").write_text("ok\n", encoding="utf-8")

    def test_write_on_symlink_to_outside_blocked(self):
        link = self.root / "leak"
        link.symlink_to(Path("/etc/passwd"))
        with self.assertRaises(SecurityError):
            safe_project_path("leak", self.root, for_write=True)

    def test_write_on_symlink_to_inside_blocked_too(self):
        """Anche un symlink QUASI legittimo: la regola è zero-symlink
        in scrittura, senza eccezioni (nessun TOCTOU)."""
        link = self.root / "alias"
        link.symlink_to(self.root / "real.txt")
        with self.assertRaises(SecurityError):
            safe_project_path("alias", self.root, for_write=True)

    def test_read_through_internal_symlink_within_root_ok(self):
        (self.root / "data").mkdir()
        link = self.root / "alias"
        link.symlink_to(self.root / "data", target_is_directory=True)
        full = safe_project_path("alias/note.txt", self.root)
        self.assertTrue(full.is_relative_to(self.root.resolve()))

    def test_read_symlink_to_outside_blocked(self):
        link = self.root / "etc_passwd"
        link.symlink_to("/etc/passwd")
        with self.assertRaises(SecurityError):
            safe_project_path("etc_passwd", self.root)


# ---------------------------------------------------------------------------
# 4. Exfiltration via comandi bash
# ---------------------------------------------------------------------------
class TestBashDotfileExfiltration(unittest.TestCase):

    def setUp(self) -> None:
        # NB: la root passata al validatore È già la directory "project/";
        # i path "project/x" dei comandi vengono normalizzati a "x".
        self.root = Path(tempfile.mkdtemp(prefix="bswarm-cmd-"))
        (self.root / "src").mkdir()
        (self.root / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        (self.root / "README.md").write_text("doc\n", encoding="utf-8")
        (self.root / "script.py").write_text("print()\n", encoding="utf-8")
        (self.root / "main.c").write_text("int main(void){return 0;}\n",
                                          encoding="utf-8")

    def test_dotfile_reading_commands_blocked(self):
        blocked = (
            "cat project/.env",
            "cat .env",
            "cat project/.ssh/id_rsa",
            "less project/.env.local",
            "grep -r candidate project/.gnupg",
            "ls project/.aws",
            "head project/.netrc",
            "tail project/customs/.git-credentials",
        )
        for cmd in blocked:
            ok, reason = validate_bash_command(cmd, self.root)
            self.assertFalse(ok, msg=f"comando non bloccato: {cmd!r}")

    def test_dotfile_casing_in_commands_blocked(self):
        for cmd in ("cat project/.ENV", "cat project/.SSH/id_rsa",
                    "cat project/Keys/ID_RSA"):
            ok, reason = validate_bash_command(cmd, self.root)
            self.assertFalse(ok, msg=f"casing bypass non bloccato: {cmd!r}")

    def test_traversing_dotfile_commands_blocked(self):
        for cmd in ("cat ../.bashrc", "cat ~/.ssh/id_rsa",
                    "grep -r token ../.env"):
            ok, reason = validate_bash_command(cmd, self.root)
            self.assertFalse(ok, msg=f"traversal non bloccato: {cmd!r}")

    def test_innocuous_commands_still_allowed(self):
        allowed = (
            "cat project/.gitignore",
            "cat project/README.md",
            "grep -r pattern project/src",
            "ls project",
            "python3 project/script.py",
            "gcc project/main.c -o project/main",
        )
        for cmd in allowed:
            ok, reason = validate_bash_command(cmd, self.root)
            self.assertTrue(ok, msg=f"falso positivo su: {cmd!r} ({reason})")


# ---------------------------------------------------------------------------
# 5. API pubblica coerente (`is_sensitive_path`)
# ---------------------------------------------------------------------------
class TestIsSensitivePath(unittest.TestCase):

    def test_sensitive_true(self):
        for p in (".ssh", "/home/u/.aws/credentials", "secrets.json",
                  ".netrc", "a/.git/config", ".SSH", ".BASHRC", "ID_RSA"):
            self.assertTrue(is_sensitive_path(p), msg=f"sensibile: {p}")

    def test_innocuous_false(self):
        for p in (".gitignore", "notes.txt", "src/main.py", ".hidden.txt",
                  "a/b/c.py"):
            self.assertFalse(is_sensitive_path(p), msg=f"innocuo: {p}")

    def test_malformed_input_fails_closed(self):
        self.assertTrue(is_sensitive_path(None))  # fail-closed


if __name__ == "__main__":
    print("Dotfile security check → SAFETY/security.py")
    print("=" * 60)
    unittest.main(verbosity=2)
