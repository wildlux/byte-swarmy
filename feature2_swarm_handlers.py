#!/usr/bin/env python3
"""
feature2_swarm_handlers.py — Handler diretti per swarm commands.

Quando un task ha intent di tipo swarm_command (es. swarm_status, show_logs),
l'orchestratore lo gestisce direttamente senza passare dal worker LLM.

Modifiche:
1. CORE/orchestrator.py: aggiunge _handle_swarm_command() e lo usa in _tick()
2. Risultato salvato come result del task (visibile nella GUI)
"""
import re
import shutil
from pathlib import Path

ORCH_FILE = Path("CORE/orchestrator.py")
ORCH_BACKUP = Path("CORE/orchestrator.py.bak.swarmcmd")


# ====================================================================
# 1. Aggiungi metodo _handle_swarm_command alla classe Orchestrator
# ====================================================================

SWARM_HANDLER_METHOD = '''
    # ------------------------------------------------------------------
    # 🆕 Swarm command handlers (no LLM needed)
    # ------------------------------------------------------------------

    def _handle_swarm_command(self, task: dict, intent: str) -> str:
        """Gestisce direttamente i comandi swarm senza usare il worker LLM.
        Ritorna il risultato testuale da salvare come result del task.
        """
        try:
            if intent == "swarm_status":
                return self._cmd_swarm_status()
            elif intent == "list_tasks":
                return self._cmd_list_tasks()
            elif intent == "show_logs":
                return self._cmd_show_logs()
            elif intent == "pause_swarm":
                return self._cmd_pause_swarm()
            elif intent == "resume_swarm":
                return self._cmd_resume_swarm()
            elif intent == "inspect_memory":
                return self._cmd_inspect_memory()
            elif intent == "cancel_task":
                return self._cmd_cancel_task(task)
            elif intent == "run_audit":
                return self._cmd_run_audit()
            else:
                return f"unknown swarm command: {intent}"
        except Exception as e:
            self.log.error(f"swarm command {intent} failed: {e}")
            return f"ERROR: {e}"

    def _cmd_swarm_status(self) -> str:
        """Stato completo dello swarm."""
        stats = self.queue.stats()
        models_loaded = self.models.list_models()
        timestral_state = "n/a"
        if self.timestral:
            advice = self.timestral.get_advice()
            timestral_state = advice.action
            if advice.sample:
                timestral_state += f" (CPU {advice.sample.cpu_temp_max:.0f}°C, load {advice.sample.cpu_load*100:.0f}%)"
        
        lines = [
            "🐝 BYTE-SWARMY Status",
            "=" * 40,
            f"Coda task: {stats}",
            f"Modelli Ollama disponibili: {len(models_loaded)}",
            f"Modello attivo: {self.models.current_model or 'nessuno'}",
            f"Stato timestral: {timestral_state}",
            f"Agenti in memoria: {len(self.memories)}",
            f"Running: {self.running}",
        ]
        return "\\n".join(lines)

    def _cmd_list_tasks(self) -> str:
        """Lista tutti i task nella coda."""
        tasks = self.queue.get_all_tasks()
        if not tasks:
            return "Nessun task nella coda."
        
        lines = [f"📋 Coda task ({len(tasks)} totali):", "=" * 60]
        for t in tasks[:20]:  # max 20
            status_icon = {
                "pending": "⏳", "running": "▶", "done": "✓",
                "retry": "🔄", "stuck": "⛔", "planned": "📝",
                "needs_human": "👤"
            }.get(t.get("status", ""), "?")
            lines.append(f"{status_icon} [{t['status']:10}] {t['id']} | {t.get('title', '')[:50]}")
        return "\\n".join(lines)

    def _cmd_show_logs(self) -> str:
        """Ultime 30 righe di log."""
        try:
            log_file = Path(self.config["logging"]["file"])
            if not log_file.exists():
                return "Log file non trovato."
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            # Filtra timestral (troppo verboso)
            filtered = [l for l in lines if "timestral" not in l.lower()][-30:]
            return "📜 Ultimi log:\\n" + "\\n".join(filtered)
        except Exception as e:
            return f"ERROR reading logs: {e}"

    def _cmd_pause_swarm(self) -> str:
        """Mette in pausa lo swarm."""
        self.running = False
        return "⏸ Swarm messo in pausa. Usa 'resume swarm' per riprendere."

    def _cmd_resume_swarm(self) -> str:
        """Riprende lo swarm."""
        self.running = True
        return "▶ Swarm ripreso."

    def _cmd_inspect_memory(self) -> str:
        """Ispeziona memoria agenti."""
        if not self.memories:
            return "Nessun agente ha memoria attiva."
        
        lines = ["🧠 Memoria agenti:", "=" * 40]
        for agent_id, mem in self.memories.items():
            try:
                history = mem.get_history() if hasattr(mem, 'get_history') else []
                lines.append(f"\\n{agent_id}:")
                lines.append(f"  Eventi: {len(history)}")
                if history:
                    last = history[-1] if history else {}
                    lines.append(f"  Ultimo: {last.get('type', '?')} - {str(last.get('content', ''))[:80]}")
            except Exception as e:
                lines.append(f"  ERROR: {e}")
        return "\\n".join(lines)

    def _cmd_cancel_task(self, task: dict) -> str:
        """Cancella un task (quello corrente o specificato nel context)."""
        # Estrai task_id dal context se presente
        import json
        target_id = None
        try:
            ctx = json.loads(task.get("context", "{}"))
            target_id = ctx.get("params", {}).get("task_id")
        except Exception:
            pass
        
        if not target_id:
            # Cancella tutti i task pending
            try:
                with self.queue._get_conn() as conn:
                    cur = conn.execute("DELETE FROM tasks WHERE status = 'pending'")
                    deleted = cur.rowcount
                    conn.commit()
                return f"🗑 Cancellati {deleted} task pending."
            except Exception as e:
                return f"ERROR: {e}"
        else:
            try:
                with self.queue._get_conn() as conn:
                    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (target_id,))
                    conn.commit()
                if cur.rowcount > 0:
                    return f"🗑 Task {target_id} cancellato."
                else:
                    return f"⚠ Task {target_id} non trovato."
            except Exception as e:
                return f"ERROR: {e}"

    def _cmd_run_audit(self) -> str:
        """Esegue un audit veloce del progetto."""
        try:
            project_root = Path(self.config["paths"]["project_root"])
            files = list(project_root.rglob("*.py"))
            total_lines = 0
            for f in files:
                try:
                    total_lines += sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
                except Exception:
                    pass
            
            lines = [
                "🔍 Audit progetto:",
                "=" * 40,
                f"File Python: {len(files)}",
                f"Linee totali: {total_lines}",
                f"Directory: {project_root}",
            ]
            if files:
                lines.append("\\nFile:")
                for f in files[:10]:
                    lines.append(f"  - {f.relative_to(project_root)}")
                if len(files) > 10:
                    lines.append(f"  ... e altri {len(files) - 10}")
            return "\\n".join(lines)
        except Exception as e:
            return f"ERROR: {e}"

'''


