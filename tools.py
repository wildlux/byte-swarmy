"""
tools.py — ToolSet class

Tool minimi per agenti autonomi. Stato = file su disco.

Sicurezza (vedi security.py):
- `run_bash` NON usa una shell: il comando viene tokenizzato e validato
  contro un'allowlist, poi eseguito con `shell=False` nella project root.
- Ogni path dei tool è confinato in `project/` (niente path assoluti, `..`, `~`).
- `HOME` dei sottoprocessi è una directory sandbox: `~/.ssh` è irraggiungibile.
- `git push`/`git pull`/`git remote add|remove` sono disabilitati per i worker.
- Limiti per processo: CPU, dimensione file, core dump, memoria.
- Ogni blocco viene registrato in `logs/security.log`.
"""

from __future__ import annotations

import os
import re
import resource
import shlex
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from security import (
    SecurityError,
    allowed_commands_text,
    log_security_event,
    normalize_bash_argv,
    safe_project_path,
    validate_bash_command,
)

# Branch che i worker non possono cancellare.
PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "trunk"})

# Nome branch/ref valido.
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,79}$")
_GLOB_RE = re.compile(r"^[A-Za-z0-9_./*?\[\]-]{1,120}$")

# File che non devono mai finire nell'output di grep/search.
GREP_EXCLUDES = (
    "--exclude=.env",
    "--exclude=.env.*",
    "--exclude=*.pem",
    "--exclude=*.key",
    "--exclude=*.p12",
    "--exclude=id_rsa",
    "--exclude=id_rsa.*",
    "--exclude=id_ed25519",
    "--exclude=id_ed25519.*",
    "--exclude=.git-credentials",
    "--exclude=.netrc",
    "--exclude-dir=.git",
    "--exclude-dir=.ssh",
    "--exclude-dir=.gnupg",
)

TRUNCATED = "\n...[output troncato]...\n"


