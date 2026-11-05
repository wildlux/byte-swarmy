"""hardware_detector.py — Rilevamento hardware automatico per BYTE-SWARMY.

Rileva il tipo di GPU (Apple Metal / NVIDIA CUDA / AMD ROCm / nessuna),
la memoria disponibile (unificata vs dedicata) e suggerisce automaticamente:
  - numero di Worker paralleli ottimale
  - keep_alive (secondi di permanenza modelli in RAM)
  - strategia di distribuzione CPU/GPU
  - modelli raccomandati in base alla RAM/VRAM

Compatibile con:
  - Apple Silicon (M1/M2/M3/M4) — memoria unificata, Metal
  - NVIDIA (RTX 30/40/50, H100, A100) — VRAM dedicata, CUDA
  - AMD (Radeon RX 7000+, Instinct MI250/MI300) — VRAM dedicata, ROCm
  - Solo CPU (no GPU) — fallback

L'auto-rilevamento avviene al boot di byte-swarmy. L'utente può anche
forzare una configurazione manuale via CONFIG/config.toml [hardware].
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Path della root del progetto (parent di CORE/)
_BASE = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════
# Dataclass: profilo hardware
# ═══════════════════════════════════════════════════════════════

@dataclass
class HardwareProfile:
    """Profilo hardware rilevato + suggerimenti di strategia.

    Tutti i campi sono auto-popolati da detect(). L'utente può leggere
    questi valori dalla GUI (pannello "Hardware & Modelli") e l'orchestratore
    li usa per configurare ModelClient e WorkerPool.
    """
    # ── Rilevamento grezzo ────────────────────────────────────────
    gpu_type: str = "none"           # "apple_metal" | "nvidia_cuda" | "amd_rocm" | "none"
    gpu_name: str = ""               # es. "Apple M3 Max", "NVIDIA GeForce RTX 4090"
    memory_unified: bool = False     # True per Apple Silicon, False per NVIDIA/AMD dedicata
    ram_total_gb: float = 0.0        # RAM sistema (totale)
    vram_total_gb: float = 0.0       # VRAM GPU (= ram_total_gb se unified)
    bandwidth_gbps: float = 0.0      # bandwidth memoria (100-400 Apple, 10-20 PCIe)
    cpu_cores: int = 0               # core logici CPU
    platform: str = ""               # "darwin" | "linux" | "win32"

    # ── Suggerimenti strategia ────────────────────────────────────
    strategy: str = "cpu_only"       # nome strategia (vedi STRATEGIES sotto)
    worker_count: int = 1            # Worker paralleli raccomandati
    keep_alive_sec: int = 0          # secondi keep_alive per Ollama
    models_in_ram: int = 1           # modelli caricati simultaneamente
    description: str = ""            # descrizione umana della strategia
    model_size_gb: float = 0.0       # dimensione stimata del modello più grande
    model_fits_vram: bool = False    # True se il modello entra in VRAM disponibile

    # ── Capacità calcolata dai modelli REALI (compute_capacity) ──
    capacity_gpu_models: int = 0     # attori che stanno in VRAM
    capacity_cpu_models: int = 0     # attori che stanno in RAM (CPU)
    capacity_note: str = ""          # nota umana sul piano di carico

    # ── Stato rilevamento ─────────────────────────────────────────
    detection_ok: bool = True        # False se rilevamento fallito (fallback a cpu_only)
    detection_warnings: list = field(default_factory=list)  # warning non fatali
    raw_data: dict = field(default_factory=dict)  # dati grezzi per debug

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def supports_multi_model(self) -> bool:
        """True se l'hardware supporta più modelli in RAM simultaneamente."""
        return self.models_in_ram >= 2

    @property
    def supports_parallel_workers(self) -> bool:
        """True se l'hardware supporta Worker paralleli."""
        return self.worker_count >= 2

    @property
    def summary(self) -> str:
        """Riepilogo one-line per GUI/log."""
        gpu_str = self.gpu_name or self.gpu_type.upper()
        mem_str = (f"{self.ram_total_gb:.0f}GB unified"
                   if self.memory_unified
                   else f"{self.ram_total_gb:.0f}GB RAM + {self.vram_total_gb:.0f}GB VRAM")
        return (f"{gpu_str} ({mem_str}) → strategy={self.strategy}, "
                f"workers={self.worker_count}, keep_alive={self.keep_alive_sec}s")


