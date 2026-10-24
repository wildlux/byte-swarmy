"""
tools.py — ToolSet class
I 6 tool minimi che ogni agente può usare. Tutto via filesystem + subprocess.
Niente DB, niente IPC, niente servizi esterni.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class ToolSet:
    """Set di tool minimi per agenti autonomi. Stato = file su disco."""

    def __init__(self, config, logger):
        self.cfg = config
        self.log = logger
        self.project_root = Path(config["paths"]["project_root"])
        self.tmp_dir = Path("./state/tmp")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    # ----- 1. read_file -----
    def read_file(self, path: str) -> str:
        """Legge un file dal progetto. Rifiuta file > max_file_size_readable."""
        full = self._resolve(path)
        if not full.exists():
            return f"ERROR: file not found: {path}"
        size = full.stat().st_size
        if size > self.cfg["routing"]["max_file_size_readable"]:
            return f"ERROR: file too large ({size} bytes). Read in chunks."
        try:
            return full.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"ERROR reading {path}: {e}"

    # ----- 2. write_file (transazionale: tmp prima, poi mv) -----
    def write_file(self, path: str, content: str) -> str:
        """Scrive in tmp/ poi sposta con rename atomico."""
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.tmp_dir / f"{full.name}.{os.getpid()}.tmp"
        try:
            tmp.write_text(content, encoding="utf-8")
            shutil.move(str(tmp), str(full))
            self.log.debug(f"wrote {len(content)} bytes -> {path}")
            return f"OK: wrote {len(content)} bytes to {path}"
        except Exception as e:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return f"ERROR writing {path}: {e}"

    # ----- 3. run_bash -----
    def run_bash(self, cmd: str) -> str:
        """Esegue un comando bash nella project_root.
        Timeout massimo = routing.timeout_bash.
        Output limitato a 10k char per non saturare il contesto LLM."""
        timeout = self.cfg["routing"]["timeout_bash"]
        try:
            result = subprocess.run(
                ["bash", "-c", cmd],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            if len(stdout) > 10000:
                stdout = stdout[:5000] + "\n...[truncated]...\n" + stdout[-5000:]
            return f"exit_code={result.returncode}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
        except subprocess.TimeoutExpired:
            return f"ERROR: timeout after {timeout}s"
        except Exception as e:
            return f"ERROR running bash: {e}"

    # ----- 4. git_commit -----
    def git_commit(self, message: str) -> str:
        """Snapshot transazionale. Aggiunge tutto e committa."""
        try:
            subprocess.run(["git", "add", "-A"],
                          cwd=str(self.project_root),
                          capture_output=True, timeout=15)
            r = subprocess.run(
                ["git", "commit", "-m", message, "--allow-empty"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                return f"OK: committed"
            # nothing to commit = ok
            if "nothing to commit" in r.stdout or "no changes" in r.stdout:
                return "OK: nothing to commit"
            return f"git exit={r.returncode}: {r.stderr.strip()}"
        except Exception as e:
            return f"ERROR git_commit: {e}"

    # ----- 5. git_diff -----
    def git_diff(self, rev: str = "HEAD~1") -> str:
        """Mostra il diff rispetto a una revisione."""
        try:
            r = subprocess.run(
                ["git", "diff", rev],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=20,
            )
            out = r.stdout or ""
            if len(out) > 10000:
                out = out[:5000] + "\n...[truncated]...\n" + out[-5000:]
            return out if out else "(no diff)"
        except Exception as e:
            return f"ERROR git_diff: {e}"

    # ----- 6. search (grep ricorsivo) -----
    def search(self, pattern: str, file_glob: str = "*") -> str:
        """Cerca pattern regex nei file del progetto."""
        try:
            cmd = ["grep", "-rn", "-E", "--include", file_glob, pattern, "."]
            r = subprocess.run(
                cmd, cwd=str(self.project_root),
                capture_output=True, text=True, timeout=20,
            )
            out = r.stdout or ""
            if len(out) > 10000:
                out = out[:5000] + "\n...[truncated]...\n" + out[-5000:]
            return out if out else "(no matches)"
        except Exception as e:
            return f"ERROR search: {e}"

    # ----- 7. git_status -----
    def git_status(self) -> str:
        """Stato del repo: file modificati/non tracciati."""
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=10,
            )
            out = r.stdout or ""
            if not out.strip():
                return "OK: working tree clean"
            return out
        except Exception as e:
            return f"ERROR git_status: {e}"

    # ----- 8. git_log -----
    def git_log(self, n: int = 10) -> str:
        """Ultimi N commit del repo."""
        try:
            r = subprocess.run(
                ["git", "log", f"--max-count={int(n)}", "--oneline"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout or "(no commits)"
        except Exception as e:
            return f"ERROR git_log: {e}"

    # ----- 9. git_branch -----
    def git_branch(self, action: str = "list", name: str = "") -> str:
        """Gestione branch: list | create | switch | delete."""
        action = action.lower()
        try:
            if action == "list":
                r = subprocess.run(
                    ["git", "branch", "-a"],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=10,
                )
                return r.stdout or "(no branches)"
            elif action == "create" and name:
                r = subprocess.run(
                    ["git", "checkout", "-b", name],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=10,
                )
                return f"OK: created branch {name}" if r.returncode == 0 \
                    else f"ERROR: {r.stderr.strip()}"
            elif action == "switch" and name:
                r = subprocess.run(
                    ["git", "checkout", name],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=10,
                )
                return f"OK: switched to {name}" if r.returncode == 0 \
                    else f"ERROR: {r.stderr.strip()}"
            elif action == "delete" and name:
                r = subprocess.run(
                    ["git", "branch", "-D", name],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=10,
                )
                return f"OK: deleted {name}" if r.returncode == 0 \
                    else f"ERROR: {r.stderr.strip()}"
            else:
                return f"ERROR: invalid action '{action}' or missing name"
        except Exception as e:
            return f"ERROR git_branch: {e}"

    # ----- 10. git_merge -----
    def git_merge(self, branch: str) -> str:
        """Merge di un branch nel branch corrente."""
        try:
            r = subprocess.run(
                ["git", "merge", "--no-ff", branch, "-m", f"Merge branch '{branch}'"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return f"OK: merged {branch}"
            return f"ERROR merge {branch} (exit {r.returncode}):\n{r.stdout}\n{r.stderr}"
        except Exception as e:
            return f"ERROR git_merge: {e}"

    # ----- 11. git_pull -----
    def git_pull(self, remote: str = "origin", branch: str = "") -> str:
        """Pull dal remote."""
        try:
            cmd = ["git", "pull", remote]
            if branch:
                cmd.append(branch)
            r = subprocess.run(
                cmd, cwd=str(self.project_root),
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                return f"OK: pulled from {remote}" + (f" {branch}" if branch else "")
            return f"ERROR pull (exit {r.returncode}):\n{r.stderr.strip()}"
        except Exception as e:
            return f"ERROR git_pull: {e}"

    # ----- 12. git_push -----
    def git_push(self, remote: str = "origin", branch: str = "") -> str:
        """Push verso il remote."""
        try:
            cmd = ["git", "push", remote]
            if branch:
                cmd.append(branch)
            r = subprocess.run(
                cmd, cwd=str(self.project_root),
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                return f"OK: pushed to {remote}" + (f" {branch}" if branch else "")
            return f"ERROR push (exit {r.returncode}):\n{r.stderr.strip()}"
        except Exception as e:
            return f"ERROR git_push: {e}"

    # ----- 13. git_remote -----
    def git_remote(self, action: str = "list", name: str = "", url: str = "") -> str:
        """Gestione remote: list | add | remove."""
        action = action.lower()
        try:
            if action == "list":
                r = subprocess.run(
                    ["git", "remote", "-v"],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=10,
                )
                return r.stdout or "(no remotes)"
            elif action == "add" and name and url:
                r = subprocess.run(
                    ["git", "remote", "add", name, url],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=10,
                )
                return f"OK: added remote {name}" if r.returncode == 0 \
                    else f"ERROR: {r.stderr.strip()}"
            elif action == "remove" and name:
                r = subprocess.run(
                    ["git", "remote", "remove", name],
                    cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=10,
                )
                return f"OK: removed remote {name}" if r.returncode == 0 \
                    else f"ERROR: {r.stderr.strip()}"
            else:
                return f"ERROR: invalid action '{action}'"
        except Exception as e:
            return f"ERROR git_remote: {e}"

    # ----- utility -----
    def _resolve(self, path: str) -> Path:
        """Risolve path relativo al project_root. Blocca path traversal."""
        p = Path(path)
        if p.is_absolute():
            return p
        full = (self.project_root / p).resolve()
        # security check: non uscire dal project_root
        try:
            full.relative_to(self.project_root.resolve())
        except ValueError:
            raise ValueError(f"path outside project_root: {path}")
        return full

    def list_tools(self) -> dict:
        """Restituisce la firma dei tool, per il system prompt dell'agente."""
        return {
            "read_file": "read_file(path) -> str: legge un file dal progetto",
            "write_file": "write_file(path, content) -> str: scrive atomicamente",
            "run_bash": "run_bash(cmd) -> str: esegue comando bash (timeout 30s)",
            "git_commit": "git_commit(message) -> str: snapshot git",
            "git_diff": "git_diff(rev='HEAD~1') -> str: mostra diff",
            "search": "search(pattern, file_glob='*') -> str: grep ricorsivo",
            # Tool Git avanzati
            "git_status": "git_status() -> str: stato repo (modificati/non tracciati)",
            "git_log": "git_log(n=10) -> str: ultimi N commit",
            "git_branch": "git_branch(action='list|create|switch|delete', name='') -> str",
            "git_merge": "git_merge(branch) -> str: merge --no-ff branch nel corrente",
            "git_pull": "git_pull(remote='origin', branch='') -> str",
            "git_push": "git_push(remote='origin', branch='') -> str",
            "git_remote": "git_remote(action='list|add|remove', name='', url='') -> str",
        }