# ====================================================================
# 2. Modifica _tick per intercettare swarm commands
# ====================================================================

TICK_OLD = '''        # 6. Dispatch task
        task = self.queue.next_pending()
        if not task:
            return  # coda vuota, aspetta

        self.log.info(f"dispatching {task['id']}: {task.get('title', '')[:80]}")'''

TICK_NEW = '''        # 6. Dispatch task
        task = self.queue.next_pending()
        if not task:
            return  # coda vuota, aspetta

        # 🆕 Intercetta swarm commands (gestione diretta, no LLM)
        swarm_intent = self._extract_swarm_intent(task)
        if swarm_intent:
            self.log.info(f"swarm command: {swarm_intent} (handling directly)")
            try:
                result = self._handle_swarm_command(task, swarm_intent)
                self.queue.mark_done(task["id"], result)
                self.log.info(f"swarm command {swarm_intent} done")
            except Exception as e:
                self.queue.mark_failed(task["id"], str(e))
                self.log.error(f"swarm command failed: {e}")
            return  # non passare al worker

        self.log.info(f"dispatching {task['id']}: {task.get('title', '')[:80]}")'''

# Aggiungi metodo helper per estrarre l'intent
HELPER_METHOD = '''
    def _extract_swarm_intent(self, task: dict) -> str:
        """Estrae l'intent swarm dal task context, se presente."""
        try:
            import json
            ctx_raw = task.get("context", "")
            if not ctx_raw:
                return None
            ctx = json.loads(ctx_raw)
            intent = ctx.get("intent")
            swarm_intents = {
                "swarm_status", "list_tasks", "show_logs", "pause_swarm",
                "resume_swarm", "inspect_memory", "cancel_task", "run_audit",
            }
            return intent if intent in swarm_intents else None
        except (json.JSONDecodeError, TypeError):
            return None

'''


def main():
    print("=" * 60)
    print("FEATURE 2: SWARM COMMAND HANDLERS")
    print("=" * 60)
    print()
    
    if not ORCH_FILE.exists():
        print(f"❌ {ORCH_FILE} non trovato")
        return 1
    
    content = ORCH_FILE.read_text()
    
    if "_handle_swarm_command" in content:
        print("ℹ  Swarm handlers già presenti, skip")
        return 0
    
    shutil.copy2(ORCH_FILE, ORCH_BACKUP)
    
    # 1. Aggiungi metodo _handle_swarm_command + helpers
    # Inserisci prima di _handle_signal
    insert_point = "    def _handle_signal(self, signum, frame) -> None:"
    if insert_point not in content:
        print("❌ Punto inserimento non trovato (_handle_signal)")
        return 1
    
    content = content.replace(
        insert_point,
        SWARM_HANDLER_METHOD + "\n" + HELPER_METHOD + insert_point,
        1
    )
    print("✓ Aggiunti metodi _handle_swarm_command + helpers + _extract_swarm_intent")
    
    # 2. Modifica _tick per intercettare swarm commands
    if TICK_OLD in content:
        content = content.replace(TICK_OLD, TICK_NEW, 1)
        print("✓ _tick intercetta swarm commands prima del dispatch")
    else:
        print("⚠  Pattern _tick non trovato esattamente")
        return 1
    
    ORCH_FILE.write_text(content)
    
    try:
        compile(content, "orchestrator.py", "exec")
        print("✓ Verifica sintassi OK")
    except SyntaxError as e:
        print(f"❌ Errore sintassi: {e}")
        shutil.copy2(ORCH_BACKUP, ORCH_FILE)
        return 1
    
    print()
    print("=" * 60)
    print("✓ FEATURE 2 COMPLETATA")
    print("=" * 60)
    print()
    print("Comandi swarm ora gestiti direttamente (no LLM):")
    print("  - swarm status     → stato dello swarm")
    print("  - list tasks       → lista task in coda")
    print("  - show logs        → ultimi 30 log")
    print("  - pause swarm      → mette in pausa")
    print("  - resume swarm     → riprende")
    print("  - inspect memory   → memoria agenti")
    print("  - cancel task      → cancella task")
    print("  - run audit        → audit progetto")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh")
    print()
    print("Test dalla Quick Command bar:")
    print("  - 'swarm status'")
    print("  - 'mostra log'")
    print("  - 'lista task'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
