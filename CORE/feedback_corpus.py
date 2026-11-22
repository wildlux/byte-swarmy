"""CORE/feedback_corpus.py — corpus di feedback (Fase B).

Ogni task termina in una tripla (prompt/output/verdetto) che diventa
carburante per il training futuro (QLoRA STaR, Fase C). Collezione passiva
e deterministica: niente LLM qui, solo scrittura di log.

Formato per task: `state/feedback_corpus/<task_id>.jsonl` (one line per
tripla, JSON). Una task può produrne più di una se corretta.

Zero rete, zero LLM, zero I/O oltre lo state dir.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]")

# A2 (2026-11-22): reason popolato dal prompt correttivo, con cap esplicito.
MAX_REASON_CHARS = 4000
VALID_VERDICTS = frozenset({"done", "corrected", "failed_definitively"})


def clamp_reason(text) -> str:
    """Normalizza e tronca il `reason` di una triple a MAX_REASON_CHARS."""
    return " ".join(str(text or "").split())[:MAX_REASON_CHARS]


def failure_triple(task: dict, reason: str, attempts: int = 1,
                   model: str = "", correction: str = "",
                   state_dir: Optional[str | Path] = None) -> Triple:
    """Tripla `failed_definitively` con reason dal prompt correttivo (A2).

    Scrittura passiva e fail-open: il calling code la avvolge in try/except.
    """
    task = task if isinstance(task, dict) else {}
    ctx = task.get("context")
    refs = tuple(
        (ctx.get("refs") or ()) if isinstance(ctx, dict) else ()
    )
    return append_triple(Triple(
        task_id=str(task.get("id") or "?"),
        kind=str(task.get("type") or "code"),
        title=str(task.get("title") or ""),
        description=str(task.get("description") or ""),
        refs=refs,
        output=clamp_reason(reason),
        verdict="failed_definitively",
        first_try=attempts <= 1,
        attempts=max(1, int(attempts)),
        model=str(model or ""),
        reason=clamp_reason(correction or reason),
        ts=time.time(),
    ), state_dir=state_dir)


@dataclass(frozen=True)
class Triple:
    task_id: str
    kind: str
    title: str
    description: str
    refs: tuple
    output: str
    verdict: str        # "done" | "corrected"
    first_try: bool
    attempts: int
    model: str
    reason: str
    ts: float

    def to_dict(self) -> dict:
        return asdict(self)

    def dedup_key(self) -> str:
        """Hash della tripla di lavoro: task + prompt + output."""
        raw = json.dumps({
            "task": self.task_id,
            "description": self.description,
            "refs": list(self.refs),
            "output": self.output,
            "verdict": self.verdict,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def task_id_safe(task_id: str) -> str:
    return (_SAFE_ID.sub("_", str(task_id)) or "task")[:64]


def task_path(task_id: str, state_dir: Optional[str | Path] = None) -> Path:
    base = Path(state_dir) if state_dir is not None else (
        Path(__file__).resolve().parent.parent / "state")
    return Path(base) / "feedback_corpus" / f"{task_id_safe(task_id)}.jsonl"


def append_triple(triple: Triple, state_dir: Optional[str | Path] = None) -> Path:
    p = task_path(triple.task_id, state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(triple.to_dict(), ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return p


def load_task(task_id: str, state_dir: Optional[str | Path] = None) -> list[Triple]:
    p = task_path(task_id, state_dir)
    if not p.exists():
        return []
    samples: list[Triple] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                samples.append(Triple(
                    task_id=d.get("task_id", task_id),
                    kind=str(d.get("kind") or "code"),
                    title=str(d.get("title") or ""),
                    description=str(d.get("description") or ""),
                    refs=tuple(d.get("refs") or ()),
                    output=str(d.get("output") or ""),
                    verdict=str(d.get("verdict") or "done"),
                    first_try=bool(d.get("first_try")),
                    attempts=int(d.get("attempts") or 1),
                    model=str(d.get("model") or ""),
                    reason=str(d.get("reason") or ""),
                    ts=float(d.get("ts") or 0.0),
                ))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue  # linea corrotta: skip senza crashare il corpus
    return samples


def dedupe(samples: Iterable[Triple]) -> list[Triple]:
    """Una sola tripla per contenuto lavorato (hash), mantenendo l'ordine."""
    seen: set[str] = set()
    out: list[Triple] = []
    for t in samples:
        key = t.dedup_key()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def stats(samples: Iterable[Triple]) -> dict:
    all_samples = list(samples)
    unique = dedupe(all_samples)
    done = sum(1 for t in all_samples if t.verdict == "done")
    corrected = sum(1 for t in all_samples if t.verdict == "corrected")
    return {
        "samples": len(all_samples),
        "unique": len(unique),
        "done": done,
        "corrected": corrected,
        "correction_rate": round(corrected / len(all_samples), 3) if all_samples else 0.0,
    }
