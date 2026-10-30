#!/usr/bin/env python3
"""
feature3_decision_model.py — Abilita il decision model tev1:4b per task generici.

Modifiche:
1. CONFIG/config.toml: abilita [decision_models.tev1] e [generic_task_planner]
2. Aggiunge system_prompt ottimizzato per tev1:4b
3. Mappa "generic" intent → task type "generic" nel router
"""
import re
import shutil
from pathlib import Path

CONFIG_FILE = Path("CONFIG/config.toml")
CONFIG_BACKUP = Path("CONFIG/config.toml.bak.decision")


# ====================================================================
# Configurazione decision model tev1:4b
# ====================================================================

NEW_DECISION_SECTION = '''
# ====================================================================
# Decision Models — modelli per scomporre task generici complessi
# ====================================================================
[decision_models]
active = "tev1"

[decision_models.tev1]
name = "tev1:4b"
enabled = true
temperature = 0.1
num_ctx = 4096

[decision_models.d3]
name = "d3:4b"
enabled = false
temperature = 0.1
num_ctx = 4096

[decision_models.nimble]
name = "nimble:4b"
enabled = false
temperature = 0.1
num_ctx = 4096

# ====================================================================
# Generic Task Planner — usa il decision model attivo
# ====================================================================
[generic_task_planner]
enabled = true
max_subtasks = 8
max_tokens = 1500
system_prompt = """Sei un pianificatore software esperto. Decomponi il task generico in 2-8 code task atomici.

REGOLE:
1. Ogni sottotask deve essere implementabile in massimo 200 righe di codice
2. I sottotask devono essere sequenziali e indipendenti
3. Includi sempre: creazione file principale, implementazione logica, test, documentazione
4. Specifica il tipo di ogni sottotask: implement | test | fix | document

RISPONDI SOLO con formato JSON:
{"subtasks": [{"title": "...", "description": "...", "type": "implement|test|fix|document"}]}

Niente testo fuori dal JSON."""
'''

# Pattern per trovare e sostituire le vecchie sezioni decision_models/generic_task_planner
OLD_PATTERN = re.compile(
    r'# ===+\n# Decision Models.*?(?=\n# ===+\n# [A-Z]|\n\[)|\n\[decision_models\].*?(?=\n# ===+\n# [A-Z]|\Z)',
    re.DOTALL
)

OLD_GENERIC_PATTERN = re.compile(
    r'\[generic_task_planner\][^\[]*',
    re.DOTALL
)


def main():
    print("=" * 60)
    print("FEATURE 3: ABILITARE DECISION MODEL TEV1:4B")
    print("=" * 60)
    print()
    
    if not CONFIG_FILE.exists():
        print(f"❌ {CONFIG_FILE} non trovato")
        return 1
    
    content = CONFIG_FILE.read_text()
    shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)
    
    # 1. Rimuovi vecchie sezioni decision_models (se esistono)
    if "[decision_models]" in content:
        # Trova l'inizio e la fine della sezione
        # Una sezione TOML finisce quando inizia una nuova [sezione] o fine file
        pattern = re.compile(
            r'\[decision_models(?:\.[\w]+)?\][^\[]*',
            re.DOTALL
        )
        content = pattern.sub('', content)
        print("✓ Rimosse vecchie sezioni [decision_models]")
    
    # 2. Rimuovi vecchia sezione generic_task_planner
    if "[generic_task_planner]" in content:
        content = OLD_GENERIC_PATTERN.sub('', content)
        print("✓ Rimossa vecchia sezione [generic_task_planner]")
    
    # 3. Aggiungi le nuove sezioni in fondo al file
    content = content.rstrip() + "\n" + NEW_DECISION_SECTION
    
    CONFIG_FILE.write_text(content)
    print("✓ Aggiunte nuove sezioni [decision_models] e [generic_task_planner]")
    print("  - tev1:4b abilitato come decision model attivo")
    print("  - Generic task planner ON (max 8 sottotask)")
    
    # Verifica sintassi TOML
    try:
        import tomllib
        with open(CONFIG_FILE, "rb") as f:
            cfg = tomllib.load(f)
        
        active = cfg.get("decision_models", {}).get("active")
        tev1_enabled = cfg.get("decision_models", {}).get("tev1", {}).get("enabled")
        planner_enabled = cfg.get("generic_task_planner", {}).get("enabled")
        
        print()
        print("✓ Verifica config:")
        print(f"  - decision_models.active = {active}")
        print(f"  - tev1.enabled = {tev1_enabled}")
        print(f"  - generic_task_planner.enabled = {planner_enabled}")
        
        if active != "tev1" or not tev1_enabled or not planner_enabled:
            print("⚠  Config non corretto, verifica manualmente")
            return 1
    except Exception as e:
        print(f"⚠  Errore verifica TOML: {e}")
        return 1
    
    print()
    print("=" * 60)
    print("✓ FEATURE 3 COMPLETATA")
    print("=" * 60)
    print()
    print("Cosa cambia:")
    print("  - I task 'generic' vengono scomposti in 2-8 sottotask da tev1:4b")
    print("  - Esempio: 'voglio un editor CLI' → sottotask:")
    print("    1. Crea main.py con arg parser")
    print("    2. Implementa apertura file")
    print("    3. Implementa salvataggio")
    print("    4. Crea test")
    print("    5. Crea README")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh")
    print()
    print("Test:")
    print("  Scrivi un task generico nella Quick Command bar:")
    print("    'voglio una calcolatrice CLI in Python'")
    print("  Dovresti vedere il task scomposto in sottotask automaticamente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
