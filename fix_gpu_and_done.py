#!/usr/bin/env python3
"""
fix_gpu_and_done.py — 2 fix:

1. orchestrator.py: l'auditor auto-APPROVE solo se è stato scritto un file
   (o se ha fatto run_test_suite, lint_code, ecc.)
2. config.toml: imposta OLLAMA_GPU=1 se disponibile (via env)
3. Crea uno script di test diretto per phi3:mini con GPU
"""
import re
import shutil
from pathlib import Path

ORCH_FILE = Path("orchestrator.py")
ORCH_BACKUP = Path("orchestrator.py.bak.gpu")


def fix_audit():
    """L'auditor deve APPROVARE solo se il worker ha fatto qualcosa di utile."""
    if not ORCH_FILE.exists():
        return
    content = ORCH_FILE.read_text()
    shutil.copy2(ORCH_FILE, ORCH_BACKUP)
    modified = False

    # Cerca l'auditor auto-APPROVE
    OLD = '''def audit(self, task: dict, worker_result: str, worker_history: list) -> dict:
        """Auditor disabilitato per CPU lente - APPROVE automatico."""
        return {"decision": "APPROVE", "feedback": "auto-approved (auditor disabled)", "severity": "LOW"}'''

    NEW = '''def audit(self, task: dict, worker_result: str, worker_history: list) -> dict:
        """Auditor semplificato: APPROVA solo se il worker ha fatto qualcosa di utile."""
        # Conta tool utili chiamati
        useful_tools = {"write_file", "patch_code", "run_test_suite", "lint_code",
                       "git_commit", "rename_symbol", "extract_method"}
        useful_count = 0
        for event in worker_history:
            if event.get("type") == "tool_result":
                content = event.get("content", "")
                for tool in useful_tools:
                    if f"tool {tool}(" in content or f"{tool}(" in content:
                        useful_count += 1
                        break
        # Se ha fatto almeno 1 tool utile, APPROVE
        if useful_count > 0:
            return {"decision": "APPROVE",
                   "feedback": f"auto-approved ({useful_count} useful tool calls)",
                   "severity": "LOW"}
        # Altrimenti REJECT con feedback utile
        return {"decision": "REJECT",
               "feedback": "No useful tools called (write_file, patch_code, etc.). Create or modify a file first.",
               "severity": "HIGH"}'''

    if OLD in content:
        content = content.replace(OLD, NEW, 1)
        modified = True
        print("✓ Auditor: APPROVE solo se il worker ha scritto/modificato file")

    # === Bonus: fix _build_initial_prompt con istruzioni più chiare ===
    OLD_PROMPT = '''    def _build_initial_prompt(self, task: dict, context: str) -> str:
        return (
            f"## TASK\\n{task.get('title', '')}\\n\\n"
            f"## DESCRIPTION\\n{task.get('description', '')}\\n\\n"
            f"## CONTEXT\\n{context}\\n\\n"
            f"## PROJECT STATE\\n{self._project_state()}\\n\\n"
            f"## SYSTEM CONSTRAINTS\\n{Planner.WORKER_CONSTRAINTS}\\n\\n"
            "Plan: 1) analyze_project to map the codebase, 2) patch_code for precise changes, "
            "3) run_test_suite to verify, 4) git_commit, 5) done=true with result.\\n\\n"
            "First step (JSON only):"
        )'''

    NEW_PROMPT = '''    def _build_initial_prompt(self, task: dict, context: str) -> str:
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

    if OLD_PROMPT in content:
        content = content.replace(OLD_PROMPT, NEW_PROMPT, 1)
        modified = True
        print("✓ Prompt worker: istruzioni più dirette (write_file FIRST)")

    if modified:
        ORCH_FILE.write_text(content)
        try:
            compile(content, "orchestrator.py", "exec")
            print("✓ Verifica sintassi OK")
        except SyntaxError as e:
            print(f"❌ Errore sintassi: {e}")
            shutil.copy2(ORCH_BACKUP, ORCH_FILE)


def check_gpu():
    """Verifica se Ollama può usare la GPU."""
    import subprocess
    print("\n=== GPU CHECK ===")

    # 1. nvidia-smi
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                                "--format=csv,noheader"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            print(f"✓ GPU NVIDIA trovata: {result.stdout.strip()}")
            print("\nPer abilitare GPU in Ollama:")
            print("  1. Verifica driver: nvidia-smi (già fatto)")
            print("  2. Verifica CUDA toolkit: nvcc --version")
            print("  3. Reinstalla Ollama con supporto CUDA:")
            print("     curl -fsSL https://ollama.com/install.sh | sh")
            print("  4. Riavvia Ollama: sudo systemctl restart ollama")
            print("  5. Test: ollama run phi3:mini 'hello' (dovrebbe essere 5-10x più veloce)")
            return True
        else:
            print("○ Nessuna GPU NVIDIA trovata")
    except FileNotFoundError:
        print("○ nvidia-smi non installato (nessuna GPU NVIDIA)")
    except Exception as e:
        print(f"○ Check GPU fallito: {e}")

    # 2. AMD/Intel GPU check
    try:
        result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
        gpu_lines = [l for l in result.stdout.split("\n") if "VGA" in l or "3D" in l or "Display" in l]
        if gpu_lines:
            print("\nController video trovati:")
            for line in gpu_lines:
                print(f"  {line}")
    except Exception:
        pass

    print("\n→ Ollama sta usando la CPU (phi3:mini runner: ggml)")
    print("  Per velocizzare senza GPU:")
    print("  - Usa modello più piccolo: qwen2.5:1.5b (5-10x più veloce di phi3:mini)")
    print("  - Riduci num_ctx a 2048")
    print("  - Riduci max_tokens a 256")
    return False


def main():
    print("=" * 60)
    print("FIX AUDITOR + GPU CHECK")
    print("=" * 60)
    print()
    print("→ Fix auditor (APPROVE solo se file scritto)")
    fix_audit()
    check_gpu()
    print()
    print("=" * 60)
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  python -c \"import sqlite3; c=sqlite3.connect('tasks/queue.db'); c.execute('DELETE FROM tasks'); c.commit()\"")
    print("  ./avvia.sh")


if __name__ == "__main__":
    main()
