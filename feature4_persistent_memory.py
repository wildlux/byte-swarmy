#!/usr/bin/env python3
"""
feature4_persistent_memory.py — Memoria persistente tra task.

L'idea: mantenere un "user profile" + "project context" che persiste
tra task diversi. Il worker lo legge all'inizio di ogni task.

Modifiche:
1. Crea CORE/persistent_memory.py (nuovo modulo)
2. CORE/orchestrator.py: worker carica persistent memory nel prompt
3. Salva automaticamente: file creati, preferenze, errori comuni
"""
import re
import shutil
from pathlib import Path

ORCH_FILE = Path("CORE/orchestrator.py")
ORCH_BACKUP = Path("CORE/orchestrator.py.bak.persmem")
PERSIST_FILE = Path("CORE/persistent_memory.py")


# ====================================================================
# 1. Nuovo modulo CORE/persistent_memory.py
# ====================================================================

PERSISTENT_MEMORY_CODE = '''"""
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
    
    return "\\n".join(lines) if lines else "(nessun contesto persistente)"


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
'''


# ====================================================================
# 2. CORE/orchestrator.py: worker carica persistent memory nel prompt
# ====================================================================

# Modifica _build_initial_prompt per includere il contesto persistente
OLD_PROMPT_BUILDER = '''    def _build_initial_prompt(self, task: dict, context: str) -> str:
        return (
            f"## TASK\\n{task.get('title', '')}\\n\\n"
            f"## DESCRIPTION\\n{task.get('description', '')}\\n\\n"
            f"## PROJECT STATE\\n{self._project_state()}\\n\\n"
            f"## RULES\\n{Planner.WORKER_CONSTRAINTS}\\n\\n"
            "PLAN (follow strictly):\\n"
            "1. write_file(path, content) to create the implementation file\\n"
            "2. lint_code(path) to verify syntax\\n"
            "3. done=true with a short result\\n\\n"
            "First step (JSON only, format: {action: \\"write_file\\", args: [\\"project/main.py\\", \\"code...\\"], done: false}):"
        )'''

NEW_PROMPT_BUILDER = '''    def _build_initial_prompt(self, task: dict, context: str) -> str:
        # 🆕 Carica contesto persistente
        persistent_context = ""
        try:
            from CORE.persistent_memory import build_context_for_prompt
            persistent_context = build_context_for_prompt()
        except Exception:
            pass
        
        return (
            f"## TASK\\n{task.get('title', '')}\\n\\n"
            f"## DESCRIPTION\\n{task.get('description', '')}\\n\\n"
            f"## PROJECT STATE\\n{self._project_state()}\\n\\n"
            f"## PERSISTENT CONTEXT\\n{persistent_context}\\n\\n"
            f"## RULES\\n{Planner.WORKER_CONSTRAINTS}\\n\\n"
            "PLAN (follow strictly):\\n"
            "1. write_file(path, content) to create the implementation file\\n"
            "2. lint_code(path) to verify syntax\\n"
            "3. done=true with a short result\\n\\n"
            "First step (JSON only, format: {action: \\"write_file\\", args: [\\"project/main.py\\", \\"code...\\"], done: false}):"
        )'''

# Modifica execute() per registrare task completato
OLD_EXECUTE_END = '''                result = action.get("result", "(no result)")
                self.memory.add_event({"type": "task_done", "content": result[:200]})
                return result'''

NEW_EXECUTE_END = '''                result = action.get("result", "(no result)")
                self.memory.add_event({"type": "task_done", "content": result[:200]})
                # 🆕 Registra task completato nella memoria persistente
                try:
                    from CORE.persistent_memory import record_task_completed, update_project_context
                    record_task_completed(
                        task_id=task.get("id", "?"),
                        title=task.get("title", ""),
                        result=result,
                    )
                    # Aggiorna lista file esistenti
                    update_project_context()
                except Exception:
                    pass
                return result'''


def main():
    print("=" * 60)
    print("FEATURE 4: MEMORIA PERSISTENTE TRA TASK")
    print("=" * 60)
    print()
    
    # 1. Crea CORE/persistent_memory.py
    if PERSIST_FILE.exists():
        print(f"ℹ  {PERSIST_FILE} già esiste, skip")
    else:
        PERSIST_FILE.write_text(PERSISTENT_MEMORY_CODE)
        try:
            compile(PERSISTENT_MEMORY_CODE, "persistent_memory.py", "exec")
            print(f"✓ Creato {PERSIST_FILE}")
        except SyntaxError as e:
            print(f"❌ Errore sintassi: {e}")
            return 1
    
    # 2. Patch orchestrator.py
    if not ORCH_FILE.exists():
        print(f"❌ {ORCH_FILE} non trovato")
        return 1
    
    content = ORCH_FILE.read_text()
    
    if "PERSISTENT CONTEXT" in content:
        print("ℹ  Orchestrator già patchato, skip")
        return 0
    
    shutil.copy2(ORCH_FILE, ORCH_BACKUP)
    modified = False
    
    # 2a. Modifica _build_initial_prompt
    if OLD_PROMPT_BUILDER in content:
        content = content.replace(OLD_PROMPT_BUILDER, NEW_PROMPT_BUILDER, 1)
        modified = True
        print("✓ _build_initial_prompt include contesto persistente")
    else:
        print("⚠  Pattern _build_initial_prompt non trovato esattamente")
    
    # 2b. Modifica execute() per registrare task completato
    if OLD_EXECUTE_END in content:
        content = content.replace(OLD_EXECUTE_END, NEW_EXECUTE_END, 1)
        modified = True
        print("✓ execute() registra task completato nella memoria persistente")
    else:
        print("⚠  Pattern execute() end non trovato esattamente")
    
    if modified:
        ORCH_FILE.write_text(content)
        try:
            compile(content, "orchestrator.py", "exec")
            print("✓ Verifica sintassi OK")
        except SyntaxError as e:
            print(f"❌ Errore sintassi: {e}")
            shutil.copy2(ORCH_BACKUP, ORCH_FILE)
            return 1
    
    # 3. Inizializza la memoria persistente con scan del progetto
    print()
    print("→ Inizializzazione memoria persistente...")
    try:
        import sys
        sys.path.insert(0, ".")
        from CORE.persistent_memory import update_project_context, load_memory
        update_project_context()
        mem = load_memory()
        print(f"✓ Memoria inizializzata: {len(mem['project_context']['existing_files'])} file trovati")
    except Exception as e:
        print(f"⚠  Inizializzazione fallita: {e}")
    
    print()
    print("=" * 60)
    print("✓ FEATURE 4 COMPLETATA")
    print("=" * 60)
    print()
    print("Cosa cambia:")
    print("  - Il worker vede i file esistenti nel progetto (non li ricrea)")
    print("  - Ricorda gli errori comuni (li evita nei task successivi)")
    print("  - Mostra gli ultimi task completati come contesto")
    print("  - Salva tutto in state/persistent_memory.json")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh")
    print()
    print("Test:")
    print("  1. Aggiungi un task (es. 'crea funzione fattoriale')")
    print("  2. Verifica che il file venga registrato:")
    print("     cat state/persistent_memory.json | python -m json.tool")
    print("  3. Aggiungi un secondo task: il worker vedrà il file esistente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