# ═══════════════════════════════════════════════════════════════
# Strategie predefinite
# ═══════════════════════════════════════════════════════════════

STRATEGIES = {
    "unified_parallel": {
        "description": "Memoria unificata Apple Silicon con ≥32GB — 4 Worker paralleli, "
                       "4 modelli caricati simultaneamente, keep_alive lungo",
        "worker_count": 4,
        "keep_alive_sec": 600,
        "models_in_ram": 4,
    },
    "unified_light": {
        "description": "Memoria unificata Apple Silicon con 16GB — 2 Worker, "
                       "2 modelli simultanei, keep_alive medio",
        "worker_count": 2,
        "keep_alive_sec": 300,
        "models_in_ram": 2,
    },
    "nvidia_dual": {
        "description": "NVIDIA con VRAM ≥20GB — 2 Worker su GPU, 2 modelli simultanei",
        "worker_count": 2,
        "keep_alive_sec": 300,
        "models_in_ram": 2,
    },
    "nvidia_cpu_split": {
        "description": "NVIDIA con VRAM 8-20GB — 1 Worker su GPU + 1 su CPU, "
                       "context switching rapido",
        "worker_count": 2,
        "keep_alive_sec": 60,
        "models_in_ram": 2,
    },
    "nvidia_light": {
        "description": "NVIDIA con VRAM 4-8GB e modello piccolo — 1 Worker su GPU, "
                       "keep_alive medio. La GPU viene usata per modelli che entrano "
                       "in VRAM (es. qwen2.5:1.5b su GTX 1050 4GB).",
        "worker_count": 1,
        "keep_alive_sec": 120,
        "models_in_ram": 1,
    },
    "amd_dual": {
        "description": "AMD ROCm con VRAM ≥16GB — 2 Worker su GPU, 2 modelli simultanei",
        "worker_count": 2,
        "keep_alive_sec": 300,
        "models_in_ram": 2,
    },
    "amd_light": {
        "description": "AMD ROCm con VRAM 4-16GB e modello piccolo — 1 Worker su GPU",
        "worker_count": 1,
        "keep_alive_sec": 120,
        "models_in_ram": 1,
    },
    "cpu_only": {
        "description": "Solo CPU (no GPU) — 1 Worker, 1 modello, context switch immediato",
        "worker_count": 1,
        "keep_alive_sec": 0,
        "models_in_ram": 1,
    },
}


# ═══════════════════════════════════════════════════════════════
# Rilevamento: Apple Silicon
# ═══════════════════════════════════════════════════════════════

def _detect_apple() -> Optional[dict]:
    """Rileva Apple Silicon e ritorna dict con chiavi: chip, ram_gb, bandwidth_gbps.

    Ritorna None se non è un Mac o se il rilevamento fallisce.
    """
    if platform.system() != "Darwin":
        return None
    try:
        # system_profiler per dettagli hardware
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        output = result.stdout
        # Estrai chip name
        chip_match = re.search(r"Chip:\s*(.+)", output)
        chip = chip_match.group(1).strip() if chip_match else "Apple Silicon"
        # Estrai RAM
        ram_match = re.search(r"Memory:\s*(\d+)\s*GB", output)
        ram_gb = float(ram_match.group(1)) if ram_match else 16.0
        # Bandwidth stimata per famiglia chip
        bandwidth = _estimate_apple_bandwidth(chip)
        return {
            "chip": chip,
            "ram_gb": ram_gb,
            "bandwidth_gbps": bandwidth,
        }
    except Exception:
        return None


def _estimate_apple_bandwidth(chip: str) -> float:
    """Stima bandwidth memoria Apple Silicon (GB/s) basandosi sul chip name."""
    chip_lower = chip.lower()
    # Fonti: benchmark pubblici Apple
    if "ultra" in chip_lower:
        return 800.0  # M1/M2/M3 Ultra
    elif "max" in chip_lower:
        return 400.0  # M1/M2/M3/M4 Max
    elif "m4" in chip_lower:
        return 120.0  # M4 base
    elif "m3" in chip_lower:
        return 100.0  # M3 base
    elif "m2" in chip_lower:
        return 100.0  # M2 base
    elif "m1" in chip_lower:
        return 68.0   # M1 base
    return 100.0  # default


