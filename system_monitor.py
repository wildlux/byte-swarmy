"""
system_monitor.py — Handles health checks, resource monitoring and Timestral integration.
"""
import os
from pathlib import Path
from constants import SAFETY_THRESHOLDS

class SystemMonitor:
    def __init__(self, config, logger, timestral_manager=None):
        self.config = config
        self.log = logger
        self.timestral = timestral_manager

    def check_resources(self) -> bool:
        """Verifies RAM and Disk availability."""
        # RAM Check (Linux)
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {l.split(":")[0].strip(): int(l.split(":")[1].strip().split()[0]) * 1024 for l in lines}
            total = info.get("MemTotal", 1)
            avail = info.get("MemAvailable", 0)
            if (1 - (avail / total)) > self.config["safety"].get("swap_threshold", 0.8):
                self.log.warning("RAM pressure too high, pausing dispatch")
                return False
        except Exception:
            pass

        # Disk Check
        try:
            import os
            stat = os.statvfs(self.config["paths"]["project_root"])
            free = stat.f_bavail * stat.f_frsize
            if free < self.config["safety"].get("disk_free_threshold", 1*1024**3):
                self.log.warning("Disk space low, pausing dispatch")
                return False
        except Exception:
            pass
            
        return True

    def get_thermal_advice(self):
        """Returns action based on Timestral's advice."""
        if not self.timestral:
            return "normal", 1.0
        
        advice = self.timestral.get_advice()
        return advice.action, advice.tick_multiplier
