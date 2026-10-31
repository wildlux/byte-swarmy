"""
decision_feedback.py — Pre-flight check dei parametri del task + persistenza.

Ordine di esecuzione (vincolo.DoD): il gate deterministico gira PRIMA di
qualsiasi consultazione LLM, cosi' un errore formale costa zero token.
Solo se i parametri superano il gate viene chiesto un parere (JSON
conciso) al decision model attivo; un modello non disponibile non blocca
l'accodamento.

Ogni stringa inviata al decision model e' troncata a MAX_PROMPT_CHARS
(500) per il vincolo globale di contesto dei modelli piccoli.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# workspace-relative: DATABASE/decision_feedback.db
DATABASE_DIR = Path("DATABASE")
DEFAULT_DB_PATH = DATABASE_DIR / "decision_feedback.db"

# Constraint globale del work order: nessun prompt > 500 caratteri
MAX_PROMPT_CHARS = 500

# "code" e' lo pseudo-type usato dalla GUI/INTENT; il resto viene da TaskType
try:
    from CORE.constants import TaskType
    _ALLOWED_TYPES = {t.value for t in TaskType} | {"code"}
except ImportError:  # test isolato senza pacchetto completo
    _ALLOWED_TYPES = {
        "implement", "test", "fix", "execute", "generic", "document", "code"
    }

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decision_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    original_prompt TEXT NOT NULL,
    invalid_parameters JSON NOT NULL,
    decision_reason TEXT NOT NULL,
    user_corrected BOOLEAN NOT NULL DEFAULT 0
);
""".strip()


@dataclass(frozen=True)
class ValidationResult:
    """Esito del preflight (typing richiesto dal work order)."""

    status: str                      # "queued" | "needs_revision"
    reason: str = ""
    task_id: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionValidator:
    """Preflight deterministico + feedback su SQLite.

    Il decision model NON viene consultato:
    - quando il gate deterministico gi a' scarta i parametri (0 token);
    - quando non configurato (determinista-puro, casi fallback).

    SQLite: query SEMPRE parametrizzate (?). SQLite non supporta
    engine.async: le chiamate restano sincrone nel thread gi a' periferico
    (worker/dispatcher o processo CLI della GUI, mai nel main thread).
    """

    def __init__(self,
                 queue: Any,
                 decision_client: Optional[Callable[[str], Optional[dict]]] = None,
                 db_path: Path = DEFAULT_DB_PATH):
        self.queue = queue
        self.decision_client = decision_client
        self.db_path = Path(db_path)
        self._ensure_schema()

    # -- Database ------------------------------------------------------------
    def _ensure_schema(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(_SCHEMA)
        except sqlite3.Error:
            pass    # schema gia' presente o disco non pronto: retry al prossimo uso

    def _insert_feedback(self, prompt: str, params: dict, reason: str) -> None:
        """INSERT atomico su decision_feedback (SQL parametrizzato)."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "INSERT INTO decision_feedback "
                    "(timestamp, original_prompt, invalid_parameters, "
                    " decision_reason, user_corrected) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (
                        time.strftime("%Y-%m-%dT%H:%M:%S"),
                        prompt[:MAX_PROMPT_CHARS],
                        json.dumps(params, ensure_ascii=False)[:2000],
                        str(reason)[:500],
                    ),
                )
        except sqlite3.Error:
            pass    # feedback persistente fallito: NON deve bloccare il flusso

    def count_feedback(self) -> int:
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM decision_feedback"
                ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error:
            return 0

    # -- Validazione ----------------------------------------------------------
    def _deterministic_check(self, params: dict) -> Optional[str]:
        """Gate veloce e gratuito: None se valido, else reason."""
        ptype = str(params.get("type", "code"))
        title = str(params.get("title", ""))
        description = str(params.get("description", ""))
        context = str(params.get("context", ""))

        if ptype not in _ALLOWED_TYPES:
            return (f"type non valido: {ptype!r} "
                    f"(consentiti: {sorted(_ALLOWED_TYPES)})")
        if not title.strip():
            return "title vuoto o mancante"
        if len(title) > 160:
            return "title oltre 160 caratteri (clean del prompt)"
        if not description.strip():
            return "description vuota o mancante"
        if len(description) > 4000:
            return "description oltre 4000 caratteri (clean del prompt)"
        if len(context) > 2000:
            return "context oltre 2000 caratteri"

        # params["paths"]: i path devono stare in project/
        for p in params.get("paths", []) or []:
            s = str(p)
            if s.startswith(("/", "~")) or ".." in Path(s).parts:
                return f"path fuori da project/: {s!r}"

        return None

    def validate(self, prompt: str,
                 params: Optional[dict] = None,
                 task: Optional[dict] = None) -> ValidationResult:
        """Valida e, se valido, accoda il task.

        Args:
            prompt: input libero dell'utente (mono-linea o multilinea).
            params: versione strutturata (type/title/description/context/...).
            task: task di partenza completo (task_id presente gia' non
                rilevante qui: il validated copre l'intero task).

        Returns:
            ValidationResult con status "queued" o "needs_revision".
        """
        params = dict(params or {})
        params.setdefault("type", "code")
        params.setdefault("title", str(prompt or "")[:160])
        params.setdefault("description", str(prompt or ""))

        # 1) gate deterministico: 0 token
        reason = self._deterministic_check(params)
        if reason:
            self._insert_feedback(prompt, params, reason)
            return ValidationResult("needs_revision", reason=reason)

        # 2) parere del decision model (se configurato; prompt troncato)
        if self.decision_client is not None:
            try:
                verdict = self.decision_client(str(prompt)[:MAX_PROMPT_CHARS])
                if isinstance(verdict, dict) and not verdict.get("valid", True):
                    dm_reason = str(verdict.get("reason",
                                                "decision model: invalid"))
                    self._insert_feedback(prompt, params, dm_reason)
                    return ValidationResult("needs_revision", reason=dm_reason)
            except Exception:
                pass    # decision model down: fallback deterministico ok

        # 3) accodamento: solo qui
        task_id = self.queue.add({
            "title": str(params["title"])[:160],
            "description": str(params["description"])[:4000],
            "context": str(params.get("context", ""))[:2000],
            "type": str(params["type"]),
        })
        return ValidationResult("queued", task_id=task_id)


def validate_task_parameters(prompt: str, params: dict,
                             validator: DecisionValidator) -> dict:
    """API richiesta dal work order: forma dict ESATTA."""
    return validator.validate(prompt, params).as_dict()
