"""
thermal_manager.py — TimestralManager

Monitora CPU (load, frequenza) e temperature (thermal zones) su Linux.
Mantiene uno storico temporale (time series) su file JSON.
Regola dinamicamente i parametri dell'orchestratore per tenere fresca la CPU:
  - se temperatura > soglia_calda: rallenta (aumenta tick, dimezza task parallelismo)
  - se temperatura > soglia_critica: pausa (nessun task dispatchato)
  - se temperatura < soglia_fredda: ottimizza (riduci tick, massimizza throughput)

Compatibile con PC a 4GB RAM: bassissimo overhead, sampling ogni 30s.

I dati termici si possono scaricare anche da HuggingFace in futuro (dataset
di curve tipiche CPU), ma per ora usiamo solo sensori locali /sys/class/thermal.

Uso:
    manager = TimestralManager(config, logger)
    manager.start()                # avvia thread di monitoraggio
    advice = manager.get_advice()  # {"action": "slow"|"normal"|"pause", "tick_multiplier": 2.0, ...}
    manager.stop()
"""

from __future__ import annotations

import json
import os
import time
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


# ====================================================================
# Data classes
# ====================================================================

@dataclass
class ThermalSample:
    """Singolo campione di misura."""
    timestamp: float
    cpu_load: float          # 0.0 - 1.0
    cpu_temp_max: float      # °C, max tra le thermal zones
    cpu_freq_avg: int        # kHz, media tra le CPU
    mem_used_ratio: float    # 0.0 - 1.0
    swap_used_ratio: float   # 0.0 - 1.0
    n_processes: int

    gpu_temp: float = 0.0  # GPU temp (NVIDIA), 0.0 if no GPU
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThermalAdvice:
    """Consiglio dinamico per l'orchestratore."""
    action: str              # "normal" | "slow" | "fast" | "pause"
    tick_multiplier: float   # moltiplicatore per orchestrator_tick (1.0 = no change)
    max_tasks_per_hour: int  # override di safety.max_tasks_per_agent_per_hour
    reason: str
    sample: Optional[ThermalSample] = None

    def to_dict(self) -> dict:
        d = {"action": self.action, "tick_multiplier": self.tick_multiplier,
             "max_tasks_per_hour": self.max_tasks_per_hour, "reason": self.reason}
        if self.sample:
            d["sample"] = self.sample.to_dict()
        return d


# ====================================================================
# Thermal Gatekeeper (work order T3) — gate termico prima dell'LLM
# ====================================================================

# Soglie del work order: pausa >= 75/80, ripresa < 65
PAUSE_CPU = 75.0
PAUSE_GPU = 80.0
RESUME_TEMP = 65.0


def thermal_should_pause(cpu_temp: float, gpu_temp: float = 0.0) -> bool:
    """Funzione pura: True se la soglia di pausa e' superata."""
    return float(cpu_temp) >= PAUSE_CPU or float(gpu_temp) >= PAUSE_GPU


class TimestralGatekeeper:
    """Gate termico con isteresi, consultabile a polling (non bloccante).

    - l' latch `paused` si DRIVE True se cpu >= 75.0 o gpu >= 80.0;
    - si richiude SOLO quando max(cpu,gpu) < 65.0 (isteresi: intorno alle
      soglie non ci sono oscillazioni di stato);
    - non fa mai I/O né sleep: chi lo consulta passa i valori di temperatura.
    """

    def __init__(self, pause_cpu: float = PAUSE_CPU,
                 pause_gpu: float = PAUSE_GPU,
                 resume_temp: float = RESUME_TEMP):
        self.pause_cpu = float(pause_cpu)
        self.pause_gpu = float(pause_gpu)
        self.resume_temp = float(resume_temp)
        self.paused = False
        self.pause_reason = ""

    def check(self, cpu_temp: float, gpu_temp: float = 0.0) -> bool:
        """Aggiorna e ritorna lo stato latch (True = in pausa termica)."""
        cpu = float(cpu_temp or 0.0)
        gpu = float(gpu_temp or 0.0)
        if not self.paused:
            if cpu >= self.pause_cpu or gpu >= self.pause_gpu:
                self.paused = True
                self.pause_reason = (
                    f"CPU {cpu:.1f}C (soglia {self.pause_cpu:.0f}) / "
                    f"GPU {gpu:.1f}C (soglia {self.pause_gpu:.0f})"
                )
        else:
            if max(cpu, gpu) < self.resume_temp:
                self.paused = False
                self.pause_reason = ""
        return self.paused


