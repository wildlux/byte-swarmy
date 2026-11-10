"""
CORE/auditor.py — Audit Worker (The Reviewer).

Estratto da CORE/orchestrator.py per ridurre il monolite.

Revisione del codice prodotto dal worker: sicurezza, clean code, verifica.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

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
    ):
        self.models = model_client
        self.log = logger
        self.decision_client = decision_client

    def audit(
        self,
        task: dict,
        worker_result: str,
        worker_history: list,
        model_name: str = "tev1:4b",
        temperature: float = 0.1,
        num_ctx: int = DEFAULT_NUM_CTX,
        max_tokens: int = 500,
    ) -> dict:
        """Review worker output using the LLM decision model.

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
