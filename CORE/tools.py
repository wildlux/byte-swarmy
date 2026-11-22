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

import difflib
import io
import os
import re
import json
import resource
import tokenize
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, Sequence

# Root del repo (tests/run_tests.py ecc.); indipendente da cwd.
# Nota: il worker NON lavora qui — project_root (config) è il suo workspace.
BASE_DIR = Path(__file__).resolve().parent.parent


def _tmp_name(base: str, suffix: str = "") -> str:
    """Nome temp file unguibile: pid + UUID per evitare collisioni fra
    worker concorrenti nello stesso processo (stesso pid → stesso nome)."""
    return f".{base}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp{suffix}"

from CORE import sandbox

from SAFETY.security import (
    SecurityError,
    allowed_commands_text,
    is_sensitive_path,
    log_security_event,
    normalize_bash_argv,
    safe_project_path,
    validate_bash_command,
)
from CORE.ast_scanner import scanner as ast_scanner, detect_artifacts
from CORE.import_check import blocking, check_path, format_issues
from CORE.regex_controller import RegexController, DEFAULT_PATTERNS, validate_chars
from CORE.runtime_verifier import RuntimeVerifier
from CORE.tool_registry import TOOL_REGISTRY, register_tool, get_tool, list_tools

# Firme dei tool per i system prompt (worker e pannello Chat).
# Estratte a livello modulo così anche la GUI può elencarle senza
# istanziare un ToolSet (che richiede config e project_root).
TOOL_SIGNATURES = {
    "read_file": "read_file(path) -> str: legge un file dentro project/",
    "read_document": "read_document(path) -> str: legge un documento (.txt/.md/.py/.pdf via pdftotext) e restituisce il testo estratto (troncato)",
    "list_refs": "list_refs() -> str: elenca i cheat sheet disponibili in GUI/refs/ (PyQt6, ToolSet API, debt ledger). Leggili con read_file per ridurre allucinazioni.",
    "api_lookup": "api_lookup(module, symbol='', strict=False) -> str: firma reale via introspezione; strict=True blocca se non verificabile.",
    "read_file_slice": "read_file_slice(path, start_line, end_line) -> str: legge max 200 righe di un file grande (righe 1-based)",
    "write_file": "write_file(path, content) -> str: scrive atomicamente in project/",
    "patch_code": "patch_code(path, old_text, new_text) -> str: sostituisce una porzione di testo in un file",
    "delete_file": "delete_file(path) -> str: cancella un file singolo dentro project/",
    "move_file": "move_file(path, new_path) -> str: rinomina o sposta un file dentro project/ (non sovrascrive)",
    "list_files": "list_files(path='.', pattern='*') -> str: elenca file e cartelle (glob, es. '*.py')",
    "analyze_project": "analyze_project() -> str: restituisce la mappa di classi e funzioni del progetto",
    "find_references": "find_references(symbol) -> str: cerca tutte le occorrenze di una funzione/variabile",
    "lint_code": "lint_code(path) -> str: verifica errori di sintassi e stile in un file",
    "rename_symbol": "rename_symbol(old, new, apply=False) -> str: anteprima diff; apply=True scrive con snapshot",
    "restore_snapshot": "restore_snapshot(id) -> str: ripristina i file di un rename precedente (rollback)",
    "spawn_subagent": "spawn_subagent(model_key, task) -> str: crea un figlio (profondità max 1, max 4); NON esegue LLM",
    "get_subagent_report": "get_subagent_report(agent_id) -> str: esegue (se pending) e restituisce il report del figlio",
    "list_subagents": "list_subagents() -> str: elenca i subagent con stato e modello",
    "analyze_complexity": "analyze_complexity(path) -> str: stima la complessità di un file",
    "get_call_graph": "get_call_graph(symbol) -> str: mappa chi chiama la funzione/classe",
    "find_dead_code": "find_dead_code(path='.') -> str: report SOLO LETTURA di funzioni/classi/import non referenziati (non cancella nulla)",
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
    "run_test_suite": "run_test_suite() -> str: esegue i test del progetto",
    "list_tools": "list_tools() -> str: elenca i tool disponibili con le loro firme",
}

# Re-export storici: tests/test_reuse.py importa questi nomi da CORE.tools.
__all__ = [
    "ToolSet", "PROTECTED_FILES", "PROTECTED_BRANCHES", "TOOL_SIGNATURES",
    "TOOL_REGISTRY", "register_tool", "get_tool", "list_tools",
]

# Controllore regex riusabile: py_class / py_def sono già nei default
_REGEX = RegexController(DEFAULT_PATTERNS)


# Branch che i worker non possono cancellare.
PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "trunk"})

# Directory escluse dal rename simbolico (generate/dati/ambienti).
_RENAME_SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "__pycache__", "data", "state",
    "node_modules", "build", "dist", ".pytest_cache", ".mypy_cache",
})


def _as_bool(value) -> bool:
    """Flag dei tool passati anche come stringa ('true'/'false')."""
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "si", "sì"}
    return bool(value)

# 🆕 Cycle 79: file di infrastruttura critica. Il worker NON può
# sovrascriverli/cancellarli con write_file/delete_file/move_file:
# il danno a requirements.txt (203 righe → 9 byte) è avvenuto perché
# la gate precedente non li copriva. patch_code resta permesso (edit
# mirati: es. aggiungere una dipendenza). La lista è di basename:
# vale per qualunque percorso dentro project/.
PROTECTED_FILES = frozenset({
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
    "requirements_gui.txt", "requirements_re.txt",
    "pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "pipfile",
    "pipfile.lock", "poetry.lock",
    ".gitignore", ".gitattributes",
    "makefile", "cmakelists.txt",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "cargo.toml", "go.mod", "go.sum",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "config.toml", "config.yaml", "config.yml",
    "readme.md", "license", "license.md",
})