class ToolSet:
    """Set di tool minimi per agenti autonomi. Stato = file su disco."""

    def __init__(self, config, logger):
        self.cfg = config
        self.log = logger
        self.project_root = Path(config["paths"]["project_root"]).resolve()
        state_dir = Path(config["paths"].get("state_dir", "./state"))
        self.tmp_dir = state_dir / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        # HOME finta: impedisce di raggiungere ~/.ssh, ~/.git-credentials, ecc.
        self.sandbox_home = state_dir / "sandbox-home"
        self.sandbox_home.mkdir(parents=True, exist_ok=True)
        self.worker = "worker"

        sec = config.get("security", {})
        self.max_output = int(sec.get("max_output_chars", 10_000))
        self.max_write_bytes = int(sec.get("max_file_size_write", 2_000_000))
        self.max_file_limit = int(sec.get("max_file_size_bytes", 50_000_000))
        self.max_memory_mb = int(sec.get("max_memory_mb", 1536))

        # REGOLA 0 — la difesa è sempre attiva.
        # `security.enabled` esiste solo per retrocompatibilità: qualunque
        # tentativo di disattivarlo (config, test, task injection) viene
        # ignorato e registrato. La policy non è delegata al LLM.
        flag = sec.get("enabled", True)
        if flag is False or str(flag).strip().lower() in {"0", "false", "no", "off"}:
            log_security_event(
                "security_disable_attempt",
                'config="[security] enabled=false" action="ignored"',
                "CRITICAL",
            )

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def set_worker(self, worker: str) -> None:
        """Imposta l'id usato nei log di sicurezza (single-thread)."""
        self.worker = worker or "worker"

    def allowed_tools(self) -> set[str]:
        """Tool che il worker può realmente chiamare."""
        return {
            "read_file", "write_file", "run_bash", "search",
            "git_commit", "git_diff", "git_status", "git_log",
            "git_branch", "git_merge", "git_pull", "git_push", "git_remote",
        }

    # ----- 1. read_file -----
    def read_file(self, path: str) -> str:
        """Legge un file dal progetto. Rifiuta path fuori/sensibili e file grandi."""
        try:
            full = safe_project_path(path, self.project_root)
        except SecurityError as exc:
            self._audit("blocked_path", f'op=read path="{self._q(path)}" reason="{exc}"',
                        "WARNING")
            return f"ERROR: {exc}. Puoi leggere solo file dentro project/."

        if not full.exists():
            return f"ERROR: file not found: {path}"
        if full.is_dir():
            return f"ERROR: '{path}' è una directory. Usa run_bash('ls {path}')."
        size = full.stat().st_size
        if size > self.cfg["routing"]["max_file_size_readable"]:
            return f"ERROR: file troppo grande ({size} byte). Leggilo a pezzi con head/tail."
        try:
            return full.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"ERROR reading {path}: {e}"

    # ----- 2. write_file (transazionale: tmp nella stessa dir, poi rename) -----
    def write_file(self, path: str, content: str) -> str:
        """Scrive in modo atomico dentro project/. Rifiuta path non sicuri."""
        if not isinstance(content, str):
            content = str(content)
        if len(content) > self.max_write_bytes:
            return (f"ERROR: contenuto troppo grande ({len(content)} byte, "
                    f"max {self.max_write_bytes}). Scrivi file più piccoli.")
        try:
            full = safe_project_path(path, self.project_root, for_write=True)
        except SecurityError as exc:
            self._audit("blocked_path", f'op=write path="{self._q(path)}" reason="{exc}"',
                        "WARNING")
            return (f"ERROR: {exc}. Scrivi solo dentro project/ "
                    f"(es. 'project/main.py').")

        if full.exists() and full.is_dir():
            return f"ERROR: '{path}' è una directory."

        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            tmp = full.parent / f".{full.name}.{os.getpid()}.tmp"
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, full)
            self.log.debug(f"wrote {len(content)} bytes -> {path}")
            return f"OK: wrote {len(content)} bytes to {path}"
        except Exception as e:
            try:
                tmp.unlink(missing_ok=True)  # type: ignore[possibly-undefined]
            except Exception:
                pass
            return f"ERROR writing {path}: {e}"

    # ----- 3. run_bash (senza shell) -----
    def run_bash(self, cmd: str) -> str:
        """Esegue UN comando semplice nella project root, senza shell.

        Non sono supportati pipe, redirect, `&&`, backtick, `$(...)`.
        Timeout = routing.timeout_bash. Output limitato per non saturare il LLM.
        """
        if not isinstance(cmd, str) or not cmd.strip():
            return "ERROR: comando vuoto"

        ok, reason = validate_bash_command(cmd, self.project_root)
        if not ok:
            self._audit(
                "blocked_command",
                f'cmd="{self._q(cmd)}" reason="{self._q(reason)}"',
                "CRITICAL",
            )
            return (
                f"ERROR: comando bloccato: {reason}.\n"
                f"{allowed_commands_text()}\n"
                "Suggerimento: usa i tool dedicati (write_file, git_commit, search) "
                "oppure un singolo comando semplice dentro project/."
            )

        self._audit("allowed_command", f'cmd="{self._q(cmd)}"', "INFO")

        try:
            argv = shlex.split(cmd, posix=True)
        except ValueError as exc:
            return f"ERROR: comando non valido: {exc}"
        if not argv:
            return "ERROR: comando vuoto"

        # `cd` non ha senso: ogni comando parte già da project/.
        if argv[0] == "cd":
            return f"OK: la working directory è già {self.project_root}"

        # Accetta sia 'project/x' sia 'x' (la cwd è già project/).
        argv = normalize_bash_argv(argv)

        # grep ricorsivo: escludi sempre file sensibili (difesa anti-leak).
        # Le esclusioni vanno DOPO eventuali --include, altrimenti GNU grep
        # lascia vincere l'ultima regola (--include '*') e il file passa.
        if argv[0] == "grep":
            sep = argv.index("--") if "--" in argv else len(argv)
            argv = [*argv[:sep], *GREP_EXCLUDES, *argv[sep:]]

        timeout = int(self.cfg["routing"]["timeout_bash"])
        return self._run(argv, timeout=timeout, cwd=self.project_root)

    # ----- 4. git_commit -----
    def git_commit(self, message: str) -> str:
        """Snapshot transazionale. Aggiunge tutto e committa."""
        if not isinstance(message, str):
            message = str(message)
        message = " ".join(message.split())[:500] or "auto"
        try:
            self._run(["git", "add", "-A"], timeout=15, cwd=self.project_root)
            r = self._run(
                ["git", "commit", "-m", message, "--allow-empty"],
                timeout=15, cwd=self.project_root,
            )
            if "exit_code=0" in r:
                return "OK: committed"
            if "nothing to commit" in r or "no changes" in r:
                return "OK: nothing to commit"
            return f"git commit fallito:\n{r[:1000]}"
        except Exception as e:
            return f"ERROR git_commit: {e}"

    # ----- 5. git_diff -----
    def git_diff(self, rev: str = "HEAD~1") -> str:
        """Mostra il diff rispetto a una revisione locale."""
        rev = self._safe_ref(rev)
        if rev is None:
            return ("ERROR: revisione non valida. Usa HEAD, HEAD~1, un hash "
                    "o un nome di branch locale.")
        try:
            r = self._run(["git", "diff", rev], timeout=20, cwd=self.project_root)
            return r if r.strip() else "(no diff)"
        except Exception as e:
            return f"ERROR git_diff: {e}"

    # ----- 6. search (grep ricorsivo) -----
    def search(self, pattern: str, file_glob: str = "*") -> str:
        """Cerca pattern regex nei file del progetto."""
        if not isinstance(pattern, str) or not pattern:
            return "ERROR: pattern mancante"
        if len(pattern) > 500:
            return "ERROR: pattern troppo lungo (max 500)"
        if not isinstance(file_glob, str):
            file_glob = "*"
        if not _GLOB_RE.match(file_glob) or ".." in Path(file_glob).parts:
            return "ERROR: file_glob non valido"
        try:
            cmd = [
                "grep", "-rn", "-E",
                "--include", file_glob,
                *GREP_EXCLUDES,
                "--", pattern, ".",
            ]
            r = self._run(cmd, timeout=20, cwd=self.project_root)
            if "exit_code=1" in r and "stdout" in r:
                return "(no matches)"
            return r if r.strip() else "(no matches)"
        except Exception as e:
            return f"ERROR search: {e}"

    # ----- 7. git_status -----
    def git_status(self) -> str:
        """Stato del repo: file modificati/non tracciati."""
        try:
            r = self._run(["git", "status", "--porcelain"],
                          timeout=10, cwd=self.project_root)
            return r
        except Exception as e:
            return f"ERROR git_status: {e}"

    # ----- 8. git_log -----
    def git_log(self, n: int = 10) -> str:
        """Ultimi N commit del repo (1-50)."""
        try:
            n = max(1, min(50, int(n)))
        except (TypeError, ValueError):
            n = 10
        try:
            r = self._run(["git", "log", f"--max-count={n}", "--oneline"],
                          timeout=10, cwd=self.project_root)
            return r or "(no commits)"
        except Exception as e:
            return f"ERROR git_log: {e}"

    # ----- 9. git_branch -----
    def git_branch(self, action: str = "list", name: str = "") -> str:
        """Gestione branch: list | create | switch | delete (locale)."""
        action = str(action).lower().strip()
        try:
            if action == "list":
                return self._run(["git", "branch", "-a"],
                                 timeout=10, cwd=self.project_root)
            if action not in ("create", "switch", "delete"):
                return f"ERROR: azione '{action}' non valida (list|create|switch|delete)"

            if self._safe_ref(name) is None:
                return "ERROR: nome branch non valido"

            if action == "delete":
                if name in PROTECTED_BRANCHES:
                    self._audit("blocked_branch_delete",
                                f'branch="{name}" reason="protected"', "WARNING")
                    return f"ERROR: il branch protetto '{name}' non può essere cancellato."

            cmd = {
                "create": ["git", "checkout", "-b", name],
                "switch": ["git", "checkout", name],
                "delete": ["git", "branch", "-D", name],
            }[action]
            r = self._run(cmd, timeout=10, cwd=self.project_root)
            if "exit_code=0" in r:
                verb = {"create": "created", "switch": "switched to",
                        "delete": "deleted"}[action]
                return f"OK: {verb} {name}"
            return r
        except Exception as e:
            return f"ERROR git_branch: {e}"

    # ----- 10. git_merge -----
    def git_merge(self, branch: str) -> str:
        """Merge di un branch locale nel branch corrente."""
        if self._safe_ref(branch) is None:
            return "ERROR: nome branch non valido"
        try:
            r = self._run(
                ["git", "merge", "--no-ff", branch, "-m", f"Merge branch '{branch}'"],
                timeout=30, cwd=self.project_root,
            )
            if "exit_code=0" in r:
                return f"OK: merged {branch}"
            return f"ERROR merge {branch}:\n{r[:1500]}"
        except Exception as e:
            return f"ERROR git_merge: {e}"

    # ----- 11. git_pull (DISABILITATO) -----
    def git_pull(self, remote: str = "origin", branch: str = "") -> str:
        """DISABILITATO: i worker non parlano con il remote."""
        return self._disabled("git_pull")

    # ----- 12. git_push (DISABILITATO) -----
    def git_push(self, remote: str = "origin", branch: str = "") -> str:
        """DISABILITATO: i worker non pushano su GitHub."""
        return self._disabled("git_push")

    # ----- 13. git_remote (solo list) -----
    def git_remote(self, action: str = "list", name: str = "", url: str = "") -> str:
        """Gestione remote: solo `list` è consentito ai worker."""
        action = str(action).lower().strip()
        if action != "list":
            return self._disabled(f"git_remote({action})")
        try:
            return self._run(["git", "remote", "-v"],
                             timeout=10, cwd=self.project_root) or "(no remotes)"
        except Exception as e:
            return f"ERROR git_remote: {e}"

    # ----- utility -----
    def _resolve(self, path: str) -> Path:
        """Compatibilità: risolve un path confinandolo in project_root."""
        return safe_project_path(path, self.project_root)

    def list_tools(self) -> dict:
        """Firma dei tool per il system prompt dell'agente."""
        return {
            "read_file": "read_file(path) -> str: legge un file dentro project/",
            "write_file": "write_file(path, content) -> str: scrive atomicamente in project/",
            "run_bash": "run_bash(cmd) -> str: UN comando semplice, senza pipe/redirect",
            "git_commit": "git_commit(message) -> str: snapshot git locale",
            "git_diff": "git_diff(rev='HEAD~1') -> str: diff locale",
            "search": "search(pattern, file_glob='*') -> str: grep ricorsivo nel progetto",
            "git_status": "git_status() -> str: stato repo (modificati/non tracciati)",
            "git_log": "git_log(n=10) -> str: ultimi N commit",
            "git_branch": "git_branch(action='list|create|switch|delete', name='') -> str",
            "git_merge": "git_merge(branch) -> str: merge --no-ff branch locale",
            "git_pull": "DISABILITATO per i worker (usa ./sync.sh come utente reale)",
            "git_push": "DISABILITATO per i worker (usa ./sync.sh come utente reale)",
            "git_remote": "git_remote(action='list') -> str (add/remove disabilitati)",
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _audit(self, event_type: str, details: str, severity: str) -> None:
        log_security_event(event_type, details, severity, worker=self.worker)

    @staticmethod
    def _q(value) -> str:
        """Rende un valore sicuro da mettere in una riga di log."""
        return str(value).replace("\n", "\\n").replace("\r", "\\r")[:300]

    def _disabled(self, tool: str) -> str:
        self._audit("blocked_tool", f'tool={tool} reason="disabled for workers"',
                    "WARNING")
        return (
            f"ERROR: {tool} è disabilitato per i worker (sicurezza).\n"
            "Il remote git si gestisce a mano come utente reale: ./sync.sh "
            "oppure ./sync.sh --pull."
        )

    def _safe_ref(self, ref) -> Optional[str]:
        """Valida un ref git locale (niente flag, niente spazi)."""
        if not isinstance(ref, str):
            return None
        ref = ref.strip()
        if not ref or len(ref) > 80 or ref.startswith("-") or " " in ref:
            return None
        if ".." in ref:
            return None
        # HEAD, HEAD~3, HEAD@{1}, hash, branch locale.
        if re.match(r"^HEAD(~\d+|@\{[^}]{1,40}\})?$", ref):
            return ref
        if re.fullmatch(r"[0-9a-fA-F]{4,40}", ref):
            return ref
        if not _REF_RE.match(ref):
            return None
        return ref

    def _safe_env(self) -> dict:
        """Ambiente minimo per i sottoprocessi: niente token/credenziali."""
        bin_dir = str(Path(sys.executable).parent)
        return {
            "PATH": f"{bin_dir}:/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.sandbox_home),
            "TMPDIR": str(self.tmp_dir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TERM": "dumb",
            "PAGER": "cat",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/true",
            "SSH_ASKPASS": "/bin/true",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }

    def _preexec(self, timeout: int):
        """Limiti per processo (Linux/Unix)."""
        max_mem = self.max_memory_mb * 1024 * 1024
        max_file = self.max_file_limit

        def _limit() -> None:  # eseguito nel figlio prima di exec
            try:
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            except (ValueError, OSError):
                pass
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 2))
            except (ValueError, OSError):
                pass
            try:
                resource.setrlimit(resource.RLIMIT_FSIZE, (max_file, max_file))
            except (ValueError, OSError):
                pass
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            except (ValueError, OSError):
                pass
            try:
                resource.setrlimit(resource.RLIMIT_AS, (max_mem, max_mem))
            except (ValueError, OSError):
                pass

        return _limit

    def _run(self, argv: Sequence[str], timeout: int,
             cwd: Optional[Path] = None) -> str:
        """Esegue argv senza shell, con process group e limiti di risorsa."""
        try:
            proc = subprocess.Popen(
                list(argv),
                cwd=str(cwd or self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._safe_env(),
                start_new_session=True,
                preexec_fn=self._preexec(timeout),
            )
        except FileNotFoundError:
            return f"ERROR: comando non trovato: {argv[0]}"
        except Exception as e:
            return f"ERROR: impossibile eseguire {argv[0]}: {e}"

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except Exception:
                stdout, stderr = "", ""
            self._audit("resource_limit", f'limit=timeout value={timeout}s',
                        "WARNING")
            return f"ERROR: timeout dopo {timeout}s (processo terminato)"

        stdout = self._truncate(stdout or "")
        stderr = self._truncate(stderr or "")
        return (
            f"exit_code={proc.returncode}\n"
            f"--- stdout ---\n{stdout}\n"
            f"--- stderr ---\n{stderr}"
        )

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_output:
            return text
        half = self.max_output // 2
        return text[:half] + TRUNCATED + text[-half:]
