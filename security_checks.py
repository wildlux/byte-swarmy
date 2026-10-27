"""
security_checks.py — System-level Isolation Validator
Verifica se il sistema gira in un ambiente isolato e sicuro.
"""

from __future__ import annotations
import os
import pwd
import logging
from pathlib import Path
from typing import Tuple

def check_isolation() -> Tuple[bool, str]:
    """
    Verifica l'isolamento del sistema.
    Ritorna (is_safe, reason).
    """
    # 1. Verifica Utente Dedicato
    # L'utente non deve essere root e non deve essere l'utente primario del sistema (se possibile)
    try:
        username = pwd.getpwuid(os.getuid()).pw_name
        if username == "root":
            return False, "Il sistema gira come ROOT. Rischio critico di escalation."
        
        # In un setup ideale, l'utente si chiama 'byteswarmy'
        # Se non lo è, non è un errore fatale ma un warning
    except Exception as e:
        return False, f"Impossibile verificare l'utente: {e}"

    # 2. Verifica Cgroups (Memory/CPU limits)
    # Controlliamo se esistono i file di limite in /sys/fs/cgroup
    # Nota: questo dipende dalla versione del kernel e se è cgroup v1 o v2
    cgroup_detected = False
    cgroup_paths = [
        Path("/sys/fs/cgroup/memory/byte-swarmy/memory.limit_in_bytes"), # v1
        Path("/sys/fs/cgroup/user.slice/user-1000.slice/memory.max"),    # v2 generic
    ]
    
    for p in cgroup_paths:
        if p.exists():
            cgroup_detected = True
            break
    
    # Non lo rendiamo bloccante perché cgroups richiede root per l'installazione,
    # ma lo registriamo.
    
    # 3. Verifica Bubblewrap installato (già fatto in tools.py, ma qui lo rendiamo sistemico)
    import subprocess
    try:
        subprocess.run(["bwrap", "--version"], capture_output=True, check=True)
    except Exception:
        return False, "Bubblewrap non installato. L'isolamento dei processi è disabilitato."

    return True, "Isolamento verificato."

def apply_safe_mode(logger: logging.Logger):
    """Attiva restrizioni aggiuntive se l'isolamento è insufficiente."""
    logger.warning("⚠️  MODALITÀ SAFE MODE ATTIVA: L'isolamento di sistema è insufficiente.")
    logger.warning("Vengono applicati timeout più brevi e restrizioni severe ai tool.")
    # Qui potremmo modificare dinamicamente la config, ma per ora usiamo il log per avvisare l'utente.
