"""
constants.py — Central repository for all system constants and enums.
No logic here, only data.
"""
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    RETRY = "retry"
    STUCK = "stuck"
    NEEDS_HUMAN = "needs_human"
    PLANNED = "planned"

class TaskType(Enum):
    IMPLEMENT = "implement"
    TEST = "test"
    FIX = "fix"
    EXECUTE = "execute"
    GENERIC = "generic"
    DOCUMENT = "document"

class ThermalState(Enum):
    FAST = "FAST"
    NORMAL = "NORMAL"
    SLOW = "SLOW"
    PAUSE = "PAUSE"

class AuditDecision(Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"

class Severity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# Default Paths (fallback if not in config)
DEFAULT_PATHS = {
    "project_root": "./project",
    "state_dir": "./state",
    "tasks_dir": "./tasks",
    "logs_dir": "./logs",
    "backups_dir": "./backups",
}

# Safety Thresholds
SAFETY_THRESHOLDS = {
    "swap_threshold": 0.8,
    "disk_free_threshold": 1 * 1024**3, # 1 GB
    "cpu_critical_threshold": 95.0,
}


# ═══════════════════════════════════════════════════════════════
# Attori: modello di default per peso (H3/H4)
# ═══════════════════════════════════════════════════════════════
# Unica fonte per CORE e GUI: il Timestral è SEMPRE "light" e SEMPRE su
# CPU (force_cpu) — è il gatekeeper termico, deve restare reattivo.

ACTOR_WEIGHT_DEFAULT_MODELS = {
    "llm": {
        "light":  "qwen2.5:1.5b",       # ~1GB RAM, per task semplici
        "medium": "qwen2.5:3b",         # ~2GB RAM, bilanciato
        "heavy":  "llama3:8b",          # ~5GB VRAM, per task complessi
    },
    "decision_model": {
        "light":  "qwen2.5:1.5b",       # veloce, per decisioni semplici
        "medium": "qwen2.5:3b",         # bilanciato, ragionamento medio
        "heavy":  "qwen2.5:7b",         # ragionamento complesso
    },
    "timestral": {
        # Timestral: SOLO light — gatekeeper in RAM su CPU (H4)
        "light":  "qwen2.5:0.5b",       # ~350MB, polling leggero
        "medium": "qwen2.5:0.5b",       # forzato a light
        "heavy":  "qwen2.5:0.5b",       # forzato a light
    },
}

# Attori che NON vanno MAI su GPU (indipendentemente dalla VRAM libera)
ACTOR_FORCE_CPU = frozenset({"timestral"})


def weight_default_model(actor: str, weight: str) -> str:
    """Ritorna il modello di default per (attore, peso)."""
    return ACTOR_WEIGHT_DEFAULT_MODELS.get(actor, {}).get(weight, "qwen2.5:1.5b")


# ═══════════════════════════════════════════════════════════════════
# Ollama host — fonte unica (19 occorrenze sostituite da questa costante)
# ═══════════════════════════════════════════════════════════════════
OLLAMA_HOST = "http://localhost:11434"


# ═══════════════════════════════════════════════════════════════════
# LLM context default — fonte unica (almeno 6 occorrenze sostituite)
# ═══════════════════════════════════════════════════════════════════
DEFAULT_NUM_CTX = 4096


# ═══════════════════════════════════════════════════════════════════
# Stile pulsante trasparente condiviso (36 occorrenze in GUI/*)
# ═══════════════════════════════════════════════════════════════════
BTN_TRANSPARENT_STYLE = (
    "QPushButton { font-size:16px; border:none; background:transparent; "
    "border-radius:4px; padding:0; }"
    "QPushButton:hover { background:#e2e8f0; border-radius:4px; }"
)

BTN_TRANSPARENT_DANGER_STYLE = (
    "QPushButton { font-size:16px; border:none; background:transparent; "
    "border-radius:4px; padding:0; }"
    "QPushButton:hover { background:#fee2e2; border-radius:4px; }"
)

BTN_TRANSPARENT_SMALL_STYLE = (
    "QPushButton { font-size:13px; border:none; background:transparent; "
    "border-radius:4px; padding:0; }"
    "QPushButton:hover { background:#e2e8f0; border-radius:4px; }"
)

BTN_TRANSPARENT_MEDIUM_STYLE = (
    "QPushButton { font-size:14px; border:none; background:transparent; "
    "border-radius:4px; padding:0; }"
    "QPushButton:hover { background:#e2e8f0; border-radius:4px; }"
)
