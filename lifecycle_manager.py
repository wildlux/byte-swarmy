"""
lifecycle_manager.py — Manages system startup, shutdown, backups and git.
"""
import os
import tarfile
import signal
import subprocess
from pathlib import Path
from typing import Optional
from constants import DEFAULT_PATHS

class LifecycleManager:
    def __init__(self, config, logger):
        self.config = config
        self.log = logger
        self.paths = config["paths"]

    def prepare_directories(self):
        """Ensures all required system directories exist."""
        for k in ("project_root", "state_dir", "tasks_dir", "logs_dir", "backups_dir"):
            Path(self.paths[k]).mkdir(parents=True, exist_ok=True)

    def init_git(self):
        """Initializes git in the project root if not already present."""
        project = Path(self.paths["project_root"])
        git_dir = project / ".git"
        if not git_dir.exists():
            try:
                subprocess.run(["git", "init"], cwd=str(project), capture_output=True, timeout=10)
                subprocess.run(["git", "config", "user.email", "ai@civ.local"], cwd=str(project), capture_output=True)
                subprocess.run(["git", "config", "user.name", "BYTE-SWARMY"], cwd=str(project), capture_output=True)
                self.log.info("git initialized in project_root")
            except Exception as e:
                self.log.warning(f"git init failed: {e}")

    def perform_backup(self):
        """Creates a full compressed backup of the project."""
        import time
        ts = int(time.time())
        backup_path = Path(self.paths["backups_dir"]) / f"backup-{ts}.tar.gz"
        project_root = Path(self.paths["project_root"])
        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in project_root.iterdir():
                    if item.name == ".git": continue
                    tar.add(item, arcname=item.name)
            self.log.info(f"backup saved: {backup_path}")
            
            # Keep only last 7
            backups = sorted(Path(self.paths["backups_dir"]).glob("backup-*.tar.gz"))
            for old in backups[:-7]:
                old.unlink()
        except Exception as e:
            self.log.error(f"backup failed: {e}")
