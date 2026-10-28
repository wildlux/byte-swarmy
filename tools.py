"""
tools.py — ToolSet class

Tool minimi per agenti autonomi. Stato = file su disco.

Sicurezza (vedi security.py e sandbox.py):
- `run_bash` NON usa una shell: il comando viene tokenizzato e validato
  contro un'allowlist, poi eseguito con `shell=False` nella project root.
- Ogni sottoprocesso (comandi, git, grep) gira dentro bubblewrap: filesystem
  minimo, niente rete, niente home reale, PID/user/IPC namespace separati.
- Se bubblewrap non è disponibile il comando NON viene eseguito (fail closed).
- Ogni path dei tool è confinato in `project/` (niente path assoluti, `..`, `~`).
- `HOME` dei sottoprocessi è una directory volatile: `~/.ssh` è irraggiungibile.
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
from pathlib import Path
from typing import Optional, Sequence

import sandbox

from security import (
    SecurityError,
    allowed_commands_text,
    log_security_event,
    normalize_bash_argv,
    safe_project_path,
    validate_bash_command,
)
from ast_scanner import scanner as ast_scanner


# Branch che i worker non possono cancellare.
PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "trunk"})

# Nome branch/ref valido. Supporta ~, ^, @ per riferimenti git.
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/~^@-]{0,79}$")
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
        self.worker = "worker"

        sec = config.get("security", {})
        self.max_output = int(sec.get("max_output_chars", 10_000))
        self.max_write_bytes = int(sec.get("max_file_size_write", 2_000_000))
        self.max_file_limit = int(sec.get("max_file_size_bytes", 50_000_000))
        self.max_memory_mb = int(sec.get("max_memory_mb", 1536))
        # M7: limita il disco consumato da project/ (saturazione in pochi
        # secondi con dd/yes non e visibile dal check periodico ogni 30s).
        self.max_project_mb = int(sec.get("project_disk_limit_mb", 2048))

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
            "read_file", "write_file", "patch_code", "run_bash", "search",
            "analyze_project", "find_references", "lint_code",
            "rename_symbol", "analyze_complexity", "get_call_graph",
            "extract_method",
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
        """Scrive in modo atomico dentro project/. Rifiuta path non sicuri.
        Inoltre, l'AST Scanner blocca l'esecuzione di codice pericoloso.
        """
        if not isinstance(content, str):
            content = str(content)
        
        # DETERMINISTIC SECURITY CHECK (AST)
        # Prima di scrivere, analizziamo se il contenuto è codice Python
        # e se contiene chiamate vietate.
        if path.endswith(".py"):
            safe, reason = ast_scanner.scan(content)
            if not safe:
                self._audit("blocked_ast", f'path="{self._q(path)}" reason="{self._q(reason)}"', 
                            "CRITICAL")
                return f"ERROR: Security Violation. Il codice contiene elementi vietati: {reason}."

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
            # Per evitare che git diff restituisca un errore se non ci sono commit,
            # o se il ref è valido ma non c'è diff, gestiamo l'output.
            r = self._run(["git", "diff", rev], timeout=20, cwd=self.project_root)
            
            # Se l'output contiene 'exit_code=0' ma è vuoto, significa che non c'è diff.
            # Se contiene un errore di git, lo restituiamo.
            if "exit_code=0" in r:
                stdout = r.split("--- stdout ---")[1].split("--- stderr ---")[0].strip()
                return stdout if stdout else "(no diff)"
            
            return r
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
            "patch_code": "patch_code(path, old_text, new_text) -> str: sostituisce una porzione di testo in un file",
            "analyze_project": "analyze_project() -> str: restituisce la mappa di classi e funzioni del progetto",
            "find_references": "find_references(symbol) -> str: cerca tutte le occorrenze di una funzione/variabile",
            "run_test_suite": "run_test_suite() -> str: esegue i test e restituisce il report degli errori",
            "lint_code": "lint_code(path) -> str: verifica errori di sintassi e stile in un file",
            "rename_symbol": "rename_symbol(old, new) -> str: rinomina un simbolo in tutto il progetto",
            "analyze_complexity": "analyze_complexity(path) -> str: stima la complessità di un file",
            "get_call_graph": "get_call_graph(symbol) -> str: mappa chi chiama la funzione/classe",
            "extract_method": "extract_method(path, old_block, name, body) -> str: estrae un blocco in una nuova funzione",
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

    # ----- 19. rename_symbol -----
    def rename_symbol(self, old_symbol: str, new_symbol: str) -> str:
        """Rinomina un simbolo in tutto il progetto.
        
        Cerca l'occorrenza esatta del simbolo e la sostituisce in tutti i file .py.
        Usa regex per evitare di sostituire parti di altre parole.
        """
        try:
            files = sorted(self.project_root.glob("**/*.py"))
            count = 0
            pattern = rf"\b{re.escape(old_symbol)}\b"
            
            for f in files:
                content = f.read_text(encoding="utf-8", errors="replace")
                if re.search(pattern, content):
                    new_content = re.sub(pattern, new_symbol, content)
                    # Scrittura transazionale
                    tmp = f.parent / f".{f.name}.rename.{os.getpid()}.tmp"
                    tmp.write_text(new_content, encoding="utf-8")
                    os.replace(tmp, f)
                    count += 1
            
            return f"OK: simbolo '{old_symbol}' rinominato in '{new_symbol}' in {count} file."
        except Exception as e:
            return f"ERROR renaming symbol: {e}"

    # ----- 20. analyze_complexity -----
    def analyze_complexity(self, path: str) -> str:
        """Calcola una stima della complessità ciclotomatica di un file.
        
        Conta i punti di decisione (if, for, while, except, with, and, or).
        """
        try:
            full = safe_project_path(path, self.project_root)
            if not full.exists():
                return f"ERROR: file non trovato: {path}"
            
            content = full.read_text(encoding="utf-8", errors="replace")
            # Punti di decisione tipici in Python
            decision_points = [
                r"\bif\b", r"\belif\b", r"\bfor\b", r"\bwhile\b", 
                r"\bexcept\b", r"\bwith\b", r"\band\b", r"\bor\b"
            ]
            
            total_complexity = 0
            details = []
            for line in content.splitlines():
                line_complexity = 0
                for p in decision_points:
                    line_complexity += len(re.findall(p, line))
                if line_complexity > 0:
                    total_complexity += line_complexity
                    details.append(f"L{content.splitlines().index(line)+1}: {line.strip()[:50]}...")
            
            return f"Complessità stimata: {total_complexity}\n" + \
                   ("\n".join(details[:10]) if details else "Codice lineare, bassa complessità.")
        except Exception as e:
            return f"ERROR analyzing complexity: {e}"

    # ----- 21. get_call_graph -----
    def get_call_graph(self, symbol: str) -> str:
        """Mappa chi chiama la funzione/classe specificata.
        
        Cerca nel progetto tutte le chiamate al simbolo fornito.
        """
        # In questo caso, find_references è già l'implementazione di base
        # ma lo specializziamo per mostrare chiaramente la relazione "chi chiama"
        return self.find_references(symbol)

    # ----- 22. extract_method -----
    def extract_method(self, path: str, old_block: str, new_method_name: str, new_method_body: str) -> str:
        """Sposta un blocco di codice in una nuova funzione e aggiorna la chiamata.
        
        Sostituisce `old_block` con la chiamata `new_method_name()` e aggiunge 
        la definizione di `new_method_body` alla fine del file o prima della funzione corrente.
        """
        try:
            full = safe_project_path(path, self.project_root)
            if not full.exists():
                return f"ERROR: file non trovato: {path}"
            
            content = full.read_text(encoding="utf-8", errors="replace")
            if old_block not in content:
                return "ERROR: blocco di codice non trovato nel file."
            
            # 1. Sostituisci il blocco con la chiamata
            new_content = content.replace(old_block, f"{new_method_name}()")
            
            # 2. Aggiungi la definizione della nuova funzione alla fine del file
            # (In un'implementazione avanzata, cercheremmo il posto giusto per evitarne l'ombra)
            new_content += f"\n\ndef {new_method_name}():\n    {new_method_body}\n"
            
            if len(new_content) > self.max_write_bytes:
                return "ERROR: file risultante troppo grande."
            
            tmp = full.parent / f".{full.name}.extract.{os.getpid()}.tmp"
            tmp.write_text(new_content, encoding="utf-8")
            os.replace(tmp, full)
            
            return f"OK: estratto '{new_method_name}' in {path}"
        except Exception as e:
            return f"ERROR extracting method: {e}"

    # ----- 15. analyze_project -----
    def analyze_project(self) -> str:
        """Genera una mappa strutturale del progetto (classi e funzioni).
        
        Scansiona i file .py in project/ e usa regex per identificare le definizioni.
        """
        results = []
        try:
            files = sorted(self.project_root.glob("**/*.py"))
            for f in files:
                rel_path = f.relative_to(self.project_root)
                content = f.read_text(encoding="utf-8", errors="replace")
                
                # Regex per classi e funzioni
                classes = re.findall(r"^class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", content, re.MULTILINE)
                funcs = re.findall(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", content, re.MULTILINE)
                
                if classes or funcs:
                    entry = f"File: {rel_path}\n"
                    if classes: entry += f"  Classes: {', '.join(classes)}\n"
                    if funcs: entry += f"  Functions: {', '.join(funcs)}\n"
                    results.append(entry)
            
            if not results:
                return "Nessuna classe o funzione trovata nel progetto."
            return "\n".join(results)
        except Exception as e:
            return f"ERROR analyzing project: {e}"

    # ----- 16. find_references -----
    def find_references(self, symbol: str) -> str:
        """Cerca tutte le occorrenze di un simbolo (funzione/variabile) nel progetto.
        
        Ritorna i file e le righe in cui il simbolo compare.
        """
        try:
            matches = []
            # Cerchiamo il simbolo come parola intera
            pattern = rf"\b{re.escape(symbol)}\b"
            files = sorted(self.project_root.glob("**/*.py"))
            for f in files:
                rel_path = f.relative_to(self.project_root)
                content = f.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    if re.search(pattern, line):
                        matches.append(f"{rel_path}:{i} -> {line.strip()}")
            
            if not matches:
                return f"Nessuna occorrenza di '{symbol}' trovata."
            return "\n".join(matches)
        except Exception as e:
            return f"ERROR finding references: {e}"

    # ----- 17. run_test_suite -----
    def run_test_suite(self) -> str:
        """Esegue la suite di test in sandbox e restituisce un report semplificato.
        
        Cerca i test in tests/ e usa pytest o unittest.
        """
        try:
            # Usiamo il runner JSON creato per la GUI per avere output strutturato
            runner_path = BASE_DIR / "tests" / "run_tests.py"
            if not runner_path.exists():
                return "ERROR: runner di test non trovato in tests/run_tests.py"
            
            # Esecuzione in sandbox
            cmd, env = sandbox.build_command(
                [sys.executable, str(runner_path), "--json"],
                self.project_root,
            )
            
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                start_new_session=True,
                preexec_fn=self._preexec(60),
            )
            stdout, stderr = proc.communicate()
            
            if proc.returncode != 0 and not stdout:
                return f"ERROR executing tests: {stderr}"
            
            # Parsing del report JSON
            raw = stdout.strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                return f"ERROR: report test non valido\n{stdout[:500]}"
            
            data = json.loads(raw[start:end+1])
            summary = data.get("summary", {})
            
            report = (
                f"TEST REPORT: {summary.get('passed', 0)}/{summary.get('total', 0)} PASS\n"
                f"FAIL: {summary.get('failed', 0)} | ERR: {summary.get('errors', 0)}\n"
                "---"
            )
            
            # Aggiungi solo i test falliti per non saturare il contesto
            for t in data.get("tests", []):
                if t["status"] in ("FAIL", "ERROR"):
                    report += f"\n[{t['status']}] {t['name']}: {t['detail']}"
            
            return report if len(report) > 15 else report + "\nTutti i test sono passati!"
        except Exception as e:
            return f"ERROR running test suite: {e}"

    # ----- 18. lint_code -----
    def lint_code(self, path: str) -> str:
        """Controlli statici su un file: py_compile + Bandit + Mypy.

        Bandit e Mypy girano SEMPRE nel sandbox (via `_run`). Se non sono
        installati vengono segnalati con un errore istruttivo, il gate
        sintattico resta comunque bloccante.
        """
        try:
            full = safe_project_path(path, self.project_root)
            if not full.exists():
                return f"ERROR: file non trovato: {path}"
            
            # 1. Sintassi (bloccante)
            import py_compile
            try:
                py_compile.compile(str(full), doraise=True)
            except SyntaxError as e:
                return f"SINTASSI ERRATA in {path}:\n{str(e)}"
            
            report = [f"SYNTAX OK: {path}"]
            
            # 2. Bandit (analisi sicurezza statica)
            try:
                rel = str(full.relative_to(self.project_root))
                r = self._run(
                    [sys.executable, "-m", "bandit", "-q", "-f", "text", rel],
                    timeout=120, cwd=self.project_root,
                )
                if "No module named bandit" in r:
                    report.append(
                        "BANDIT: non installato (pip install bandit). "
                        "Gate statico parziale: ieri puro py_compile."
                    )
                elif "No issues identified." in r or "Total issues: 0" in r:
                    report.append("BANDIT OK: nessun problema di sicurezza.")
                else:
                    snippet = r.strip()[:800]
                    report.append(f"BANDIT ISSUES:\n{snippet}")
            except Exception as e:
                report.append(f"BANDIT: errore esecuzione: {e}")
            
            # 3. Mypy (tipi statici, best-effort)
            try:
                rel = str(full.relative_to(self.project_root))
                r = self._run(
                    [sys.executable, "-m", "mypy", "--no-error-summary", rel],
                    timeout=120, cwd=self.project_root,
                )
                if "No module named mypy" in r:
                    report.append(
                        "MYPY: non installato (pip install mypy). "
                        "Type check non eseguito."
                    )
                elif "Success: no issues found" in r or r.strip().endswith("exit_code=0"):
                    report.append("MYPY OK: nessun errore di tipo.")
                else:
                    snippet = r.strip()[:800]
                    report.append(f"MYPY ISSUES:\n{snippet}")
            except Exception as e:
                report.append(f"MYPY: errore esecuzione: {e}")
            
            return "\n".join(report)
        except Exception as e:
            return f"ERROR linting {path}: {e}"


    # ----- 14. patch_code -----
    def patch_code(self, path: str, old_text: str, new_text: str) -> str:
        """Modifica una porzione specifica di un file.
        
        Cerca l'esatta occorrenza di `old_text` e la sostituisce con `new_text`.
        Se `old_text` non è trovato esattamente, l'operazione fallisce.
        """
        try:
            full = safe_project_path(path, self.project_root)
            if not full.exists():
                return f"ERROR: file non trovato: {path}"
            
            content = full.read_text(encoding="utf-8", errors="replace")
            if old_text not in content:
                return (f"ERROR: testo originale non trovato nel file. "
                        "Assicurati di copiare esattamente il blocco di codice.")
            
            new_content = content.replace(old_text, new_text, 1)
            
            if len(new_content) > self.max_write_bytes:
                return "ERROR: file risultante troppo grande."
            
            # GATE ANTI-CORRUZIONE (todo 9c/M1): una patch su un file Python
            # deve lasciare il file ancora compilabile e senza codice vietato.
            # Chiude il buco per cui una patch corrotta (es. artefatti di
            # escape) potevano infrangere la validita di un file esistente.
            if str(path).endswith(".py"):
                safe, reason = ast_scanner.scan(new_content)
                if not safe:
                    self._audit(
                        "blocked_patch_scan",
                        f'path="{self._q(path)}" reason="{self._q(reason)}"',
                        "CRITICAL",
                    )
                    return (f"ERROR: patch rifiutata (il file `{path}` risulterebbe "
                            f"invalido o insicuro): {reason}")
            
            # Scrittura transazionale
            full.parent.mkdir(parents=True, exist_ok=True)
            tmp = full.parent / f".{full.name}.patch.{os.getpid()}.tmp"
            tmp.write_text(new_content, encoding="utf-8")
            os.replace(tmp, full)
            
            return f"OK: patch applicata a {path}"
        except Exception as e:
            return f"ERROR patching {path}: {e}"


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
        """Esegue argv dentro il sandbox bubblewrap, senza shell.

        Fail closed: se bubblewrap non è disponibile il comando non viene
        eseguito sull'host e l'evento viene registrato come CRITICAL.
        """
        # M7: quota disco — non avviare comandi con project/ satura.
        guard = self._disk_guard()
        if guard:
            return guard

        try:
            workdir = sandbox.sandbox_workdir(cwd, self.project_root)
            cmd, env = sandbox.build_command(
                argv, self.project_root, workdir=workdir,
            )
        except sandbox.SandboxError as exc:
            self._audit(
                "sandbox_unavailable",
                f'cmd="{self._q(" ".join(str(a) for a in argv))}" '
                f'reason="{self._q(exc)}" action="fail-closed"',
                "CRITICAL",
            )
            return (
                "ERROR: sandbox non disponibile, comando NON eseguito "
                "(fail closed).\n"
                f"Dettaglio: {exc}\n"
                "Installa bubblewrap con: sudo apt install bubblewrap"
            )

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                start_new_session=True,
                preexec_fn=self._preexec(timeout),
            )
        except FileNotFoundError:
            return f"ERROR: comando non trovato: {argv[0]} (o bwrap assente)"
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

        # bwrap riporta così un eseguibile assente nel sandbox: traduci in un
        # errore istruttivo per i modelli piccoli.
        if proc.returncode != 0 and "bwrap: execvp" in stderr:
            missing = str(argv[0])
            for line in stderr.splitlines():
                if "bwrap: execvp" in line:
                    missing = line.split("execvp", 1)[1].strip().rstrip(":")
                    break
            return (
                f"ERROR: comando non disponibile nel sandbox: {missing}\n"
                "Controlla il nome (es. 'python3', 'gcc') e riprova con un "
                "singolo comando semplice."
            )

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

    def _project_disk_mb(self) -> int:
        """Usa cumulata in MB dei file in project/ (non .git)."""
        total = 0
        for root, dirs, files in os.walk(self.project_root):
            if ".git" in dirs:
                dirs.remove(".git")
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    continue
        return total // (1024 * 1024)

    def _disk_guard(self) -> str:
        """Rifiuta l'esecuzione se project/ supera la quota (M7)."""
        used = self._project_disk_mb()
        if used >= self.max_project_mb:
            self._audit(
                "resource_limit",
                f'project_size={used}MB limit={self.max_project_mb}MB',
                "WARNING",
            )
            return (
                f"ERROR: quota disco project/ superata "
                f"({used} MB >= limite {self.max_project_mb} MB). "
                "Elimina i file temporanei grandi in project/ e riprova."
            )
        return ""

    # ----- 23. inspect_usb_devices -----
    def inspect_usb_devices(self) -> str:
        """Returns detailed information about connected USB devices."""
        try:
            r = self._run(["lsusb", "-v"], timeout=20, cwd=self.project_root)
            return r if r.strip() else "(no USB devices found)"
        except Exception as e:
            return f"ERROR inspecting USB: {e}"

    # ----- 24. capture_usb_traffic(bus, duration) -----
    def capture_usb_traffic(self, bus: str, duration: int = 5) -> str:
        """Captures USB traffic on a specific bus for a duration using tshark."""
        try:
            cmd = [
                "tshark", "-i", f"usbmon{bus}", 
                "-a", f"duration:{duration}", 
                "-c", "100", 
                "-T", "text"
            ]
            r = self._run(cmd, timeout=duration + 10, cwd=self.project_root)
            return r if r.strip() else "(no traffic captured on this bus)"
        except Exception as e:
            return f"ERROR capturing USB traffic: {e}"

    def _safe_ref(self, ref: str) -> Optional[str]:
        """Validates a git reference to prevent injection attacks."""
        if not ref:
            return None
        if _REF_RE.match(ref):
            return ref
        return None
