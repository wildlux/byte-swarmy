"""
persistent_memory.py — Memoria persistente tra task del worker.

Mantiene:
- user_profile: preferenze utente (linguaggio, stile, convenzioni)
- project_context: file esistenti, struttura, dipendenze
- common_errors: errori ricorrenti da evitare
- recent_files: ultimi file modificati

Salva su state/persistent_memory.json (caricato ad ogni avvio del worker).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


MEMORY_FILE = Path("state/persistent_memory.json")


def load_memory() -> dict:
    """Carica la memoria persistente da disco."""
    if not MEMORY_FILE.exists():
        return _default_memory()
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        # Merge con default per gestire nuovi campi
        default = _default_memory()
        default.update(data)
        return default
    except Exception:
        return _default_memory()


def save_memory(memory: dict) -> None:
    """Salva la memoria persistente su disco."""
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        memory["last_updated"] = time.time()
        MEMORY_FILE.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"WARNING: cannot save persistent memory: {e}")


def _default_memory() -> dict:
    """Struttura default della memoria."""
    return {
        "user_profile": {
            "preferred_language": "python",
            "style_preferences": [],
            "naming_conventions": [],
            "framework_preferences": [],
        },
        "project_context": {
            "existing_files": [],
            "main_modules": [],
            "dependencies": [],
            "entry_point": None,
        },
        "common_errors": [],
        "recent_files": [],  # ultimi 10 file modificati
        "task_history": [],  # ultimi 20 task completati
        "last_updated": 0,
    }


def record_file_created(filepath: str, description: str = "") -> None:
    """Registra che un file è stato creato/modificato."""
    mem = load_memory()
    
    # Aggiungi ai file esistenti (se non già presente)
    existing = mem["project_context"]["existing_files"]
    if filepath not in existing:
        existing.append(filepath)
        # Mantieni solo gli ultimi 50
        if len(existing) > 50:
            mem["project_context"]["existing_files"] = existing[-50:]
    
    # Aggiungi ai recent files
    recent = mem["recent_files"]
    # Rimuovi se già presente
    recent = [r for r in recent if r.get("path") != filepath]
    recent.insert(0, {
        "path": filepath,
        "description": description,
        "timestamp": time.time(),
    })
    mem["recent_files"] = recent[:10]
    
    save_memory(mem)


def record_error(error_type: str, error_message: str, context: str = "") -> None:
    """Registra un errore comune per evitare di ripeterlo."""
    mem = load_memory()
    errors = mem["common_errors"]
    
    # Verifica se simile a uno esistente
    for e in errors:
        if e.get("type") == error_type and error_message[:50] in e.get("message", ""):
            e["count"] = e.get("count", 0) + 1
            e["last_seen"] = time.time()
            save_memory(mem)
            return
    
    # Nuovo errore
    errors.append({
        "type": error_type,
        "message": error_message[:200],
        "context": context[:200],
        "count": 1,
        "first_seen": time.time(),
        "last_seen": time.time(),
    })
    # Mantieni solo gli ultimi 20
    mem["common_errors"] = errors[-20:]
    save_memory(mem)


def record_task_completed(task_id: str, title: str, result: str) -> None:
    """Registra un task completato nella history."""
    mem = load_memory()
    history = mem["task_history"]
    history.append({
        "task_id": task_id,
        "title": title[:80],
        "result": result[:200],
        "timestamp": time.time(),
    })
    # Mantieni solo gli ultimi 20
    mem["task_history"] = history[-20:]
    save_memory(mem)


def build_context_for_prompt() -> str:
    """Costruisce una stringa di contesto da inserire nel prompt del worker.
    
    Include:
    - File esistenti nel progetto
    - Errori comuni da evitare
    - Ultimi task completati
    """
    mem = load_memory()
    lines = []
    
    # File esistenti
    existing = mem["project_context"]["existing_files"]
    if existing:
        lines.append("## FILE ESISTENTI NEL PROGETTO")
        lines.append("(NON ricreare questi file, usa patch_code per modificarli)")
        for f in existing[-15:]:  # ultimi 15
            lines.append(f"  - {f}")
        lines.append("")
    
    # Errori comuni
    errors = mem["common_errors"]
    if errors:
        # Solo errori visti più di una volta
        recurring = [e for e in errors if e.get("count", 0) >= 2]
        if recurring:
            lines.append("## ERRORI COMUNI DA EVITARE")
            for e in recurring[-5:]:
                lines.append(f"  - [{e['type']}] {e['message'][:80]}")
            lines.append("")
    
    # Ultimi task
    history = mem["task_history"]
    if history:
        lines.append("## ULTIMI TASK COMPLETATI")
        for t in history[-5:]:
            lines.append(f"  - {t['title']}")
        lines.append("")
    
    return "\n".join(lines) if lines else "(nessun contesto persistente)"


def update_project_context() -> None:
    """Scansiona la cartella project/ e aggiorna i file esistenti."""
    project_root = Path("project")
    if not project_root.exists():
        return
    
    mem = load_memory()
    existing = []
    
    # Scan ricorsivo (max 30 file)
    for f in sorted(project_root.rglob("*")):
        if f.is_file() and ".git" not in f.parts:
            existing.append(str(f.relative_to(project_root)))
            if len(existing) >= 30:
                break
    
    mem["project_context"]["existing_files"] = existing
    save_memory(mem)