# ═══════════════════════════════════════════════════════════════
# Rilevamento: NVIDIA
# ═══════════════════════════════════════════════════════════════

def _detect_nvidia() -> Optional[dict]:
    """Rileva GPU NVIDIA e ritorna dict con chiavi: name, vram_gb.

    Ritorna None se non c'è NVIDIA o se nvidia-smi non è disponibile.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        # Prendi la prima GPU (multi-GPU non gestito in questa versione)
        first_line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in first_line.split(",")]
        if len(parts) < 2:
            return None
        name = parts[0]
        vram_mb = float(parts[1])
        return {
            "name": name,
            "vram_gb": vram_mb / 1024.0,
        }
    except FileNotFoundError:
        return None  # nvidia-smi non installato
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# Rilevamento: AMD ROCm
# ═══════════════════════════════════════════════════════════════

def _detect_amd() -> Optional[dict]:
    """Rileva GPU AMD ROCm e ritorna dict con chiavi: name, vram_gb.

    Ritorna None se non c'è AMD ROCm o se rocm-smi non è disponibile.
    """
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname", "--showmeminfo", "vram",
             "--format", "json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        data = json.loads(result.stdout)
        # rocm-smi ritorna dict con chiavi "card0", "card1", ecc.
        for card_key, card_data in data.items():
            if not card_key.startswith("card"):
                continue
            name = card_data.get("Card series", card_data.get("Card model", "AMD GPU"))
            vram_bytes = card_data.get("VRAM Total Memory (B)", 0)
            if vram_bytes > 0:
                return {
                    "name": name,
                    "vram_gb": vram_bytes / (1024 ** 3),
                }
        return None
    except FileNotFoundError:
        return None  # rocm-smi non installato
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# Rilevamento: RAM sistema
# ═══════════════════════════════════════════════════════════════

def _detect_ram_gb() -> float:
    """Rileva RAM totale del sistema in GB.

    Su Apple Silicon legge da system_profiler (fonte autorevole per
    memoria unificata). Su Linux/Windows usa psutil o file di sistema.
    """
    # Su Apple Silicon, system_profiler è la fonte più affidabile
    if platform.system() == "Darwin":
        apple = _detect_apple()
        if apple and "ram_gb" in apple:
            return apple["ram_gb"]
    # Fallback cross-platform: psutil
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    # Fallback OS-specific
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / (1024 ** 2)  # kB → GB
        elif platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"],
                capture_output=True, text=True, timeout=5,
            )
            return float(result.stdout.strip().split("\n")[-1]) / (1024 ** 3)
    except Exception:
        pass
    return 8.0  # fallback conservativo


def _detect_cpu_cores() -> int:
    """Numero di core logici CPU."""
    try:
        import os as _os
        return _os.cpu_count() or 4
    except Exception:
        return 4


# ═══════════════════════════════════════════════════════════════
# Stima dimensione modello
# ═══════════════════════════════════════════════════════════════

# Mappa nome modello → dimensione stimata in GB (formato Q4_K_M, il default di Ollama)
# Fonte: dimensioni reali dei modelli Ollama più comuni
_MODEL_SIZE_GB = {
    # Modelli molto piccoli (< 1GB)
    "0.5b": 0.4, "270m": 0.3, "1b": 0.7, "tiny": 0.3,
    # Modelli piccoli (1-2GB)
    "1.3b": 0.8, "1.5b": 1.0, "1.7b": 1.1, "1.8b": 1.2,
    # Modelli medi (2-4GB)
    "2b": 1.5, "3b": 2.0, "4b": 2.6, "3.8b": 2.5,
    # Modelli grandi (4-8GB)
    "7b": 4.5, "6.7b": 4.0, "8b": 5.2, "6b": 3.8,
    # Modelli molto grandi (8-15GB)
    "13b": 8.0, "14b": 9.0, "12b": 7.5,
    # Modelli enormi (>15GB) — non supportati su GPU piccole
    "30b": 20.0, "31b": 21.0, "33b": 22.0, "70b": 40.0,
}


def _estimate_model_size_gb(model_name: str) -> float:
    """Stima la dimensione di un modello Ollama in GB (formato Q4 default).

    Cerca nel nome del modello pattern come '1.5b', '7b', '13b' e ritorna
    la dimensione stimata. Fallback: 2GB (modello medio-piccolo).

    Esempi:
        'qwen2.5:1.5b' → 1.0 GB
        'qwen2.5:7b'   → 4.5 GB
        'llama3:8b'    → 5.2 GB
        'phi3:mini'    → 2.0 GB (fallback)
    """
    if not model_name:
        return 2.0
    name_lower = model_name.lower()
    # Cerca pattern N.Nb o Nb (es. 1.5b, 7b, 13b, 270m)
    import re
    match = re.search(r'(\d+(?:\.\d+)?)(b|m)\b', name_lower)
    if match:
        size_str = match.group(1) + match.group(2)
        if size_str in _MODEL_SIZE_GB:
            return _MODEL_SIZE_GB[size_str]
        # Se non è nella mappa, stima: 1B ≈ 0.65GB in Q4
        try:
            num = float(match.group(1))
            unit = match.group(2)
            if unit == "b":
                return num * 0.65  # stima Q4
            else:  # 'm'
                return num * 0.001  # 270m ≈ 0.27GB
        except ValueError:
            pass
    return 2.0  # fallback conservativo


# Peso di default per attore quando actors.json non lo specifica
_ACTOR_DEFAULT_WEIGHTS = {"llm": "medium", "decision_model": "light",
                          "timestral": "light"}


def _resolved_actor_models() -> list[tuple[str, str, bool]]:
    """Risolve (attore, modello, force_cpu) per i 3 attori del sistema.

    Il software usa 3 LLM con ruoli diversi:
      - llm:            il "pesante" che scrive il codice
      - decision_model: decide l'ordine/strategia per codice migliore
      - timestral:      gatekeeper TERMICO — ferma o rallenta gli altri
                        (SEMPRE light e SEMPRE su CPU, force_cpu)
    Il modello esplicito di actors.json vince; altrimenti default per
    peso (H3). Il Timestral è force_cpu per design (H4).
    """
    from CORE.constants import ACTOR_FORCE_CPU, weight_default_model
    try:
        import json
        actors_file = _BASE / "CONFIG" / "actors.json"
        data = {}
        if actors_file.exists():
            with open(actors_file, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        data = {}

    out = []
    for actor in ("llm", "decision_model", "timestral"):
        a = data.get(actor, {}) if isinstance(data, dict) else {}
        weight = a.get("weight") or _ACTOR_DEFAULT_WEIGHTS[actor]
        if actor == "timestral":
            weight = "light"           # H4: mai altro peso
        model = a.get("model") or weight_default_model(actor, weight)
        out.append((actor, model, actor in ACTOR_FORCE_CPU))
    return out


def _get_configured_models() -> list[str]:
    """Nomi dei modelli dei 3 attori risolti (LLM + Decision + Timestral)."""
    return [m for (_, m, _) in _resolved_actor_models()]


def _largest_configured_model_gb() -> float:
    """Ritorna la dimensione del modello più grande configurato in actors.json.

    Usato per decidere se la GPU ha abbastanza VRAM. Se actors.json non
    è leggibile, ritorna 2.0GB (assunzione conservativa modello medio).
    """
    models = _get_configured_models()
    if not models:
        return 2.0
    sizes = [_estimate_model_size_gb(m) for m in models]
    return max(sizes) if sizes else 2.0


# ═══════════════════════════════════════════════════════════════
# Selettore strategia
# ═══════════════════════════════════════════════════════════════

# Overhead di sicurezza per VRAM (Ollama ha bisogno di ~1GB per KV cache + compute)
_VRAM_OVERHEAD_GB = 1.0
# Margine extra sulla VRAM utile: le KV cache crescono col contesto e i
# buffer compute variano; senza margine un piano "esatto" finisce in OOM.
_VRAM_HEADROOM_FACTOR = 0.85
# RAM riservata a OS + GUI + orchestratore quando si calcola quanto resta
# ai modelli su CPU (conservativo: chi svuota la RAM va in swap).
_RAM_OS_OVERHEAD_GB = 2.5
# Overhead runtime di un modello caricato su CPU (~20% sopra il peso file)
_RAM_RUNTIME_FACTOR = 1.2
# Ogni modello su GPU usa comunque un po' di RAM di sistema (buffer/copy)
_RAM_RESERVED_PER_GPU_MODEL_GB = 0.3


def compute_capacity(profile: "HardwareProfile") -> "HardwareProfile":
    """Ricalcola models_in_ram e il piano GPU/CPU dai MODELLI REALI.

    La tabella STRATEGIES dà valori fissi conservativi per fascia (es.
    nvidia_light = 1 modello); qui si affina col calcolo vero: si stima
    la dimensione di ogni attore configurato in actors.json e si riempiono
    VRAM e RAM finché c'è spazio, con margini di sicurezza.

    Così il multi-modello NON è più vietato per firma: se cambi hardware
    (più VRAM/RAM) o scegli modelli più piccoli nel pannello Attori,
    basta rieseguire il rilevamento e la capacità si aggiorna.
    """
    actors = _resolved_actor_models()
    # (attore, size, force_cpu); Timestral per design NON va mai su GPU:
    # è il gatekeeper termico, deve girare su CPU anche a VRAM vuota.
    entries = [(a, _estimate_model_size_gb(m), fc) for (a, m, fc) in actors]
    if not entries:
        entries = [("(fallback)", profile.model_size_gb or 2.0, False)]
    # GPU-first per i NON-force-cpu, dal più grande al più piccolo
    entries.sort(key=lambda e: (e[2], -e[1]))

    vram_usable = (profile.vram_total_gb - _VRAM_OVERHEAD_GB) \
        * _VRAM_HEADROOM_FACTOR
    ram_budget = max(0.0, profile.ram_total_gb - _RAM_OS_OVERHEAD_GB)
    ram_used = 0.0

    gpu: list = []
    cpu: list = []
    overflow: list = []
    force_cpu_actor: str = ""
    for actor, size, force_cpu in entries:
        on_gpu = (not force_cpu and profile.vram_total_gb > 0
                  and (sum(gpu) + size) <= vram_usable)
        if on_gpu:
            gpu.append(size)
            ram_used += _RAM_RESERVED_PER_GPU_MODEL_GB
        elif (ram_budget - ram_used) >= size * _RAM_RUNTIME_FACTOR:
            cpu.append(size)
            ram_used += size * _RAM_RUNTIME_FACTOR
            if force_cpu:
                force_cpu_actor = actor
        else:
            overflow.append(size)

    profile.capacity_gpu_models = len(gpu)
    profile.capacity_cpu_models = len(cpu)
    # models_in_ram = quanti attori possono restare RESIDENTI insieme.
    # Non scende mai sotto 1 (almeno il Worker deve girare).
    profile.models_in_ram = max(1, len(gpu) + len(cpu))
    parts = []
    if gpu:
        parts.append(f"{len(gpu)} su GPU")
    if cpu:
        parts.append(f"{len(cpu)} su CPU")
    if overflow:
        parts.append(f"{len(overflow)} NON residente (memoria insufficiente)")
    profile.capacity_note = " + ".join(parts) if parts else "—"
    if force_cpu_actor and cpu:
        profile.capacity_note += f" ({force_cpu_actor} sempre su CPU)"
    if overflow:
        profile.detection_warnings.append(
            f"capacità: {len(overflow)} modello/i non entrano in memoria — "
            "usa modelli più piccoli o aumenta keep_alive a 0")
    return profile


def _select_strategy(gpu_type: str, ram_gb: float, vram_gb: float,
                     unified: bool, model_gb: float = None) -> str:
    """Seleziona la strategia ottimale in base all'hardware + modello configurato.

    Args:
        gpu_type: tipo GPU ("apple_metal" | "nvidia_cuda" | "amd_rocm" | "none")
        ram_gb: RAM totale sistema in GB
        vram_gb: VRAM GPU in GB (per unified, = ram_gb)
        unified: True per memoria unificata Apple Silicon
        model_gb: dimensione del modello più grande configurato in GB.
                  Se None, legge da CONFIG/actors.json (fallback 2.0GB).
    """
    if model_gb is None:
        model_gb = _largest_configured_model_gb()

    # VRAM utile = VRAM totale - overhead (KV cache, compute buffers)
    vram_available = vram_gb - _VRAM_OVERHEAD_GB

    if gpu_type == "apple_metal":
        # Apple Silicon: memoria unificata, decide in base alla RAM totale
        if ram_gb >= 32:
            return "unified_parallel"
        elif ram_gb >= 16:
            return "unified_light"
        else:
            return "cpu_only"  # Mac con poca RAM (8GB), resta conservativo
    elif gpu_type == "nvidia_cuda":
        # Gerarchia: dual (≥20GB) → cpu_split (8-20GB) → light (4-8GB + modello piccolo)
        if vram_gb >= 20:
            return "nvidia_dual"
        elif vram_gb >= 8:
            return "nvidia_cpu_split"
        elif vram_gb >= 4 and model_gb <= vram_available:
            # GPU piccola (4-8GB) MA il modello configurato entra in VRAM
            # → usa GPU per inference (es. GTX 1050 4GB + qwen2.5:1.5b 1GB)
            return "nvidia_light"
        else:
            return "cpu_only"  # modello troppo grande per la VRAM disponibile
    elif gpu_type == "amd_rocm":
        if vram_gb >= 16:
            return "amd_dual"
        elif vram_gb >= 4 and model_gb <= vram_available:
            return "amd_light"
        elif vram_gb >= 8:
            return "nvidia_cpu_split"  # riusa la strategia split
        else:
            return "cpu_only"
    else:
        return "cpu_only"


# ═══════════════════════════════════════════════════════════════
# Funzione principale: detect()
# ═══════════════════════════════════════════════════════════════

def detect() -> HardwareProfile:
    """Rileva l'hardware e ritorna un HardwareProfile con suggerimenti.

    Questa funzione viene chiamata al boot di byte-swarmy. Non fallisce
    mai: se qualcosa va storto, ritorna un profile cpu_only conservativo.
    """
    profile = HardwareProfile()
    profile.platform = platform.system().lower()

    try:
        # Rileva RAM e CPU (sempre disponibili)
        profile.ram_total_gb = _detect_ram_gb()
        profile.cpu_cores = _detect_cpu_cores()
        profile.raw_data["ram_gb"] = profile.ram_total_gb
        profile.raw_data["cpu_cores"] = profile.cpu_cores

        # Prova Apple Silicon primo (priorità su Mac)
        apple = _detect_apple()
        if apple:
            profile.gpu_type = "apple_metal"
            profile.gpu_name = apple["chip"]
            profile.memory_unified = True
            profile.vram_total_gb = apple["ram_gb"]  # unificata
            profile.bandwidth_gbps = apple["bandwidth_gbps"]
            profile.raw_data["apple"] = apple
        else:
            # Prova NVIDIA
            nvidia = _detect_nvidia()
            if nvidia:
                profile.gpu_type = "nvidia_cuda"
                profile.gpu_name = nvidia["name"]
                profile.memory_unified = False
                profile.vram_total_gb = nvidia["vram_gb"]
                profile.bandwidth_gbps = 20.0  # PCIe 4.0 ~16GB/s, stima conservativa
                profile.raw_data["nvidia"] = nvidia
            else:
                # Prova AMD ROCm
                amd = _detect_amd()
                if amd:
                    profile.gpu_type = "amd_rocm"
                    profile.gpu_name = amd["name"]
                    profile.memory_unified = False
                    profile.vram_total_gb = amd["vram_gb"]
                    profile.bandwidth_gbps = 20.0
                    profile.raw_data["amd"] = amd
                else:
                    # Solo CPU
                    profile.gpu_type = "none"
                    profile.gpu_name = f"CPU ({profile.cpu_cores} cores)"
                    profile.memory_unified = False
                    profile.vram_total_gb = 0.0
                    profile.bandwidth_gbps = 0.0

        # Seleziona strategia
        profile.strategy = _select_strategy(
            profile.gpu_type, profile.ram_total_gb,
            profile.vram_total_gb, profile.memory_unified,
        )
        strat = STRATEGIES.get(profile.strategy, STRATEGIES["cpu_only"])
        profile.worker_count = strat["worker_count"]
        profile.keep_alive_sec = strat["keep_alive_sec"]
        profile.models_in_ram = strat["models_in_ram"]
        profile.description = strat["description"]

        # Popola info sul modello configurato (per GUI e debug)
        profile.model_size_gb = _largest_configured_model_gb()
        vram_available = profile.vram_total_gb - _VRAM_OVERHEAD_GB
        profile.model_fits_vram = (
            profile.vram_total_gb > 0 and profile.model_size_gb <= vram_available
        )

        # Capacità REALE: quanti attori stanno residenti e dove (GPU/CPU),
        # calcolata dai modelli in actors.json — non dalla tabella fissa.
        compute_capacity(profile)

    except Exception as e:
        # Fail-safe: cpu_only conservativo
        profile.detection_ok = False
        profile.detection_warnings.append(f"Rilevamento fallito: {e}")
        profile.strategy = "cpu_only"
        strat = STRATEGIES["cpu_only"]
        profile.worker_count = strat["worker_count"]
        profile.keep_alive_sec = strat["keep_alive_sec"]
        profile.models_in_ram = strat["models_in_ram"]
        profile.description = strat["description"]
        profile.capacity_gpu_models = 0
        profile.capacity_cpu_models = 1
        profile.capacity_note = "1 su CPU (rilevamento fallito, piano conservativo)"

    return profile


# ═══════════════════════════════════════════════════════════════
# API pubblica: get_profile() con cache
# ═══════════════════════════════════════════════════════════════

_cached_profile: Optional[HardwareProfile] = None


def get_profile(force_refresh: bool = False) -> HardwareProfile:
    """Ritorna il profilo hardware cached (lo rileva al primo uso).

    Args:
        force_refresh: se True, rilancia il rilevamento anche se già cached
    """
    global _cached_profile
    if _cached_profile is None or force_refresh:
        _cached_profile = detect()
    return _cached_profile


def get_keep_alive_override(config: dict = None) -> int:
    """Ritorna keep_alive ottimale dall'hardware profile o dal config.

    L'utente può forzare un valore in CONFIG/config.toml [hardware].keep_alive_sec.
    Se non specificato (o "auto"), usa il suggerimento dell'hardware detector.
    """
    if config is None:
        return get_profile().keep_alive_sec
    hw_cfg = config.get("hardware", {})
    if hw_cfg.get("keep_alive_sec", "auto") == "auto":
        return get_profile().keep_alive_sec
    try:
        return int(hw_cfg.get("keep_alive_sec", 0))
    except (TypeError, ValueError):
        return get_profile().keep_alive_sec


def get_worker_count_override(config: dict = None) -> int:
    """Ritorna worker_count ottimale dall'hardware profile o dal config."""
    if config is None:
        return get_profile().worker_count
    hw_cfg = config.get("hardware", {})
    if hw_cfg.get("worker_count", "auto") == "auto":
        return get_profile().worker_count
    try:
        return max(1, int(hw_cfg.get("worker_count", 1)))
    except (TypeError, ValueError):
        return get_profile().worker_count


