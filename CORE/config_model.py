"""
config_model.py — Configurazione tipizzata con dataclass.

Motivazione: oggi `config.toml` viene caricato come dizionario grezzo e passato
in giro come `config["ollama"]["host"]`, `config["paths"]["project_root"]`,
ecc. È facile sbagliare una chiave e ottenere `KeyError` in runtime.

Questo modulo fornisce:
  - Dataclass tipizzate per le sezioni di config più usate (ollama, paths,
    security, orchestrator, thermal, timing, routing, safety).
  - `load_typed_config(path)` — legge il TOML e popola le dataclass.
  - `to_dict()` su ogni dataclass per retrocompatibilità con il codice che
    aspetta ancora un dict.

Nessun modulo esistente è obbligato a migrare subito: il modulo serve come
fonte tipizzata per il nuovo codice e per la migrazione graduale.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from CORE.constants import OLLAMA_HOST, DEFAULT_NUM_CTX

# Python 3.11+ ha tomllib, fallback a tomli
try:
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


def _load_toml(path: Path) -> dict:
    if tomllib is None:
        raise RuntimeError("serve Python 3.11+ o `pip install tomli` per leggere TOML")
    with open(path, "rb") as f:
        return tomllib.load(f)


# ═══════════════════════════════════════════════════════════════════
# Dataclass per sezione
# ═══════════════════════════════════════════════════════════════════


@dataclass
class OllamaConfig:
    host: str = OLLAMA_HOST
    request_timeout: int = 300


@dataclass
class ModelConfig:
    name: str = ""
    temperature: float = 0.1
    top_p: float = 0.8
    top_k: int = 40
    repeat_penalty: float = 1.1
    repeat_last_n: int = 256
    num_ctx: int = 2048
    num_predict: int = 256
    seed: Optional[int] = None
    enabled: bool = True


@dataclass
class ModelsConfig:
    orchestrator: ModelConfig = field(default_factory=ModelConfig)
    planner: ModelConfig = field(default_factory=ModelConfig)
    worker_coder: ModelConfig = field(default_factory=ModelConfig)
    worker_general: ModelConfig = field(default_factory=ModelConfig)
    embedding: ModelConfig = field(default_factory=ModelConfig)
    extra: Dict[str, ModelConfig] = field(default_factory=dict)


@dataclass
class ThermalConfig:
    enabled: bool = True
    sample_interval: int = 30
    history_max: int = 2880
    temp_cold: float = 50.0
    temp_warm: float = 65.0
    temp_hot: float = 80.0
    temp_critical: float = 90.0
    gpu_temp_warm: float = 80.0
    gpu_temp_hot: float = 85.0
    gpu_temp_critical: float = 95.0
    cpu_pause_threshold: float = 0.95


@dataclass
class TimingConfig:
    orchestrator_tick: int = 30
    worker_tick: int = 60
    health_check: int = 300
    git_snapshot: int = 999999
    memory_compaction: int = 3600
    backup_complete: int = 86400
    model_unload_idle: int = 120


@dataclass
class SafetyConfig:
    sandbox_enabled: bool = True
    max_attempts: int = 10
    max_consecutive_failures: int = 3
    cooldown_after_failure: int = 120
    swap_threshold: float = 0.95
    disk_free_threshold: int = 1000000000
    max_log_size: int = 10000000
    heartbeat_timeout: int = 300
    max_tasks_per_agent_per_hour: int = 20
    memory_compaction_threshold: int = 50


@dataclass
class SecurityConfig:
    enabled: bool = True
    max_output_chars: int = 10000
    max_file_size_write: int = 2000000
    max_file_size_bytes: int = 50000000
    max_memory_mb: int = 1536


@dataclass
class RoutingConfig:
    confidence_threshold: float = 0.65
    max_files_per_task: int = 8
    max_file_size_readable: int = 50000
    timeout_bash: int = 30
    worker_coder_keywords: List[str] = field(default_factory=list)
    worker_general_keywords: List[str] = field(default_factory=list)


@dataclass
class PathsConfig:
    project_root: str = "./project"
    state_dir: str = "./state"
    tasks_dir: str = "./tasks"
    logs_dir: str = "./logs"
    backups_dir: str = "./backups"
    git_dir: str = "./project"


@dataclass
class LoggingConfig:
    level: str = "DEBUG"
    file: str = "./logs/byte-swarmy.log"


@dataclass
class DecisionModelConfig:
    name: str = ""
    enabled: bool = False
    temperature: float = 0.1
    num_ctx: int = DEFAULT_NUM_CTX


@dataclass
class DecisionModelsConfig:
    active: str = ""
    extra: Dict[str, DecisionModelConfig] = field(default_factory=dict)


@dataclass
class GenericTaskPlannerConfig:
    enabled: bool = True
    max_subtasks: int = 8
    max_tokens: int = 1500
    system_prompt: str = ""


@dataclass
class HardwareConfig:
    mode: str = "auto"
    worker_count: Optional[int] = None
    keep_alive_sec: Optional[int] = None
    strategy: Optional[str] = None


@dataclass
class AuditGatesConfig:
    enabled: bool = False
    mode: str = "advisory"
    target: str = "auto"
    categories: List[str] = field(default_factory=list)


@dataclass
class SMLBestConfig:
    """Configurazione ottimizzata per modelli SML (Small Language Models, <= 7B).

    Valori determinati empiricamente tramite test su 20 modelli Ollama <= 7B.
    Modelli promossi: qwen2.5:1.5b, qwen2.5-coder:1.5b, phi3:mini, qwen3:1.7b,
    qwen2.5-coder:3b, llama3.2:latest, phi3:3.8b, granite4:1b, translategemma:4b,
    qwen2.5vl:3b, llama3.2:3b, codellama:7b.

    Regola FSM (Finite State Machine) nel system prompt:
    - TENERE la tabella degli stati piccola (3-5 stati, 3-4 transizioni)
    - Usare etichette semplici (S0, S1, S2)
    - Mettere la tabella PRIMA delle istruzioni nel system prompt
    """
    temperature: float = 0.1
    num_ctx: int = 2048
    num_predict: int = 512
    repeat_penalty: float = 1.15
    seed: int = 42
    modello_consigliato: str = "qwen2.5:1.5b"
    system_prompt_versione: str = "v3.1"
    fsm_max_stati: int = 5
    fsm_max_transizioni: int = 4

@dataclass
class GUISettingsConfig:
    """Preferenze GUI utente."""
    icon_text_position: str = "below"  # below | above | right | left | icons_only


@dataclass
class LLMTunerConfig:
    fast: Dict[str, Any] = field(default_factory=dict)
    normal: Dict[str, Any] = field(default_factory=dict)
    slow: Dict[str, Any] = field(default_factory=dict)
    pause: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Config root
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AppConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    thermal: ThermalConfig = field(default_factory=ThermalConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    decision_models: DecisionModelsConfig = field(
        default_factory=DecisionModelsConfig
    )
    generic_task_planner: GenericTaskPlannerConfig = field(
        default_factory=GenericTaskPlannerConfig
    )
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    audit_gates: AuditGatesConfig = field(default_factory=AuditGatesConfig)
    llm_tuner: LLMTunerConfig = field(default_factory=LLMTunerConfig)
    sml_best: SMLBestConfig = field(default_factory=SMLBestConfig)
    gui: GUISettingsConfig = field(default_factory=GUISettingsConfig)
    raw: Dict[str, Any] = field(default_factory=dict)  # TOML grezzo per usi estesi


def load_typed_config(path: str | Path = "CONFIG/config.toml") -> AppConfig:
    """Carica ``config.toml`` e popola le dataclass tipizzate.

    Se il file non esiste o TOML non è disponibile, ritorna una
    ``AppConfig`` con tutti i default.
    """
    config = AppConfig()
    p = Path(path)
    if not p.exists():
        return config
    try:
        data = _load_toml(p)
    except Exception:
        return config

    config.raw = data

    def _get(section: str, default: dict = None) -> dict:
        return data.get(section, default or {})

    # ollama
    o = _get("ollama")
    config.ollama = OllamaConfig(
        host=o.get("host", config.ollama.host),
        request_timeout=int(o.get("request_timeout", config.ollama.request_timeout)),
    )

    # models
    m = _get("models")
    models_cfg = ModelsConfig()
    for key in ("orchestrator", "planner", "worker_coder", "worker_general",
                "embedding"):
        sub = m.get(key, {})
        models_cfg.__dict__[key] = ModelConfig(
            name=sub.get("name", ""),
            temperature=float(sub.get("temperature", 0.1)),
            top_p=float(sub.get("top_p", 0.8)),
            top_k=int(sub.get("top_k", 40)),
            repeat_penalty=float(sub.get("repeat_penalty", 1.1)),
            repeat_last_n=int(sub.get("repeat_last_n", 256)),
            num_ctx=int(sub.get("num_ctx", 2048)),
            num_predict=int(sub.get("num_predict", 256)),
            seed=sub.get("seed"),
            enabled=bool(sub.get("enabled", True)),
        )
    # modelli extra non mappati
    for key, sub in m.items():
        if key not in ("orchestrator", "planner", "worker_coder",
                       "worker_general", "embedding"):
            if isinstance(sub, dict):
                models_cfg.extra[key] = ModelConfig(
                    name=sub.get("name", ""),
                    enabled=bool(sub.get("enabled", True)),
                )
    config.models = models_cfg

    # thermal
    th = _get("thermal")
    thresholds = th.get("thresholds", {}) if isinstance(th, dict) else {}
    config.thermal = ThermalConfig(
        enabled=bool(th.get("enabled", True)) if isinstance(th, dict) else True,
        sample_interval=int(th.get("sample_interval", 30)) if isinstance(th, dict) else 30,
        history_max=int(th.get("history_max", 2880)) if isinstance(th, dict) else 2880,
        temp_cold=float(thresholds.get("temp_cold", 50.0)),
        temp_warm=float(thresholds.get("temp_warm", 65.0)),
        temp_hot=float(thresholds.get("temp_hot", 80.0)),
        temp_critical=float(thresholds.get("temp_critical", 90.0)),
        gpu_temp_warm=float(thresholds.get("gpu_temp_warm", 80.0)),
        gpu_temp_hot=float(thresholds.get("gpu_temp_hot", 85.0)),
        gpu_temp_critical=float(thresholds.get("gpu_temp_critical", 95.0)),
        cpu_pause_threshold=float(thresholds.get("cpu_pause_threshold", 0.95)),
    )

    # timing
    ti = _get("timing")
    config.timing = TimingConfig(
        orchestrator_tick=int(ti.get("orchestrator_tick", 30)),
        worker_tick=int(ti.get("worker_tick", 60)),
        health_check=int(ti.get("health_check", 300)),
        git_snapshot=int(ti.get("git_snapshot", 999999)),
        memory_compaction=int(ti.get("memory_compaction", 3600)),
        backup_complete=int(ti.get("backup_complete", 86400)),
        model_unload_idle=int(ti.get("model_unload_idle", 120)),
    )

    # safety
    sa = _get("safety")
    config.safety = SafetyConfig(
        sandbox_enabled=bool(sa.get("sandbox_enabled", True)),
        max_attempts=int(sa.get("max_attempts", 10)),
        max_consecutive_failures=int(sa.get("max_consecutive_failures", 3)),
        cooldown_after_failure=int(sa.get("cooldown_after_failure", 120)),
        swap_threshold=float(sa.get("swap_threshold", 0.95)),
        disk_free_threshold=int(sa.get("disk_free_threshold", 1000000000)),
        max_log_size=int(sa.get("max_log_size", 10000000)),
        heartbeat_timeout=int(sa.get("heartbeat_timeout", 300)),
        max_tasks_per_agent_per_hour=int(
            sa.get("max_tasks_per_agent_per_hour", 20)
        ),
        memory_compaction_threshold=int(
            sa.get("memory_compaction_threshold", 50)
        ),
    )

    # security
    se = _get("security")
    config.security = SecurityConfig(
        enabled=bool(se.get("enabled", True)),
        max_output_chars=int(se.get("max_output_chars", 10000)),
        max_file_size_write=int(se.get("max_file_size_write", 2000000)),
        max_file_size_bytes=int(se.get("max_file_size_bytes", 50000000)),
        max_memory_mb=int(se.get("max_memory_mb", 1536)),
    )

    # routing
    ro = _get("routing")
    dk = ro.get("direct_keywords", {}) if isinstance(ro, dict) else {}
    config.routing = RoutingConfig(
        confidence_threshold=float(ro.get("confidence_threshold", 0.65)),
        max_files_per_task=int(ro.get("max_files_per_task", 8)),
        max_file_size_readable=int(ro.get("max_file_size_readable", 50000)),
        timeout_bash=int(ro.get("timeout_bash", 30)),
        worker_coder_keywords=list(dk.get("worker_coder", [])),
        worker_general_keywords=list(dk.get("worker_general", [])),
    )

    # paths
    pa = _get("paths")
    config.paths = PathsConfig(
        project_root=str(pa.get("project_root", "./project")),
        state_dir=str(pa.get("state_dir", "./state")),
        tasks_dir=str(pa.get("tasks_dir", "./tasks")),
        logs_dir=str(pa.get("logs_dir", "./logs")),
        backups_dir=str(pa.get("backups_dir", "./backups")),
        git_dir=str(pa.get("git_dir", "./project")),
    )

    # logging
    lg = _get("logging")
    config.logging = LoggingConfig(
        level=str(lg.get("level", "DEBUG")),
        file=str(lg.get("file", "./logs/byte-swarmy.log")),
    )

    # decision_models
    dm = _get("decision_models")
    dmc = DecisionModelsConfig(active=str(dm.get("active", "")))
    for key, sub in dm.items():
        if key == "active" or not isinstance(sub, dict):
            continue
        dmc.extra[key] = DecisionModelConfig(
            name=str(sub.get("name", "")),
            enabled=bool(sub.get("enabled", False)),
            temperature=float(sub.get("temperature", 0.1)),
            num_ctx=int(sub.get("num_ctx", DEFAULT_NUM_CTX)),
        )
    config.decision_models = dmc

    # generic_task_planner
    gp = _get("generic_task_planner")
    config.generic_task_planner = GenericTaskPlannerConfig(
        enabled=bool(gp.get("enabled", True)),
        max_subtasks=int(gp.get("max_subtasks", 8)),
        max_tokens=int(gp.get("max_tokens", 1500)),
        system_prompt=str(gp.get("system_prompt", "")),
    )

    # hardware
    hw = _get("hardware")
    config.hardware = HardwareConfig(
        mode=str(hw.get("mode", "auto")),
        worker_count=hw.get("worker_count"),
        keep_alive_sec=hw.get("keep_alive_sec"),
        strategy=hw.get("strategy"),
    )

    # audit_gates
    ag = _get("audit.gates") if isinstance(_get("audit.gates"), dict) else {}
    config.audit_gates = AuditGatesConfig(
        enabled=bool(ag.get("enabled", False)),
        mode=str(ag.get("mode", "advisory")),
        target=str(ag.get("target", "auto")),
        categories=list(ag.get("categories", [])),
    )

    # llm_tuner
    lt = _get("llm_tuner")
    config.llm_tuner = LLMTunerConfig(
        fast=dict(lt.get("fast", {})) if isinstance(lt, dict) else {},
        normal=dict(lt.get("normal", {})) if isinstance(lt, dict) else {},
        slow=dict(lt.get("slow", {})) if isinstance(lt, dict) else {},
        pause=dict(lt.get("pause", {})) if isinstance(lt, dict) else {},
    )

    # sml_best (valori ottimizzati per modelli <= 7B)
    sb = _get("sml_best")
    config.sml_best = SMLBestConfig(
        temperature=float(sb.get("temperature", SMLBestConfig.temperature)),
        num_ctx=int(sb.get("num_ctx", SMLBestConfig.num_ctx)),
        num_predict=int(sb.get("num_predict", SMLBestConfig.num_predict)),
        repeat_penalty=float(sb.get("repeat_penalty", SMLBestConfig.repeat_penalty)),
        seed=int(sb.get("seed", SMLBestConfig.seed)),
        modello_consigliato=str(sb.get("modello_consigliato", SMLBestConfig.modello_consigliato)),
        system_prompt_versione=str(sb.get("system_prompt_versione", SMLBestConfig.system_prompt_versione)),
        fsm_max_stati=int(sb.get("fsm_max_stati", SMLBestConfig.fsm_max_stati)),
        fsm_max_transizioni=int(sb.get("fsm_max_transizioni", SMLBestConfig.fsm_max_transizioni)),
    )

    # gui (preferenze interfaccia)
    g = _get("gui")
    config.gui = GUISettingsConfig(
        icon_text_position=str(g.get("icon_text_position", GUISettingsConfig.icon_text_position)),
    )

    return config


__all__ = [
    "AppConfig", "OllamaConfig", "ModelsConfig", "ModelConfig",
    "ThermalConfig", "TimingConfig", "SafetyConfig", "SecurityConfig",
    "RoutingConfig", "PathsConfig", "LoggingConfig",
    "DecisionModelsConfig", "DecisionModelConfig",
    "GenericTaskPlannerConfig", "HardwareConfig", "AuditGatesConfig",
    "LLMTunerConfig", "SMLBestConfig", "GUISettingsConfig", "load_typed_config",
]
