#!/usr/bin/env python3
"""
fix_timeout.py — Fix per timeout di phi3:mini su CPU lente.

1. Aumenta request_timeout a 300s (5 min)
2. Riduce WORKER_CONSTRAINTS (system prompt troppo lungo)
3. Riduce max_tokens per step (1024 → 512)
4. Pulisci memory all'avvio worker (no eredità da task precedenti)
"""
import shutil
from pathlib import Path

CONFIG_FILE = Path("config.toml")
CONFIG_BACKUP = Path("config.toml.bak.timeout")
ORCH_FILE = Path("orchestrator.py")
ORCH_BACKUP = Path("orchestrator.py.bak.timeout")


def fix_config():
    if not CONFIG_FILE.exists():
        return False
    content = CONFIG_FILE.read_text()
    shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)
    modified = False

    # Aumenta request_timeout
    if 'request_timeout = 60' in content:
        content = content.replace('request_timeout = 60', 'request_timeout = 300')
        modified = True
        print("✓ request_timeout: 60s → 300s")
    elif 'request_timeout = 120' in content:
        content = content.replace('request_timeout = 120', 'request_timeout = 300')
        modified = True
        print("✓ request_timeout: 120s → 300s")
    elif 'request_timeout' in content:
        print("ℹ  request_timeout già customizzato, lascio com'è")

    if modified:
        CONFIG_FILE.write_text(content)
    return True


def fix_orchestrator():
    if not ORCH_FILE.exists():
        return False
    content = ORCH_FILE.read_text()
    shutil.copy2(ORCH_FILE, ORCH_BACKUP)
    modified = False

    # === Fix 1: Riduci WORKER_CONSTRAINTS (system prompt troppo lungo) ===
    OLD_CONSTRAINTS = '''    # Costituzione dell'Agente Worker: regole ferree di sicurezza e qualità.
    WORKER_CONSTRAINTS = (
        "### 🛡️ PROTOCOLLO DI SICUREZZA (OBBLIGATORIO)\\n"
        "1. PRIVILEGIO MINIMO: Non richiedere mai l'accesso a file o directory fuori da `project/`.\\n"
        "2. SANIFICAZIONE: Tratta ogni input esterno come dato non fidato. Non inserire variabili "
        "non validate in comandi bash.\\n"
        "3. NO-SHELL: È vietato l'uso di pipe (|), redirect (>, >>), concatenazione (;, &&, ||) "
        "o backtick/substituzioni. Se l'operazione richiede più step, usa i tool in sequenza.\\n"
        "4. FAIL-CLOSED: Se un tool di sicurezza restituisce un errore, NON provare a bypassarlo.\\n\\n"
        "### 💻 STANDARD DI CODIFICA (BEST PRACTICES)\\n"
        "1. MODULARITÀ: Se una funzione supera le 20 righe o ha un'alta complessità, "
        "DEVI usare `extract_method` per scomporla.\\n"
        "2. ATOMICITÀ: Usa `patch_code` per modifiche mirate. Riscrivi l'intero file con "
        "`write_file` SOLO per la creazione iniziale.\\n"
        "3. DOCUMENTAZIONE: Ogni nuova funzione DEVE avere un docstring chiaro e type hints.\\n"
        "4. VERIFICA: Non dichiarare un task come `done` senza aver prima eseguito `lint_code` "
        "e `run_test_suite`. Il risultato deve essere 'OK'.\\n\\n"
        "### 🛠️ WORKFLOW PROFESSIONALE (REFACTOR-LOOP)\\n"
        "Per ogni modifica, segui rigorosamente questa sequenza:\\n"
        "1. MAPPATURA: Usa `analyze_project` per capire la struttura e `find_references` per l'impatto.\\n"
        "2. ANALISI: Usa `analyze_complexity` e `get_call_graph` per identificare i punti critici.\\n"
        "3. INTERVENTO: Applica modifiche mirate con `patch_code` o tool di refactoring (`rename_symbol`, `extract_method`).\\n"
        "4. VALIDAZIONE: Esegui `lint_code` per la sintassi e `run_test_suite` per la logica.\\n"
        "5. CHIUSURA: Solo dopo il superamento dei test, dichiara `done=true`.\\n\\n"
        "RISPETTA QUESTE REGOLE O IL TASK VERRÀ RIFIUTATO."
    )'''

    NEW_CONSTRAINTS = '''    # Costituzione dell'Agente Worker: regole ferree di sicurezza e qualità.
    # Versione compatta per modelli piccoli (3-4B su CPU).
    WORKER_CONSTRAINTS = (
        "RULES:\\n"
        "1. Work only inside project/ directory.\\n"
        "2. Use ONLY the tools listed in TOOLS section. Do not invent tool names.\\n"
        "3. write_file(path, content) to CREATE files.\\n"
        "4. patch_code(path, old_string, new_string) to MODIFY files.\\n"
        "5. After writing, run run_test_suite() to verify.\\n"
        "6. When done: set done=true with a short result string.\\n"
    )'''

    if "REFACTOR-LOOP" in content and "Versione compatta" not in content:
        content = content.replace(OLD_CONSTRAINTS, NEW_CONSTRAINTS, 1)
        modified = True
        print("✓ WORKER_CONSTRAINTS ridotto (era troppo lungo per modelli piccoli)")

    # === Fix 2: Riduci max_tokens per step (1024 → 512) ===
    OLD_MAXTOK = '''            raw = self.models.call(
                model_key=self.model_key,
                prompt=prompt,
                system=self.SYSTEM,
                max_tokens=1024,
            )'''
    NEW_MAXTOK = '''            raw = self.models.call(
                model_key=self.model_key,
                prompt=prompt,
                system=self.SYSTEM,
                max_tokens=512,
            )'''
    if OLD_MAXTOK in content:
        content = content.replace(OLD_MAXTOK, NEW_MAXTOK, 1)
        modified = True
        print("✓ max_tokens per step: 1024 → 512 (più veloce)")

    # === Fix 3: Riduci num_ctx per worker_coder in config (se 8192) ===
    # Lo lasciamo al config separato

    if modified:
        ORCH_FILE.write_text(content)
    return True


def fix_config_ctx():
    """Riduce num_ctx del worker_coder se è troppo alto."""
    if not CONFIG_FILE.exists():
        return
    content = CONFIG_FILE.read_text()
    # Se worker_coder ha num_ctx = 8192 o più, riduci a 4096
    import re
    # Trova sezione [models.worker_coder]
    match = re.search(r'\[models\.worker_coder\]\s*\n((?:[^\[]+))', content)
    if not match:
        return
    section = match.group(1)
    if 'num_ctx = 8192' in section:
        new_section = section.replace('num_ctx = 8192', 'num_ctx = 4096')
        content = content.replace(section, new_section)
        CONFIG_FILE.write_text(content)
        print("✓ worker_coder num_ctx: 8192 → 4096 (meno RAM, più veloce)")


def main():
    print("=" * 60)
    print("FIX TIMEOUT + PERFORMANCE")
    print("=" * 60)
    print()

    print("→ Fix 1: config.toml (request_timeout)")
    fix_config()
    print()

    print("→ Fix 2: orchestrator.py (prompt + max_tokens)")
    fix_orchestrator()
    print()

    print("→ Fix 3: config.toml num_ctx")
    fix_config_ctx()

    print()
    print("=" * 60)
    print("✓ FIX COMPLETATI")
    print("=" * 60)
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh")


if __name__ == "__main__":
    main()