# ═══════════════════════════════════════════════════════════════
# CLI per test rapido
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hardware detector per BYTE-SWARMY")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", action="store_true", help="Mostra dati grezzi")
    args = parser.parse_args()

    profile = detect()
    if args.json:
        print(json.dumps(profile.to_dict(), indent=2, default=str))
    else:
        print("=" * 60)
        print("  HARDWARE DETECTION — BYTE-SWARMY")
        print("=" * 60)
        print()
        print(f"  Platform:         {profile.platform}")
        print(f"  GPU type:         {profile.gpu_type}")
        print(f"  GPU name:         {profile.gpu_name}")
        print(f"  Memory unified:   {profile.memory_unified}")
        print(f"  RAM total:        {profile.ram_total_gb:.1f} GB")
        print(f"  VRAM total:       {profile.vram_total_gb:.1f} GB")
        print(f"  Bandwidth:        {profile.bandwidth_gbps:.0f} GB/s")
        print(f"  CPU cores:        {profile.cpu_cores}")
        print()
        print(f"  ─── Strategia suggerita ───")
        print(f"  Strategy:         {profile.strategy}")
        print(f"  Worker count:     {profile.worker_count}")
        print(f"  Keep alive:       {profile.keep_alive_sec}s")
        print(f"  Models in RAM:    {profile.models_in_ram}")
        print(f"  Model size:       {profile.model_size_gb:.1f} GB")
        print(f"  Model fits VRAM:  {'✓ sì' if profile.model_fits_vram else '✗ no'}")
        print(f"  Description:      {profile.description}")
        print()
        if not profile.detection_ok:
            print(f"  ⚠️ Detection warnings:")
            for w in profile.detection_warnings:
                print(f"    - {w}")
            print()
        if args.verbose:
            print(f"  ─── Raw data ───")
            print(json.dumps(profile.raw_data, indent=2, default=str))
        print(f"  Summary: {profile.summary}")
        print()
