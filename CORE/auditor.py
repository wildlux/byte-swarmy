"""
CORE/auditor.py — Audit Worker (The Reviewer).

Estratto da CORE/orchestrator.py per ridurre il monolite.

Revisione del codice prodotto dal worker: sicurezza, clean code, verifica.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Callable, Optional

from CORE.constants import DEFAULT_NUM_CTX
from CORE.ollama_client import ModelClient

log = logging.getLogger("byte-swarmy.auditor")


class AuditWorker:
    """
    The Reviewer: An agent specialized in cross-checking code for security,
    bugs, and architectural consistency.
    """

    SYSTEM = (
        "You are the Senior Audit Worker (The Reviewer) and a Clean Code Expert.\n"
        "Your goal is to ensure enterprise-grade quality, security, and maintainability.\n\n"
        "### 🛡️ SECURITY CRITERIA (IMMEDIATE REJECT)\n"
        "1. No `eval()`, `exec()`, unsafe `pickle`, or shell injections.\n"
        "2. No hardcoded secrets or absolute paths.\n"
        "3. No bypass of sandbox rules.\n\n"
        "### 🧼 CLEAN CODE CRITERIA (REJECT IF VIOLATED)\n"
        "1. SINGLE RESPONSIBILITY: Functions must do one thing. If a function exceeds 20-25 lines, REJECT and ask for `extract_method`.\n"
        "2. NAMING: Variables and functions must have descriptive names (e.g., `user_timeout` instead of `ut`).\n"
        "3. COGNITIVE LOAD: No deep nesting. If you see more than 3 levels of indentation, REJECT and ask for 'Guard Clauses'.\n"
        "4. DRY: No duplicated logic. If the same code appears twice, suggest a helper function.\n"
        "5. DOCUMENTATION: Every public function MUST have a docstring and type hints.\n\n"
        "### 🧪 VERIFICATION\n"
        "1. Did the worker run `run_test_suite` and `lint_code`?\n"
        "2. Did all tests pass? If not = REJECT.\n\n"
        "### 📩 RESPONSE FORMAT\n"
        "Respond ONLY with a JSON object:\n"
        '{"decision": "APPROVE" | "REJECT", "feedback": "be specific: mention line numbers or function names", "severity": "LOW" | "MEDIUM" | "HIGH"}\n\n'
        "Be a strict mentor. Guide the worker toward professional excellence."
    )

    def __init__(
        self,
        model_client: ModelClient,
        logger,
        decision_client: Optional[Callable[[str, str, str, float, int, int], str]] = None,
        config: Optional[dict] = None,
    ):
        self.models = model_client
        self.log = logger
        self.decision_client = decision_client
        # 🆕 C: gate deterministico (config-gated, default OFF per non
        # cambiare comportamento a config esistenti senza la chiave).
        cfg = config or {}
        self.deterministic_gate = bool(
            cfg.get("audit", {}).get("deterministic_gate", False))

    def audit(
        self,
        task: dict,
        worker_result: str,
        worker_history: list,
        model_name: str = "tev1:4b",
        temperature: float = 0.1,
        num_ctx: int = DEFAULT_NUM_CTX,
        max_tokens: int = 500,
        project_path: Optional[str] = None,
        started_at: Optional[float] = None,
    ) -> dict:
        """Review worker output for the task.

        Returns {"decision": "APPROVE" | "REJECT", "feedback": str, "severity": "LOW"|"MEDIUM"|"HIGH"}.
        """
        useful_tools = {"write_file", "patch_code", "run_test_suite", "lint_code",
                       "git_commit", "rename_symbol", "extract_method"}
        useful_count = 0
        for event in worker_history:
            if event.get("type") == "tool_result":
                content = event.get("content", "")
                for tool in useful_tools:
                    if f"tool {tool}(" in content or f"{tool}(" in content:
                        useful_count += 1
                        break

        if useful_count > 0:
            return {"decision": "APPROVE",
                   "feedback": f"auto-approved ({useful_count} useful tool calls)",
                   "severity": "LOW"}

        # 🆕 C: gate deterministico PRIMA dell'audit LLM. Il LLM gira solo
        # quando NESSUN tool utile è stato chiamato (il caso comune con
        # write_file/patch_code è già auto-APPROVE senza LLM). Se i file
        # scritti durante il task:
        #   - compilano (AST)   → APPROVE senza spendere la chiamata LLM;
        #   - hanno SyntaxError → REJECT con l'errore VERO nel feedback
        #     (il loop di correzione riceve riga+messaggio esatti invece
        #     della parafrasi vaga di un LLM).
        # Se nessun file è stato scritto (task di risposta/analisi) →
        # prosegui con l'audit LLM come prima (None = gate non applicable).
        if self.deterministic_gate and project_path and started_at:
            det = self._deterministic_check(project_path, started_at)
            if det is not None:
                self.log.info(f"deterministic audit gate: {det['decision']}")
                return det

        # Fallback: usa il decision model LLM per review codice
        system_prompt = ("You are a senior code reviewer. Review the following "
                         "worker result for security, correctness, and clean code. "
                         "Respond ONLY with valid JSON: "
                         '{"decision": "APPROVE" | "REJECT", "feedback": "string", "severity": "LOW"|"MEDIUM"|"HIGH"}')

        user_prompt = f"Task: {task.get('title','unknown')}\n\n"
        user_prompt += f"Worker result: {worker_result[:3000]}\n\n"
        user_prompt += "Review this output and decide APPROVE or REJECT."

        if self.decision_client is not None:
            try:
                raw = self.decision_client(
                    model_name=model_name,
                    prompt=user_prompt,
                    system=system_prompt,
                    temperature=temperature,
                    num_ctx=num_ctx,
                    max_tokens=max_tokens,
                )
                parsed = json.loads(raw)
                if parsed.get("decision") in ("APPROVE", "REJECT"):
                    return {
                        "decision": parsed["decision"],
                        "feedback": parsed.get("feedback", ""),
                        "severity": parsed.get("severity", "LOW")
                    }
            except Exception as e:
                self.log.warning(f"LLM audit failed: {e}")

        # Fallback heuristic
        return {"decision": "REJECT",
               "feedback": "No useful tools called and LLM review unavailable.",
               "severity": "HIGH"}

    # ------------------------------------------------------------------
    # 🆕 C: gate deterministico (AST, zero LLM)
    # ------------------------------------------------------------------

    # Directory che non contano come "artifact del task"
    _SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "ENV",
                  "node_modules", "state", "tasks", "logs", "backups",
                  ".pytest_cache", ".mypy_cache", ".ruff_cache"}

    def _deterministic_check(self, project_path: str,
                             started_at: float) -> Optional[dict]:
        """Verifica deterministica dei file scritti DURANTE il task.

        Scansiona project_path cercando file con mtime >= started_at
        (l'istante del claim del task), poi AST-parsa i .py tra questi.

        Returns:
            None   → nessun file recente: gate non applicable, prosegui
                     con l'audit LLM (es. task di risposta senza artifact).
            dict   → decisione APPROVE/REJECT deterministica.
        """
        if not started_at:
            return None
        root = Path(project_path)
        if not root.is_dir():
            return None
        recent_py: list[Path] = []
        recent_any = 0
        try:
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                rel = p.relative_to(root)
                if any(part in self._SKIP_DIRS for part in rel.parts):
                    continue
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    continue
                if mtime < started_at:
                    continue
                recent_any += 1
                if p.suffix == ".py":
                    recent_py.append(p)
        except Exception as e:
            self.log.debug(f"deterministic gate scan fallita: {e}")
            return None  # fail-open: LLM come prima

        if recent_any == 0:
            return None  # nessun artifact scritto → audit LLM come prima

        errors: list[str] = []
        for p in recent_py:
            try:
                ast.parse(p.read_text(encoding="utf-8", errors="replace"),
                          filename=str(p))
            except SyntaxError as e:
                errors.append(f"{p.name}: {e.msg} (riga {e.lineno})")
            except (OSError, ValueError) as e:
                errors.append(f"{p.name}: {e}")
        if errors:
            return {"decision": "REJECT",
                    "feedback": "deterministic gate — SyntaxError nei file "
                                "scritti: " + "; ".join(errors[:3]),
                    "severity": "HIGH"}
        return {"decision": "APPROVE",
                "feedback": f"deterministic gate: {recent_any} file scritti, "
                            f"{len(recent_py)} .py AST OK",
                "severity": "LOW"}