# 🆕 Cycle 80: cartelle di riferimento curate — il worker NON può
# sovrascriverle (sono "salva culo" per ridurre le allucinazioni).
PROTECTED_PATH_PREFIXES = ("gui/refs/", "skills/", ".opencode/skill/")


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
        self.subagents = None  # registry iniettata dal Worker (CORE/subagent.py)

        sec = config.get("security", {})
        self.max_output = int(sec.get("max_output_chars", 10_000))
        self.max_write_bytes = int(sec.get("max_file_size_write", 2_000_000))
        self.max_file_limit = int(sec.get("max_file_size_bytes", 50_000_000))
        self.max_memory_mb = int(sec.get("max_memory_mb", 1536))
        # M7: limita il disco consumato da project/ (saturazione in pochi
        # secondi con dd/yes non e visibile dal check periodico ogni 30s).
        self.max_project_mb = int(sec.get("project_disk_limit_mb", 2048))

        # 🆕 Cycle 56: runtime verification harness (smoke test sui file scritti).
        self.runtime = RuntimeVerifier(
            self.project_root, self.log,
            timeout_py=int(sec.get("timeout_py", 60)),
            timeout_test=int(sec.get("timeout_test", 180)),
            timeout_boot=int(sec.get("timeout_boot", 15)),
        )

        # P1-2: file .py toccati nel task corrente → gate import-check
        # (nomi indefiniti) eseguito a ogni scrittura e al `done`.
        self.touched_python: dict[str, str] = {}

        # Robustezza #2: snapshot pre-write (backup deterministico).
        self._backup_session_ts = int(time.time())
        self._backup_retention = int(
            (self.cfg.get("backup") or {}).get("retention_sessions", 5))

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

    def set_subagents(self, registry) -> None:
        """Collega il registry dei subagent (senza chiamare l'LLM)."""
        self.subagents = registry

    # ------------------------------------------------------------------
    # P1-2 — gate import-check (nomi indefiniti = API allucinate)
    # ------------------------------------------------------------------
    def reset_touched(self) -> None:
        """Azzera i file tracciati: chiamato a inizio task dal worker."""
        self.touched_python.clear()

    def _track_python(self, path: str) -> str:
        """Registra un .py scritto e ritorna l'eventuale warning.

        Non blocca la scrittura: a metà task un file può citare un modulo
        che verrà creato dopo. Il blocco vero è sul `done` del worker
        (come il test-gate C78); qui il feedback è immediato per poter
        correggere subito.
        """
        if not str(path).endswith(".py"):
            return ""
        try:
            full = safe_project_path(path, self.project_root)
        except Exception:
            return ""
        self.touched_python[str(path)] = str(full)
        issues = blocking(check_path(full))
        if not issues:
            return ""
        self.log.warning(
            f"import-check {path}: {len(issues)} nome/i indefinito/i")
        return ("IMPORT-CHECK WARNING: nomi indefiniti (il `done` sarà "
                "rifiutato finché restano):\n"
                + format_issues(issues, limit=5))

    def pending_import_issues(self) -> dict[str, list]:
        """Ricalcola i nomi indefiniti sui .py toccati (solo esistenti).

        Ritorna {path_relativo: [Issue, ...]} solo per i file che ancora
        hanno errori bloccanti — quindi una patch successiva che li
        corregge fa sparire il blocco.
        """
        pending: dict[str, list] = {}
        for rel, full in self.touched_python.items():
            if not Path(full).exists():
                continue
            issues = blocking(check_path(full))
            if issues:
                pending[rel] = issues
        return pending

    # ------------------------------------------------------------------
    # Robustezza #2 — snapshot pre-write (backup deterministico)
    # ------------------------------------------------------------------
    def _snapshot_path(self, rel_path: str):
        """Path del backup per questo file/sessione, o None se non applicabile."""
        try:
            full = safe_project_path(rel_path, self.project_root)
        except Exception:
            return None
        if not full.exists() or not full.is_file():
            return None
        backups_root = Path(self.cfg["paths"].get("backups_dir", "./backups"))
        session_dir = backups_root / f"prewrite-{self._backup_session_ts}"
        dest = session_dir / rel_path
        try:
            dest.resolve().relative_to(session_dir.resolve())
        except ValueError:
            return None
        return dest

    def snapshot_before_write(self, path: str) -> str:
        """Copia il file corrente in backups/prewrite-<ts>/<relpath>.

        Chiamato prima di ogni scrittura sovrascrivente. Fail-open: se il
        backup fallisce, la scrittura procede (il backup è una rete, non
        un gate). Ritorna il path del backup o '' se non applicabile.
        """
        dest = self._snapshot_path(path)
        if dest is None:
            return ""
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_project_path(path, self.project_root), dest)
            self._prune_prewrite_backups()
            return str(dest)
        except Exception as e:
            self.log.warning(f"snapshot pre-write fallito per {path}: {e}")
            return ""

    def restore_from_backup(self, path: str, session_ts: int | None = None) -> str:
        """Ripristina un file dal backup pre-write.

        session_ts: timestamp della sessione (default: quella corrente).
        Ritorna 'OK: ...' o 'ERROR: ...'.
        """
        ts = session_ts if session_ts is not None else self._backup_session_ts
        try:
            full = safe_project_path(path, self.project_root)
        except Exception as e:
            return f"ERROR: {e}"
        backups_root = Path(self.cfg["paths"].get("backups_dir", "./backups"))
        src = backups_root / f"prewrite-{ts}" / path
        if not src.exists() or not src.is_file():
            return f"ERROR: backup non trovato per {path} (sessione {ts})"
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, full)
            return f"OK: ripristinato {path} da backup prewrite-{ts}"
        except Exception as e:
            return f"ERROR: restore fallito: {e}"

    def _prune_prewrite_backups(self) -> None:
        backups_root = Path(self.cfg["paths"].get("backups_dir", "./backups"))
        if not backups_root.exists():
            return
        sessions = sorted(backups_root.glob("prewrite-*"),
                          key=lambda p: p.name)
        keep = max(1, self._backup_retention)
        for old in sessions[:-keep]:
            try:
                shutil.rmtree(old)
            except Exception:
                pass

    def retrieve_similar_task(self, query: str, k: int = 3) -> str:
        """Fase F: retrieval TF-IDF di task gia' chiusi con soluzione.

        Costruisce l'indice dal corpus di feedback (output completi) e,
        in fallback, da queue.db (result troncati). Ritorna i top-k
        simili formattati per l'iniezione nel prompt. Zero LLM.
        """
        try:
            from CORE import retrieval as _ret
            state_dir = self.cfg["paths"].get("state_dir", "./state")
            tasks_dir = self.cfg["paths"].get("tasks_dir", "./tasks")
            r = _ret.build_from_corpus(state_dir)
            if not r.tasks:
                r = _ret.build_from_queue_db(tasks_dir=tasks_dir,
                                            state_dir=state_dir)
            results = r.retrieve(query, k=max(1, int(k)))
            return r.format_results(results)
        except Exception as e:
            self.log.warning(f"retrieve_similar_task fallito: {e}")
            return f"ERROR: retrieval fallito: {e}"

    # ----- subagent: creazione/rendicontazione figli (no LLM in spawn) -----
    def spawn_subagent(self, model_key: str, task: str) -> str:
        """Crea un subagent con ruolo modello esistente. Non lo esegue."""
        if self.subagents is None:
            return "ERROR: registry subagent non inizializzata."
        return self.subagents.spawn(self.worker, model_key, task)

    def get_subagent_report(self, agent_id: str) -> str:
        """Report del figlio; se pending applica i gate e lo esegue."""
        if self.subagents is None:
            return "ERROR: registry subagent non inizializzata."
        return self.subagents.get_report(agent_id)

    def list_subagents(self) -> str:
        """Elenco dei figli creati in questa sessione."""
        if self.subagents is None:
            return "ERROR: registry subagent non inizializzata."
        return self.subagents.list_agents()

    def allowed_tools(self) -> set[str]:
        """Tool che il worker può realmente chiamare."""
        tools = {
            "read_file", "read_file_slice", "read_document", "write_file", "patch_code",
            "delete_file", "move_file", "list_files",
            "run_bash", "search",
            "analyze_project", "find_references", "lint_code",
            "rename_symbol", "restore_snapshot", "analyze_complexity",
            "get_call_graph", "find_dead_code", "extract_method",
            "git_commit", "git_diff", "git_status", "git_log",
            "git_branch", "git_merge", "git_pull", "git_push", "git_remote",
            "run_test_suite", "list_refs", "list_tools", "diary_llm", "retrieve_similar_task",
            "api_lookup", "spawn_subagent", "get_subagent_report",
            "list_subagents",
        }
        try:
            from GUI.settings_store import get_usb_tools_enabled
            if get_usb_tools_enabled():
                tools.add("inspect_usb_devices")
                tools.add("capture_usb_traffic")
        except Exception:
            pass
        return tools

    # ----- 1. read_file -----
    def read_file(self, path: str) -> str:
        """Legge un file dal progetto. Rifiuta path fuori/sensibili e file grandi."""
        try:
            full = safe_project_path(path, self.project_root)
        except SecurityError as exc:
            self._audit("blocked_path", f'op=read path="{self._q(path)}" reason="{exc}"',
                        "WARNING")
            return f"ERROR: {exc}. You can only read files inside project/."

        if not full.exists():
            return f"ERROR: file not found: {path}"
        if full.is_dir():
            return f"ERROR: '{path}' is a directory. Use run_bash('ls {path}')."
        size = full.stat().st_size
        if size > self.cfg["routing"]["max_file_size_readable"]:
            return f"ERROR: file too large ({size} bytes). Read it in chunks with read_file_slice."
        try:
            return full.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"ERROR reading {path}: {e}"

    # ----- 1b. read_document (testo/PDF/markdown -> estrazione + summary) -----
    def read_document(self, path: str) -> str:
        """Legge un documento di testo dal progetto.

        Supporta: .txt, .md, .py, .json, .csv, .log (testo diretto) e
        .pdf (via pdftotext se installato). Per i PDF restituisce il testo
        estratto (troncato a max_file_size_readable).
        """
        try:
            full = safe_project_path(path, self.project_root)
        except SecurityError as exc:
            self._audit("blocked_path",
                        'op=read_document path="%s" reason="%s"' % (self._q(path), exc),
                        "WARNING")
            return "ERROR: %s. You can only read files inside project/." % exc

        if not full.exists():
            return "ERROR: file not found: %s" % path
        if full.is_dir():
            return "ERROR: '%s' is a directory." % path

        suffix = full.suffix.lower()
        text_exts = {".txt", ".md", ".markdown", ".py", ".json", ".csv",
                     ".log", ".rst", ".yaml", ".yml", ".toml", ".ini",
                     ".cfg", ".html", ".xml"}
        try:
            if suffix == ".pdf":
                import shutil, subprocess
                if not shutil.which("pdftotext"):
                    return ("ERROR: pdftotext non installato. "
                            "Installa poppler-utils (apt install poppler-utils).")
                proc = subprocess.run(
                    ["pdftotext", "-layout", str(full), "-"],
                    capture_output=True, text=True, timeout=60,
                )
                if proc.returncode != 0:
                    return "ERROR pdftotext: %s" % proc.stderr[:300]
                text = proc.stdout
            elif suffix in text_exts:
                text = full.read_text(encoding="utf-8", errors="replace")
            else:
                return ("ERROR: formato non supportato '%s'. "
                        "Supportati: %s, .pdf" % (suffix, ", ".join(sorted(text_exts))))
        except Exception as e:
            return "ERROR reading document %s: %s" % (path, e)

        size = len(text)
        if size > self.cfg["routing"]["max_file_size_readable"]:
            text = text[:self.cfg["routing"]["max_file_size_readable"]]
            text += "\n\n[... troncato a %d byte]" % self.cfg["routing"]["max_file_size_readable"]
        return text

    # ----- 1c. list_refs — elenco dei cheat sheet in GUI/refs/ -----
    def list_refs(self) -> str:
        """Elenca i file di riferimento (cheat sheet) disponibili in
        GUI/refs/. Il worker puo' leggerli con read_file/read_document
        per ridurre le allucinazioni su API comuni."""
        try:
            refs_dir = safe_project_path("GUI/refs", self.project_root)
        except SecurityError as exc:
            return "ERROR: %s" % exc
        if not refs_dir.exists() or not refs_dir.is_dir():
            return "Nessun ref disponibile (cartella GUI/refs/ assente)."
        files = sorted(p.name for p in refs_dir.iterdir()
                       if p.is_file() and p.suffix in (".md", ".txt", ".py"))
        if not files:
            return "Nessun ref disponibile."
        return "REFS DISPONIBILI (leggi con read_file):\n" + "\n".join(
            "  - GUI/refs/%s" % f for f in files)

    # ----- api_lookup: introspezione runtime di un pacchetto installato -----
    def api_lookup(self, module: str, symbol: str = "",
                   strict: bool = False) -> str:
        """Introspezione runtime di un pacchetto installato (anti-allucinazione).

        Restituisce la firma + docstring di `symbol` in `module`, oppure
        l'elenco dei simbodo pubblici se `symbol` è vuoto. Funziona per
        qualsiasi pacchetto installato, incluse API nuove. Con `strict=True`
        import falliti, simboli assenti e firme non introspettabili bloccano
        la generazione invece di lasciare un elenco generico.
        """
        import importlib
        import inspect
        strict = _as_bool(strict)

        def blocked(msg: str) -> str:
            if strict:
                return (f"ERROR: {msg} — API NON VERIFICATA (strict): "
                        "generazione bloccata.")
            return f"ERROR: {msg}"

        if not isinstance(module, str) or not module.strip():
            return blocked("module richiesto (es. 'json', 'pathlib').")
        try:
            mod = importlib.import_module(module.strip())
        except Exception as e:
            return blocked(f"impossibile importare '{module}': {e}")

        if not symbol or not str(symbol).strip():
            if strict:
                return blocked(
                    "elenco pubblico non verifica una firma: specificare un simbolo.")
            names = [n for n in dir(mod) if not n.startswith("_")]
            return ("SIMBODI PUBBLICI di %s (%d):\n" % (module, len(names)) +
                    ", ".join(names[:80]) +
                    ("\n... (troncato)" if len(names) > 80 else ""))

        sym = str(symbol).strip()
        # Supporta "module.sub" o "Class.method"
        obj = mod
        for part in sym.split("."):
            if not hasattr(obj, part):
                return blocked(
                    f"simbolo '{sym}' non trovato in '{module}'. "
                    f"Usa api_lookup('{module}') per l'elenco.")
            obj = getattr(obj, part)

        lines = [f"{module}.{sym}"]
        try:
            sig = inspect.signature(obj)
            lines.append(f"  firma: {sym}{sig}")
        except (TypeError, ValueError):
            if strict:
                return blocked(f"firma di '{sym}' non introspettabile")
            lines.append("  firma: (non disponibile)")
        doc = inspect.getdoc(obj)
        if doc:
            lines.append("  doc: " + doc.splitlines()[0][:200])
        if strict:
            lines.append(f"  stato: VERIFICATO via inspect su {module}")
        return "\n".join(lines)

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
                return f"ERROR: Security Violation. The code contains forbidden elements: {reason}."

        # Gate anti-corruzione (todo 9c/M1): artefatti di escape su QUALSIASI
        # file di testo (il bug più costoso del progetto colpiva anche .py/.md).
        if detect_artifacts(content):
            self._audit("blocked_escape_artifact",
                        f'path="{self._q(path)}"', "CRITICAL")
            return ("ERROR: write_file rejected: the content contains escape "
                "artifacts (e.g. \\\" at line start). Do NOT use patch_code "
                "to fix it: rewrite the whole clean file with write_file.")
        if len(content) > self.max_write_bytes:
            return (f"ERROR: content too large ({len(content)} bytes, "
                    f"max {self.max_write_bytes}). Write smaller files.")
        try:
            full = safe_project_path(path, self.project_root, for_write=True)
        except SecurityError as exc:
            self._audit("blocked_path", f'op=write path="{self._q(path)}" reason="{exc}"',
                        "WARNING")
            return (f"ERROR: {exc}. Write only inside project/ "
                    f"(e.g. 'project/main.py').")

        # 🆕 Cycle 80: cartelle di riferimento curate — mai sovrascrivibili.
        norm = path.replace("\\", "/").lower().lstrip("./")
        if any(norm.startswith(p) for p in PROTECTED_PATH_PREFIXES):
            self._audit("blocked_protected_ref",
                        f'path="{self._q(path)}"', "CRITICAL")
            return ("ERROR: write_file bloccato: '%s' e' in una cartella di "
                    "riferimento curata (GUI/refs, SKILLS, .opencode/skill). "
                    "I ref sono read-only." % path)

        # 🆕 Cycle 79: file di infrastruttura critica — mai sovrascrivibili
        # con write_file (il danno a requirements.txt: 203 righe -> 9 byte).
        # patch_code resta permesso (edit mirati). delete_file/move_file
        # hanno la stessa guardia.
        if os.path.basename(path).lower() in PROTECTED_FILES and full.exists():
            self._audit("blocked_protected_write",
                        f'path="{self._q(path)}"', "CRITICAL")
            return ("ERROR: write_file bloccato: '%s' e' un file di "
                    "infrastruttura critica (protetto). Usa patch_code per "
                    "modifiche mirate, oppure modifica il file a mano." % path)

        # 🆕 Cycle 79: guardia anti-shrink sospetto. Se un file esistente
        # e' grande (>500 byte) e il nuovo contenuto e' <20% delle
        # dimensioni originali, blocca: e' il pattern esatto del danno
        # (requirements.txt 203 righe -> 9 byte, main.py 53 righe -> 1).
        try:
            if full.exists():
                old_size = full.stat().st_size
                if (old_size >= 500
                        and len(content) < max(50, old_size // 5)):
                    self._audit("blocked_suspicious_shrink",
                                f'path="{self._q(path)}" old={old_size} '
                                f'new={len(content)}', "CRITICAL")
                    return ("ERROR: write_file bloccato: shrink sospetto "
                            "(%d byte -> %d byte, <20%% dell'originale). "
                            "Se intendi davvero ridurre il file, usa "
                            "patch_code o modifica a mano." % (old_size, len(content)))
        except OSError:
            pass

        # M7: quota disco — non permettere scritture con project/ già saturo.
        guard = self._disk_guard()
        if guard:
            return guard

        if full.exists() and full.is_dir():
            return f"ERROR: '{path}' is a directory."

        # Robustezza #2: snapshot pre-write (solo se il file esiste).
        self.snapshot_before_write(path)
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            tmp = full.parent / _tmp_name(full.name)
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, full)
            # 🆕 Cycle 56: runtime verification smoke test sul file scritto.
            # Su fallimento: rollback (rimozione) + feedback specifico al worker
            # (che entra nel correction loop con questo errore, non un generico
            # "syntax error").
            verify_msg = self.runtime.verify_task_files([str(full)])
            if verify_msg.startswith("ERROR"):
                try:
                    full.unlink(missing_ok=True)
                except Exception:
                    pass
                self._audit("runtime_verify_failed",
                            f'path="{self._q(path)}" err="{self._q(verify_msg)}"',
                            "HIGH")
                log_security_event(
                    "runtime_verify_failed",
                    f'path="{self._q(path)}" err="{self._q(verify_msg)}"',
                    "HIGH", worker=self.worker,
                )
                self.log.warning(f"write_file runtime verify FAILED: {verify_msg}")
                return verify_msg
            self.log.debug(f"wrote {len(content)} bytes -> {path}")
            extra = self._track_python(path)
            msg = f"OK: wrote {len(content)} bytes to {path}"
            return f"{msg}\n{extra}" if extra else msg
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
            return "ERROR: empty command"

        ok, reason = validate_bash_command(cmd, self.project_root)
        if not ok:
            self._audit(
                "blocked_command",
                f'cmd="{self._q(cmd)}" reason="{self._q(reason)}"',
                "CRITICAL",
            )
            return (
                f"ERROR: command blocked: {reason}.\n"
                f"{allowed_commands_text()}\n"
                "Hint: use the dedicated tools (write_file, git_commit, search) "
                "or a single simple command inside project/."
            )

        self._audit("allowed_command", f'cmd="{self._q(cmd)}"', "INFO")

        try:
            argv = shlex.split(cmd, posix=True)
        except ValueError as exc:
            return f"ERROR: invalid command: {exc}"
        if not argv:
            return "ERROR: empty command"

        # `cd` non ha senso: ogni comando parte già da project/.
        if argv[0] == "cd":
            return f"OK: the working directory is already {self.project_root}"

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
            return ("ERROR: invalid revision. Use HEAD, HEAD~1, a hash "
                    "or a local branch name.")
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
            return "ERROR: missing pattern"
        if len(pattern) > 500:
            return "ERROR: pattern too long (max 500)"
        if not isinstance(file_glob, str):
            file_glob = "*"
        if not validate_chars(file_glob, "glob") or ".." in Path(file_glob).parts:
            return "ERROR: invalid file_glob"
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

    # ----- 6b. delete_file (ciclo di vita file: create esiste, delete no) -----
    def delete_file(self, path: str) -> str:
        """Cancella UN file dentro project/ (mai directory, mai root)."""
        try:
            full = safe_project_path(path, self.project_root, for_write=True)
        except SecurityError as exc:
            self._audit("blocked_path",
                        f'op=delete path="{self._q(path)}" reason="{exc}"',
                        "WARNING")
            return f"ERROR: {exc}. You can only delete files inside project/."

        if not full.exists():
            return f"ERROR: file not found: {path}"
        if full.is_dir():
            return ("ERROR: '{p}' is a directory: delete_file deletes "
                    "single files only.".format(p=path))

        # 🆕 Cycle 79: file di infrastruttura critica — non cancellabili.
        if os.path.basename(path).lower() in PROTECTED_FILES:
            self._audit("blocked_protected_delete",
                        f'path="{self._q(path)}"', "CRITICAL")
            return ("ERROR: delete_file bloccato: '%s' e' un file di "
                    "infrastruttura critica (protetto)." % path)

        size = full.stat().st_size
        try:
            full.unlink()
            self._audit("file_deleted", f'path="{self._q(path)}" bytes={size}', "INFO")
            return f"OK: deleted {path} ({size} bytes)"
        except Exception as e:
            return f"ERROR deleting {path}: {e}"

    # ----- 6c. move_file (rinomina/sposta file dentro project/) -----
    def move_file(self, path: str, new_path: str) -> str:
        """Rinomina o sposta un file dentro project/. Non sovrascrive."""
        try:
            src = safe_project_path(path, self.project_root, for_write=True)
            dst = safe_project_path(new_path, self.project_root, for_write=True)
        except SecurityError as exc:
            self._audit("blocked_path",
                        f'op=move "{self._q(path)}"->"{self._q(new_path)}" '
                        f'reason="{exc}"', "WARNING")
            return f"ERROR: {exc}. You can only move files inside project/."

        if not src.exists():
            return f"ERROR: file not found: {path}"
        if src.is_dir():
            return (f"ERROR: '{path}' is a directory: move_file moves "
                    "single files only.")

        # 🆕 Cycle 79: file di infrastruttura critica — non sovrascrivibili
        # via move (dst protetto).
        if os.path.basename(new_path).lower() in PROTECTED_FILES and dst.exists():
            self._audit("blocked_protected_move",
                        f'"{self._q(path)}"->"{self._q(new_path)}"', "CRITICAL")
            return ("ERROR: move_file bloccato: la destinazione '%s' e' un "
                    "file di infrastruttura critica (protetto)." % new_path)
        if dst.exists():
            return f"ERROR: '{new_path}' already exists: choose another name."
        if src == dst:
            return "ERROR: source and destination are the same."

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            self._audit("file_moved",
                        f'from="{self._q(path)}" to="{self._q(new_path)}"', "INFO")
            return f"OK: moved {path} -> {new_path}"
        except Exception as e:
            return f"ERROR moving {path} -> {new_path}: {e}"

    # ----- 6d. list_files (listing sicuro con glob) -----
    def list_files(self, path: str = ".", pattern: str = "*") -> str:
        """Elenca file e cartelle dentro project/ (glob, esclude sensibili)."""
        if not isinstance(pattern, str) or not validate_chars(pattern or "*", "glob"):
            return "ERROR: invalid pattern (use e.g. '*.py')"
        try:
            base = safe_project_path(path or ".", self.project_root)
        except SecurityError as exc:
            self._audit("blocked_path",
                        f'op=list path="{self._q(path)}" reason="{exc}"',
                        "WARNING")
            return f"ERROR: {exc}. You can only list directories inside project/."

        if not base.exists():
            return f"ERROR: directory not found: {path}"
        if not base.is_dir():
            return f"ERROR: '{path}' is not a directory."

        try:
            entries = sorted(base.glob(pattern))[:200]
            lines = []
            for e in entries:
                if is_sensitive_path(e):
                    continue
                tag = "/" if e.is_dir() else ""
                size = f" ({e.stat().st_size}b)" if e.is_file() else ""
                lines.append(f"{e.relative_to(self.project_root)}{tag}{size}")
            if not lines:
                return "(empty)"
            out = "\n".join(lines)
            if len(entries) == 200:
                out += TRUNCATED
            return out
        except Exception as e:
            return f"ERROR list_files: {e}"

    # ----- 6e. read_file_slice (porzioni di file grandi, 1-based) -----
    def read_file_slice(self, path: str, start_line: int, end_line: int) -> str:
        """Legge le righe [start_line, end_line] di un file (max 200 a chiamata)."""
        try:
            full = safe_project_path(path, self.project_root)
        except SecurityError as exc:
            self._audit("blocked_path",
                        f'op=read_slice path="{self._q(path)}" reason="{exc}"',
                        "WARNING")
            return f"ERROR: {exc}. You can only read files inside project/."

        if not full.exists():
            return f"ERROR: file not found: {path}"
        if full.is_dir():
            return f"ERROR: '{path}' is a directory."

        try:
            start_line = int(start_line)
            end_line = int(end_line)
        except (TypeError, ValueError):
            return "ERROR: start_line and end_line must be integers (1-based)."

        if start_line < 1:
            start_line = 1
        if end_line < start_line:
            return f"ERROR: end_line ({end_line}) < start_line ({start_line})."
        if end_line - start_line + 1 > 200:
            end_line = start_line + 199  # cap: 200 righe per chiamata

        try:
            out_lines = []
            total = 0
            with full.open("r", encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, start=1):
                    if i < start_line:
                        continue
                    if i > end_line:
                        break
                    piece = f"{i}\t{line.rstrip(chr(10))[:500]}"
                    out_lines.append(piece)
                    total += len(piece) + 1
                    if total > self.max_output:
                        out_lines.append(TRUNCATED.strip())
                        break
            if not out_lines:
                return f"(no lines in {start_line}-{end_line}: file is empty or shorter)"
            return "\n".join(out_lines)
        except Exception as e:
            return f"ERROR read_file_slice: {e}"

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
                    return f"ERROR: protected branch '{name}' cannot be deleted."

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
        return dict(TOOL_SIGNATURES)

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
    @staticmethod
    def _rename_occurrences(text: str, old: str):
        """Posizioni token NAME + occorrenze in stringhe/commenti."""
        positions = []
        text_hits = 0
        try:
            stream = io.StringIO(text).readline
            for tok in tokenize.generate_tokens(stream):
                if tok.type == tokenize.NAME and tok.string == old:
                    positions.append((tok.start[0], tok.start[1], tok.end[1]))
                elif tok.type in (tokenize.STRING, tokenize.COMMENT):
                    text_hits += len(re.findall(
                        r"\b" + re.escape(old) + r"\b", tok.string))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            positions = []
            text_hits = 0
            for row, line in enumerate(text.splitlines(), 1):
                for m in re.finditer(r"\b" + re.escape(old) + r"\b", line):
                    positions.append((row, m.start(), m.end()))
        return positions, text_hits

    def _rename_plan(self, old: str, new: str) -> list[dict]:
        """Piano di rename senza scritture: testo nuovo per ogni file."""
        plan = []
        root = Path(self.project_root)
        for path in sorted(root.rglob("*.py")):
            if any(part in _RENAME_SKIP_DIRS for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            positions, text_hits = self._rename_occurrences(text, old)
            if not positions:
                continue
            lines = text.splitlines(keepends=True)
            for row, start, end in sorted(positions, reverse=True):
                line = lines[row - 1]
                lines[row - 1] = line[:start] + new + line[end:]
            plan.append({
                "path": path,
                "rel": str(path.relative_to(root)),
                "old": text,
                "new": "".join(lines),
                "hits": len(positions),
                "text_hits": text_hits,
            })
        return plan

    @staticmethod
    def _format_rename_diff(plan: list[dict], limit: int = 160) -> list[str]:
        """Righe di diff unificato per l'anteprima del rename."""
        lines = []
        shown = 0
        for item in plan:
            lines.append(f"--- {item['rel']} ({item['hits']})")
            diff = difflib.unified_diff(
                item["old"].splitlines(), item["new"].splitlines(),
                fromfile=item["rel"], tofile=item["rel"], lineterm="")
            for line in diff:
                if shown >= limit:
                    lines.append("... (diff troncato)")
                    return lines
                lines.append(line)
                shown += 1
        return lines

    def rename_symbol(self, old_symbol: str, new_symbol: str,
                      apply: bool = False) -> str:
        """Rinomina un simbolo nei .py: default = solo anteprima.

        Usa i token NAME (non regex): stringhe e commenti non vengono toccati.
        Con `apply=True` scrive in modo transazionale e salva uno snapshot
        ripristinabile con `restore_snapshot(id)`.
        """
        try:
            valid = re.compile(r"^[A-Za-z_]\w*$")
            if (not isinstance(old_symbol, str)
                    or not isinstance(new_symbol, str)
                    or not valid.match(old_symbol)
                    or not valid.match(new_symbol)):
                return "ERROR: simboli non validi ([A-Za-z_][A-Za-z0-9_]*)."
            if old_symbol == new_symbol:
                return "ERROR: old e new sono uguali."
            apply = _as_bool(apply)

            plan = self._rename_plan(old_symbol, new_symbol)
            code_hits = sum(p["hits"] for p in plan)
            text_hits = sum(p["text_hits"] for p in plan)
            header = (f"RENAME {old_symbol} -> {new_symbol}\n"
                      f"File: {len(plan)} | occorrenze codice: {code_hits} | "
                      f"in stringhe/commenti (non toccate): {text_hits}")
            if not plan:
                return header + "\nNessuna occorrenza: nessuna modifica."

            if not apply:
                lines = ["RENAME — ANTEPRIMA (nessun file modificato)", header,
                         "Per applicare: rename_symbol(old, new, apply=True)"]
                lines.extend(self._format_rename_diff(plan))
                return "\n".join(lines)

            sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
            base = Path(self.project_root) / "state" / "refactor_snapshots" / sid
            base.mkdir(parents=True, exist_ok=True)
            manifest = {"id": sid, "old": old_symbol, "new": new_symbol,
                        "files": [p["rel"] for p in plan]}
            for item in plan:
                snap = base / item["rel"]
                snap.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item["path"], snap)
            (base / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8")

            for item in plan:
                tmp = item["path"].parent / _tmp_name(item["path"].name, ".rename")
                tmp.write_text(item["new"], encoding="utf-8")
                os.replace(tmp, item["path"])
            return (f"OK: {code_hits} occorrenze in {len(plan)} file. "
                    f"Snapshot '{sid}' — rollback: restore_snapshot('{sid}')")
        except Exception as e:
            return f"ERROR renaming symbol: {e}"

    def restore_snapshot(self, snapshot_id: str) -> str:
        """Ripristina i file di uno snapshot di rename precedente."""
        try:
            sid = str(snapshot_id).strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
                return "ERROR: snapshot_id non valido."
            root = Path(self.project_root).resolve()
            base = root / "state" / "refactor_snapshots" / sid
            manifest_path = base / "manifest.json"
            if not manifest_path.is_file():
                return f"ERROR: snapshot '{sid}' non trovato."
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            restored = 0
            for rel in manifest.get("files", []):
                source = (base / rel).resolve()
                dest = (root / rel).resolve()
                if not str(dest).startswith(str(root) + os.sep):
                    return "ERROR: percorso snapshot fuori dal progetto."
                if not source.is_file():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                restored += 1
            return f"OK: ripristinati {restored} file dallo snapshot '{sid}'."
        except Exception as e:
            return f"ERROR restore snapshot: {e}"

    # ----- 20. analyze_complexity -----
    def analyze_complexity(self, path: str) -> str:
        """Calcola una stima della complessità ciclotomatica di un file.

        Conta i punti di decisione (if, for, while, except, with, and, or).
        """
        try:
            full = safe_project_path(path, self.project_root)
            if not full.exists():
                return f"ERROR: file not found: {path}"

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

            return f"Estimated complexity: {total_complexity}\n" + \
                   ("\n".join(details[:10]) if details else "Linear code, low complexity.")
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

    # ----- 21b. find_dead_code (report-only) -----
    def find_dead_code(self, path: str = ".") -> str:
        """Report di funzioni/classi/import non referenziati: NON modifica file.

        Analisi AST deterministico. L'utente deve verificare i candidati con
        ``find_references`` prima di qualsiasi rimozione (hook e dynamic
        dispatch possono dare falsi positivi).
        """
        try:
            from CORE.dead_code import format_report, scan
            target = path if isinstance(path, str) and path.strip() else "."
            full = safe_project_path(target, self.project_root)
            findings = scan(full)
            label = target if target != "." else "."
            return format_report(findings, label)
        except Exception as e:
            return f"ERROR: ricerca codice morto fallita: {e}"

    # ----- 22. extract_method -----
    def extract_method(self, path: str, old_block: str, new_method_name: str, new_method_body: str) -> str:
        """Sposta un blocco di codice in una nuova funzione e aggiorna la chiamata.

        Sostituisce `old_block` con la chiamata `new_method_name()` e aggiunge
        la definizione di `new_method_body` alla fine del file o prima della funzione corrente.
        """
        try:
            full = safe_project_path(path, self.project_root)
            if not full.exists():
                return f"ERROR: file not found: {path}"

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

            tmp = full.parent / _tmp_name(full.name, ".extract")
            tmp.write_text(new_content, encoding="utf-8")
            os.replace(tmp, full)

            return f"OK: extracted '{new_method_name}' in {path}"
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

                # Regex per classi e funzioni (via RegexController)
                classes = _REGEX.findall("py_class", content)
                funcs = _REGEX.findall("py_def", content)

                if classes or funcs:
                    entry = f"File: {rel_path}\n"
                    if classes: entry += f"  Classes: {', '.join(classes)}\n"
                    if funcs: entry += f"  Functions: {', '.join(funcs)}\n"
                    results.append(entry)

            if not results:
                return "No classes or functions found in the project."
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
        """Esegue i test del PROGETTO del worker e restituisce un report.

        Il worker lavora su project_root (es. project/): la suite da
        eseguire è quella DEL PROGETTO, non quella del repo host (mai
        visibile dentro il sandbox). Ordine:
          1. <project_root>/tests/run_tests.py (runner JSON) se esiste
          2. altrimenti `python -m pytest -q` su <project_root>/tests
          3. altrimenti errore istruttivo
        """
        try:
            root = Path(self.project_root)
            runner_path = root / "tests" / "run_tests.py"

            if runner_path.exists():
                # 1. Runner JSON del progetto (output strutturato)
                cmd, env = sandbox.build_command(
                    self._sandbox_argv(
                        [sys.executable, str(runner_path), "--json"]),
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
                    return f"ERROR: invalid test report\n{stdout[:500]}"

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

                return report if len(report) > 15 else report + "\nAll tests passed!"

            # 2. Fallback: pytest diretto sulla suite del progetto
            tests_dir = root / "tests"
            if tests_dir.is_dir():
                out = self._run(
                    [sys.executable, "-m", "pytest", "-q",
                     str(tests_dir.relative_to(root))],
                    timeout=180, cwd=root,
                )
                # Sintesi per non saturare il contesto del worker
                lines = [ln for ln in out.splitlines() if ln.strip()]
                tail = "\n".join(lines[-12:])
                return f"PYTEST REPORT:\n{tail}"

            # 3. Nessuna suite nel progetto
            return (
                "ERROR: no tests/ directory in project "
                f"({root.name}). Crea tests/ prima di chiedere "
                "l'esecuzione della suite."
            )
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
                return f"ERROR: file not found: {path}"

            # 1. Sintassi (bloccante)
            import py_compile
            try:
                py_compile.compile(str(full), doraise=True)
            except SyntaxError as e:
                return f"SYNTAX ERROR in {path}:\n{str(e)}"

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
                    report.append("BANDIT OK: no security issues.")
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

    # ----- 13.5. diary_llm (diario di bordo LLM) -----
    def diary_llm(self, task_id: str, content: str) -> str:
        """Diario di bordo LLM (Cycle 53): scrive l'apprendimento di un task.

        L'LLM usa questo tool al termine di un task per lasciare tutto il
        necessario per risolvere/ottimizzare (problem, context, attempts,
        failures, learnings, optimization). Persistenza: state/diary/<task>.md.
        """
        try:
            if not isinstance(content, str) or len(content) > self.max_output:
                return (f"ERROR: diario troppo lungo ({len(content) if isinstance(content, str) else 0} chars)."
                        f" Max {self.max_output}.")
            task_id_safe = "".join(
                c for c in str(task_id) if c.isalnum() or c in "-_"
            )[:64] or "task"
            diary_dir = Path(self.cfg["paths"]["state_dir"]).resolve() / "diary"
            diary_dir.mkdir(parents=True, exist_ok=True)
            p = diary_dir / f"{task_id_safe}.md"
            p.write_text(
                f"# Diario LLM — task {task_id_safe}\n\n{content}\n",
                encoding="utf-8",
            )
            self.log.info(f"diary_llm: task {task_id_safe} salvato in {p}")
            return f"OK: diario salvato in {p}"
        except Exception as e:
            return f"ERROR: diario_llm failed: {e}"

    # ----- 14. patch_code -----
    def patch_code(self, path: str, old_text: str, new_text: str) -> str:
        """Modifica una porzione specifica di un file.

        Cerca l'esatta occorrenza di `old_text` e la sostituisce con `new_text`.
        Se `old_text` non è trovato esattamente, l'operazione fallisce.
        """
        try:
            full = safe_project_path(path, self.project_root)
            if not full.exists():
                return f"ERROR: file not found: {path}"

            content = full.read_text(encoding="utf-8", errors="replace")
            if old_text not in content:
                return ("ERROR: testo originale non trovato nel file. "
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

            # Gate anti-corruzione (todo 9c/M1): artefatti di escape su
            # qualunque file di testo, non solo .py.
            if detect_artifacts(new_text):
                self._audit(
                    "blocked_patch_artifact",
                    f'path="{self._q(path)}"',
                    "CRITICAL",
                )
                return ("ERROR: patch rifiutata: contiene artefatti di escape. "
                        "NON usare patch_code per correggere: riscrivi l'intero "
                        "file pulito con write_file.")

            # Robustezza #2: snapshot pre-write.
            self.snapshot_before_write(path)
            # Scrittura transazionale
            full.parent.mkdir(parents=True, exist_ok=True)
            tmp = full.parent / _tmp_name(full.name, ".patch")
            tmp.write_text(new_content, encoding="utf-8")
            os.replace(tmp, full)

            extra = self._track_python(path)
            msg = f"OK: patch applicata a {path}"
            return f"{msg}\n{extra}" if extra else msg
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

    def _sandbox_argv(self, argv: Sequence[str]) -> list[str]:
        """Mappa un argv host → argv visibile dentro il sandbox.

        `sys.executable` e i path assoluti sotto project_root NON esistono
        dentro bwrap (progetto montato in /workspace, venv in /opt/venv).
        Senza questa traduzione bandit/mypy/run_test_suite falliscono con
        "bwrap: execvp ... No such file or directory".
        """
        root = Path(self.project_root).resolve()
        out: list[str] = []
        for i, a in enumerate(argv):
            s = str(a)
            if i == 0 and (s == sys.executable or s.startswith(sys.prefix)):
                out.append(sandbox.python_executable())
                continue
            p = Path(s)
            if p.is_absolute():
                try:
                    rel = p.resolve().relative_to(root)
                    out.append(f"{sandbox.WORKSPACE}/{rel.as_posix()}")
                    continue
                except (ValueError, OSError):
                    pass
            out.append(s)
        return out

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

        # 3. Sandbox opzionale: se disabilitato, esegui direttamente
        sandbox_enabled = self.cfg.get("safety", {}).get("sandbox_enabled", True)
        if not sandbox_enabled:
            try:
                proc = subprocess.Popen(
                    argv,
                    cwd=str(cwd or self.project_root),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    start_new_session=True,
                    preexec_fn=self._preexec(timeout),
                )
                stdout, stderr = proc.communicate(timeout=timeout)
                stdout = self._truncate(stdout or "")
                stderr = self._truncate(stderr or "")
                return (
                    f"exit_code={proc.returncode}\n"
                    f"--- stdout ---\n{stdout}\n"
                    f"--- stderr ---\n{stderr}"
                )
            except Exception as e:
                return f"ERROR: {e}"

        try:
            workdir = sandbox.sandbox_workdir(cwd, self.project_root)
            cmd, env = sandbox.build_command(
                self._sandbox_argv(argv), self.project_root, workdir=workdir,
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
        if validate_chars(ref, "ref"):
            return ref
        return None
