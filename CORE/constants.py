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
