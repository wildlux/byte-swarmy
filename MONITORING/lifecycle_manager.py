"""
lifecycle_manager.py — Manages system startup, shutdown, backups and git.
"""
import os
import tarfile
import signal
import subprocess
from pathlib import Path
from typing import Optional
from CORE.constants import DEFAULT_PATHS

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
        """Creates a full compressed backup of the project, WITH restore verification.

        Un backup non verificato e' un backup inesistente: dopo la creazione
        viene aperto, estratto in una directory temporanea e ricontato. Se la
        verifica fallisce il backup non viene considerato valido.
        """
        import time
        ts = int(time.time())
        backup_path = Path(self.paths["backups_dir"]) / f"backup-{ts}.tar.gz"
        project_root = Path(self.paths["project_root"])
        backup_ok = False
        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in project_root.iterdir():
                    if item.name == ".git": continue
                    tar.add(item, arcname=item.name)
            # --- VERIFICA DI RESTORE (M5) ---
            backup_ok, detail = self._verify_backup(backup_path)
            if backup_ok:
                self.log.info(f"backup verified: {backup_path.name} ({detail})")
            else:
                self.log.error(f"backup NOT verified ({detail}): {backup_path.name}")
            
            if backup_ok:
                # Keep only last 7 (solo backup validi)
                backups = sorted(Path(self.paths["backups_dir"]).glob("backup-*.tar.gz"))
                for old in backups[:-7]:
                    old.unlink()
        except Exception as e:
            self.log.error(f"backup failed: {e}")

    def _verify_backup(self, backup_path) -> tuple[bool, str]:
        """Apre il backup, lo estrae in temp e riconta i file. Non muta l'host."""
        import tempfile
        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                members = tar.getmembers()
                file_members = [m for m in members if m.isfile()]
                if not file_members:
                    return False, "backup vuoto (nessun file memorizzato)"
                with tempfile.TemporaryDirectory(prefix="bswarm-restore-") as tmp:
                    tar.extractall(tmp)
                    restored = sum(1 for p in Path(tmp).rglob("*") if p.is_file())
                    if restored < len(file_members):
                        return False, (
                            f"restore incompleto: attesi {len(file_members)} "
                            f"file, estratti {restored}"
                        )
                    return True, f"{len(file_members)} file, restore OK"
        except Exception as e:
            return False, f"verifica fallita: {e}"
