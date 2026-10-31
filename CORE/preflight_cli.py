"""
preflight_cli.py — CLI di preflight per la GUI (work order T1 + T4).

La GUI lancia questo script via QProcess (mai bloccante nel main thread):

    python CORE/preflight_cli.py "<prompt>" [--type <tipo>] [--context "<ctx>"]

Scrivendo su stdout UNA riga JSON:
    {"status": "queued", "task_id": "..."}
    {"status": "needs_revision", "reason": "..."}
    {"ok": false, "error": "..."}          (problema interno)

Il gate e' deterministico (zero token LLM): la consultazione del decision
model e' disattivata nel path CLI (validator senza decision_client).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from CORE.decision_feedback import DecisionValidator  # noqa: E402
from CORE.orchestrator import TaskQueue  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight check task")
    parser.add_argument("prompt", help="testo libero dal prompt dell'utente")
    parser.add_argument("--type", default="code",
                        help="tipo del task (default: code)")
    parser.add_argument("--context", default="")
    args = parser.parse_args()

    log = logging.getLogger("preflight-cli")
    log.addHandler(logging.NullHandler())

    result = {"ok": False, "error": "unknown"}
    try:
        queue = TaskQueue(BASE_DIR / "tasks", log)
        validator = DecisionValidator(queue, decision_client=None)
        result = validator.validate(
            args.prompt,
            {
                "type": args.type,
                "description": args.prompt,
                "context": args.context[:2000],
            },
        ).as_dict()
        result.setdefault("ok", result.get("status") == "queued")
    except Exception as e:  # mai traceback crudo su stdout
        result = {"ok": False, "error": str(e)[:200]}

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
