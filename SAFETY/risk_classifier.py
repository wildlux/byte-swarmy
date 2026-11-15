"""Classificatore di rischio deterministico (Cycle 56).

Nessun LLM al passaggio: le decisioni di rischio sono presi da regole
statiche e deterministiche su:
  - task type / hint testuali (refactoring, cambio API pubblica, ...);
  - path toccati (SAFETY/, CORE/sandbox.py, CORE/tools.py, CONFIG/ ...);
  - dimensione del diff (righe > 50 o > 3 file toccati → alto).

Livelli prodotti: low | medium | high | critical.
`high`/`critical` → il task viene messo in stato `awaiting_human_approval`
dall'orchestrator (gate umano) — l'Audit Worker LLM NON è affidabile per
decisioni di rischio (è un modello piccolo, può essere ingannato o confuso).
"""

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

# Path che, se toccati da un diff, alzano il rischio di sicurezza.
CRITICAL_PATHS = (
    "SAFETY/",
    "CORE/sandbox.py",
    "CORE/tools.py",
    "CONFIG/",
)

# Parole chiave che indicano refactoring/architettura/API change.
ARCHITECTURAL_KEYWORDS = (
    "refactor",
    "architettura",
    "architectural",
    "api",
    "breaking",
    "riarchitettura",
    "refactoring",
)
ARCHITECTURAL_TASK_TYPES = ("refactor", "architectural", "riarchitettura")

# Dimensione massima di un diff "piccolo" prima di alzare il rischio.
MAX_LOW_DIFF_LINES = 50
MAX_LOW_DIFF_FILES = 3


def _is_critical_path(path: str) -> bool:
    """True se il path toccato cade in una zona critica del sistema."""
    p = str(path).replace("\\", "/").strip()
    if not p:
        return False
    critical_exact = tuple(
        x for x in CRITICAL_PATHS if not x.endswith("/")
    )
    if p in critical_exact or p.startswith(CRITICAL_PATHS):
        return True
    return False


def is_architectural(task: dict) -> bool:
    """True se il task e' refactoring/architettura/cambio API pubblica."""
    ttype = str(task.get("type") or task.get("task_type") or "generic").lower()
    text = f"{task.get('title') or ''} {task.get('description') or ''} ".lower()
    if ttype in ARCHITECTURAL_TASK_TYPES:
        return True
    return any(k in text for k in ARCHITECTURAL_KEYWORDS)


def classify(task: dict, touched_paths=None, diff_lines: int = 0,
             diff_files: int = 0) -> dict:
    """Classifica il rischio di un task in modo deterministico.

    Args:
        task: dict con almeno title/description/type (lo stesso shape del task).
        touched_paths: path toccati dal diff (opzionale; pre-esecuzione spesso
                       e' vuoto e si valuta solo type/keywords).
        diff_lines: numero di righe aggiunte/modificate nel diff (0 se ignoto).
        diff_files: numero di file toccati nel diff (0 se ignoto).

    Returns:
        dict con chiave "level" in {low, medium, high, critical} e "reasons".
    """
    level = RISK_MEDIUM
    reasons: list[str] = []

    ttype = str(task.get("type") or task.get("task_type") or "generic").lower()
    text = f"{task.get('title') or ''} {task.get('description') or ''} ".lower()
    touched = [str(p) for p in (touched_paths or [])]

    critical_hits = [p for p in touched if _is_critical_path(p)]
    arch = is_architectural(task)

    if critical_hits:
        level = RISK_CRITICAL if arch else RISK_HIGH
        reasons.append(f"critical_paths={critical_hits[0]}")

    if arch:
        level = RISK_CRITICAL if level == RISK_CRITICAL else RISK_HIGH
        reasons.append(f"architectural_task={ttype or 'unknown'}")

    if diff_lines > MAX_LOW_DIFF_LINES or diff_files > MAX_LOW_DIFF_FILES:
        if level in (RISK_LOW, RISK_MEDIUM):
            level = RISK_HIGH
        reasons.append(f"diff_size={diff_lines}lines/{diff_files}files")

    return {"level": level, "reasons": reasons, "task_type": ttype}


def requires_human(level: str) -> bool:
    """True se il task ad alto rischio richiede approvazione umana."""
    return str(level).lower() in (RISK_HIGH, RISK_CRITICAL)