# ====================================================================
# TimestralManager
# ====================================================================

class TimestralManager:
    """
    Monitor termico + timeseries + dynamic tuning.

    Thread-safe: il loop di sampling gira in un thread separato.
    L'orchestratore chiama get_advice() quando vuole (tip: ogni tick).
    """

    # Soglie di default (configurabili via config.toml)
    DEFAULT_THRESHOLDS = {
        "temp_cold": 50.0,       # sotto: ottimizza
        "temp_warm": 65.0,       # sopra: rallenta
        "temp_hot": 80.0,        # sopra: rallenta molto
        "temp_critical": 90.0,   # sopra: pausa
        "cpu_pause_threshold": 0.95,  # CPU load > 95% per N secondi = pausa
    }

    # Parametri di campionamento
    SAMPLE_INTERVAL = 30          # secondi tra campioni
    HISTORY_MAX = 2880            # 24h di campioni a 30s = 2880

    def __init__(self, config: dict, logger, base_dir: Path):
        self.config = config
        self.log = logger
        self.base_dir = base_dir
        self.history_file = base_dir / "state" / "timestral_history.json"

        # Soglie dal config (sezione thermal) o default
        thermal_cfg = config.get("thermal", {})
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **thermal_cfg.get("thresholds", {})}

        # Storico in RAM (deque per FIFO automatico)
        self.history: deque[ThermalSample] = deque(maxlen=self.HISTORY_MAX)

        # Stato runtime
        self.last_sample: Optional[ThermalSample] = None
        self.last_advice: Optional[ThermalAdvice] = None
        self.cpu_high_since: float = 0.0  # timestamp in cui CPU ha superato soglia

        # Thread
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Carica storico da disco
        self._load_history()

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Avvia il thread di monitoraggio."""
        if self._thread and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._sample_loop, daemon=True, name="timestral"
        )
        self._thread.start()
        self.log.info("[timestral] monitoring thread started")
        return True

    def stop(self) -> None:
        """Ferma il thread e salva lo storico."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._save_history()
        self.log.info("[timestral] monitoring thread stopped, history saved")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_advice(self) -> ThermalAdvice:
        """Calcola il consiglio dinamico basato sull'ultimo sample.
        Chiamato dall'orchestratore a ogni tick."""
        if not self.last_sample:
            return ThermalAdvice(
                action="normal", tick_multiplier=1.0,
                max_tasks_per_hour=self.config.get("safety", {}).get(
                    "max_tasks_per_agent_per_hour", 20),
                reason="no sample yet"
            )

        s = self.last_sample
        max_per_hour = self.config.get("safety", {}).get(
            "max_tasks_per_agent_per_hour", 20)

        # PAUSA: temperatura critica o CPU satura da > 60s
        if s.cpu_temp_max >= self.thresholds["temp_critical"]:
            self.last_advice = ThermalAdvice(
                action="pause", tick_multiplier=4.0,
                max_tasks_per_hour=0,
                reason=f"CPU temp {s.cpu_temp_max:.1f}C >= critical "
                       f"{self.thresholds['temp_critical']}C",
                sample=s
            )
            return self.last_advice

        if s.cpu_load >= self.thresholds["cpu_pause_threshold"]:
            if self.cpu_high_since == 0:
                self.cpu_high_since = time.time()
            elif time.time() - self.cpu_high_since > 60:
                self.last_advice = ThermalAdvice(
                    action="pause", tick_multiplier=4.0,
                    max_tasks_per_hour=0,
                    reason=f"CPU load {s.cpu_load*100:.0f}% saturated for >60s",
                    sample=s
                )
                return self.last_advice
        else:
            self.cpu_high_since = 0

        # SLOW: temperatura alta
        if s.cpu_temp_max >= self.thresholds["temp_hot"]:
            self.last_advice = ThermalAdvice(
                action="slow", tick_multiplier=2.5,
                max_tasks_per_hour=max(1, max_per_hour // 4),
                reason=f"CPU temp {s.cpu_temp_max:.1f}C >= hot "
                       f"{self.thresholds['temp_hot']}C",
                sample=s
            )
            return self.last_advice

        if s.cpu_temp_max >= self.thresholds["temp_warm"]:
            self.last_advice = ThermalAdvice(
                action="slow", tick_multiplier=1.7,
                max_tasks_per_hour=max(2, max_per_hour // 2),
                reason=f"CPU temp {s.cpu_temp_max:.1f}C >= warm "
                       f"{self.thresholds['temp_warm']}C",
                sample=s
            )
            return self.last_advice

        # FAST: temperatura bassa e CPU non satura
        if s.cpu_temp_max < self.thresholds["temp_cold"] and s.cpu_load < 0.6:
            self.last_advice = ThermalAdvice(
                action="fast", tick_multiplier=0.6,
                max_tasks_per_hour=max_per_hour * 2,
                reason=f"CPU cool ({s.cpu_temp_max:.1f}C) and idle "
                       f"({s.cpu_load*100:.0f}%)",
                sample=s
            )
            return self.last_advice

        # NORMAL
        self.last_advice = ThermalAdvice(
            action="normal", tick_multiplier=1.0,
            max_tasks_per_hour=max_per_hour,
            reason=f"normal operation (temp {s.cpu_temp_max:.1f}C, "
                   f"load {s.cpu_load*100:.0f}%)",
            sample=s
        )
        return self.last_advice

    def get_history(self, last_n: int = 100) -> list:
        """Ritorna gli ultimi N campioni (per plotting/debug)."""
        return [s.to_dict() for s in list(self.history)[-last_n:]]

    def get_stats(self) -> dict:
        """Statistiche aggregate sulle ultime 24h (o meno se non disponibile)."""
        if not self.history:
            return {"samples": 0}
        samples = list(self.history)
        temps = [s.cpu_temp_max for s in samples]
        loads = [s.cpu_load for s in samples]
        return {
            "samples": len(samples),
            "temp_min": min(temps),
            "temp_max": max(temps),
            "temp_avg": sum(temps) / len(temps),
            "load_min": min(loads),
            "load_max": max(loads),
            "load_avg": sum(loads) / len(loads),
            "first_ts": samples[0].timestamp,
            "last_ts": samples[-1].timestamp,
        }

    # ------------------------------------------------------------------
    # Loop di campionamento (private)
    # ------------------------------------------------------------------

    def _sample_loop(self) -> None:
        """Loop principale: campiona ogni SAMPLE_INTERVAL secondi."""
        while not self._stop_event.is_set():
            try:
                sample = self._take_sample()
                if sample:
                    self.last_sample = sample
                    self.history.append(sample)
                    # Salva storico su disco ogni 10 campioni (~5 min)
                    if len(self.history) % 10 == 0:
                        self._save_history()
                    self.log.debug(
                        f"[timestral] sample: temp={sample.cpu_temp_max:.1f}C "
                        f"load={sample.cpu_load*100:.0f}% "
                        f"freq={sample.cpu_freq_avg//1000}MHz "
                        f"mem={sample.mem_used_ratio*100:.0f}%"
                    )
                    # 🆕 Scrivi advice su file per la GUI (LLM tuner indicator)
                    try:
                        advice = self.get_advice()
                        import json as _json
                        advice_file = Path("state/timestral_advice.json")
                        advice_file.parent.mkdir(parents=True, exist_ok=True)
                        advice_data = {
                            "action": advice.action,
                            "tick_multiplier": advice.tick_multiplier,
                            "reason": advice.reason,
                            "timestamp": sample.timestamp,
                            "cpu_temp": sample.cpu_temp_max,
                            "gpu_temp": getattr(sample, "gpu_temp", 0.0),
                            "cpu_load": sample.cpu_load,
                        }
                        advice_file.write_text(_json.dumps(advice_data, indent=2))
                    except Exception as e:
                        self.log.debug(f"advice file write failed: {e}")
            except Exception as e:
                self.log.error(f"[timestral] sample error: {e}")

            self._stop_event.wait(timeout=self.SAMPLE_INTERVAL)
    def _read_gpu_temp(self) -> float:
        """Legge la temperatura GPU via nvidia-smi. Ritorna 0.0 se non disponibile."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip().split()[0])
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
        return 0.0

    def _take_sample(self) -> Optional[ThermalSample]:
        """Prende un campione leggendo /proc e /sys (Linux)."""
        try:
            return ThermalSample(
                timestamp=time.time(),
                cpu_load=self._read_cpu_load(),
                cpu_temp_max=self._read_cpu_temp_max(),
                cpu_freq_avg=self._read_cpu_freq(),
                mem_used_ratio=self._read_mem_used(),
                swap_used_ratio=self._read_swap_used(),
                n_processes=self._count_processes(),
                gpu_temp=self._read_gpu_temp(),
            )
        except Exception as e:
            self.log.error(f"[timestral] _take_sample failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Lettori sensori Linux
    # ------------------------------------------------------------------

    _prev_cpu_total: int = 0
    _prev_cpu_idle: int = 0

    def _read_cpu_load(self) -> float:
        """Legge /proc/stat per calcolare il CPU load dalla precedente chiamata."""
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            parts = line.split()[1:]  # skip "cpu"
            # user, nice, system, idle, iowait, irq, softirq, steal, ...
            values = [int(p) for p in parts]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
            prev_total, prev_idle = self._prev_cpu_total, self._prev_cpu_idle
            self._prev_cpu_total, self._prev_cpu_idle = total, idle
            if prev_total == 0:
                return 0.0
            dt = total - prev_total
            di = idle - prev_idle
            if dt == 0:
                return 0.0
            return max(0.0, min(1.0, 1.0 - (di / dt)))
        except Exception:
            return 0.0

    def _read_cpu_temp_max(self) -> float:
        """Legge tutte le thermal zones in /sys/class/thermal/ e ritorna la max."""
        temps = []
        try:
            thermal_dir = Path("/sys/class/thermal")
            if not thermal_dir.exists():
                return 0.0
            for zone in thermal_dir.glob("thermal_zone*"):
                temp_file = zone / "temp"
                if temp_file.exists():
                    try:
                        # valore in millicelsius
                        raw = int(temp_file.read_text().strip())
                        temps.append(raw / 1000.0)
                    except Exception:
                        continue
        except Exception:
            pass
        # Fallback: /sys/class/hwmon
        if not temps:
            try:
                hwmon_dir = Path("/sys/class/hwmon")
                for hwmon in hwmon_dir.iterdir():
                    for temp_file in hwmon.glob("temp*_input"):
                        try:
                            raw = int(temp_file.read_text().strip())
                            temps.append(raw / 1000.0)
                        except Exception:
                            continue
            except Exception:
                pass
        return max(temps) if temps else 0.0

    def _read_cpu_freq(self) -> int:
        """Media delle frequenze CPU in kHz."""
        try:
            freqs = []
            cpu_dir = Path("/sys/devices/system/cpu")
            for cpu in cpu_dir.glob("cpu[0-9]*"):
                freq_file = cpu / "cpufreq" / "scaling_cur_freq"
                if freq_file.exists():
                    try:
                        freqs.append(int(freq_file.read_text().strip()))
                    except Exception:
                        continue
            return sum(freqs) // len(freqs) if freqs else 0
        except Exception:
            return 0

    def _read_mem_used(self) -> float:
        """Legge /proc/meminfo per uso RAM."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                k, _, v = line.partition(":")
                info[k.strip()] = int(v.strip().split()[0]) * 1024  # bytes
            total = info.get("MemTotal", 1)
            avail = info.get("MemAvailable", 0)
            return max(0.0, min(1.0, 1.0 - (avail / total)))
        except Exception:
            return 0.0

    def _read_swap_used(self) -> float:
        """Legge /proc/meminfo per uso swap."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                k, _, v = line.partition(":")
                info[k.strip()] = int(v.strip().split()[0]) * 1024  # bytes
            total = info.get("SwapTotal", 0)
            free = info.get("SwapFree", 0)
            if total == 0:
                return 0.0
            return max(0.0, min(1.0, 1.0 - (free / total)))
        except Exception:
            return 0.0

    def _count_processes(self) -> int:
        """Conta i processi attivi."""
        try:
            return len([p for p in Path("/proc").iterdir()
                       if p.name.isdigit()])
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Persistenza storico
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        """Carica lo storico da disco (ultimi 24h)."""
        if not self.history_file.exists():
            return
        try:
            data = json.loads(self.history_file.read_text())
            samples = data.get("samples", [])
            # Carica solo gli ultimi N per non saturare RAM
            for s in samples[-self.HISTORY_MAX:]:
                self.history.append(ThermalSample(**s))
            self.log.info(f"[timestral] loaded {len(self.history)} samples from disk")
        except Exception as e:
            self.log.warning(f"[timestral] cannot load history: {e}")

    def _save_history(self) -> None:
        """Salva lo storico su disco (JSON)."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "saved_at": time.time(),
                "samples": [s.to_dict() for s in list(self.history)],
            }
            tmp = self.history_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            tmp.replace(self.history_file)
        except Exception as e:
            self.log.warning(f"[timestral] cannot save history: {e}")
