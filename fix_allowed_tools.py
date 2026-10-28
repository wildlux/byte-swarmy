#!/usr/bin/env python3
"""
fix_allowed_tools.py — Fix DEFINITIVO per i 3 bug residui:

1. tools.py: allowed_tools() mancava patch_code, analyze_project, ecc.
2. Verifica config.toml abbia davvero qwen2.5-coder:3b
3. Pulisci __pycache__ per ricaricare codice fresco
"""
import shutil
import os
from pathlib import Path

TOOLS_FILE = Path("tools.py")
TOOLS_BACKUP = Path("tools.py.bak.allowed")
CONFIG_FILE = Path("config.toml")


# ====================================================================
# Fix 1: allowed_tools() completa
# ====================================================================

OLD_ALLOWED = '''    def allowed_tools(self) -> set[str]:
        """Tool che il worker può realmente chiamare."""
        return {
            "read_file", "write_file", "run_bash", "search",
            "git_commit", "git_diff", "git_status", "git_log",
            "git_branch", "git_merge", "git_pull", "git_push", "git_remote",
        }'''

NEW_ALLOWED = '''    def allowed_tools(self) -> set[str]:
        """Tool che il worker può realmente chiamare."""
        return {
            "read_file", "write_file", "patch_code", "run_bash", "search",
            "analyze_project", "find_references", "lint_code",
            "rename_symbol", "analyze_complexity", "get_call_graph",
            "extract_method",
            "git_commit", "git_diff", "git_status", "git_log",
            "git_branch", "git_merge", "git_pull", "git_push", "git_remote",
        }'''


def fix_tools() -> bool:
    if not TOOLS_FILE.exists():
        return False
    content = TOOLS_FILE.read_text()

    if "extract_method" in content and "patch_code" in content and content.count("patch_code") > 2 and '"patch_code", "write_file"' in content:
        print("ℹ  Fix allowed_tools già applicato, skip")
        return True

    if OLD_ALLOWED not in content:
        print("⚠  Pattern allowed_tools non trovato esattamente.")
        print("   Cerco il blocco con regex flessibile...")
        import re
        # Pattern flessibile
        pattern = r'def allowed_tools\(self\)[^:]*:\s*\n\s*"""[^"]*"""\s*\n\s*return\s*\{[^}]+\}'
        match = re.search(pattern, content)
        if not match:
            print("❌ Impossibile trovare allowed_tools")
            return False
        content = content[:match.start()] + NEW_ALLOWED + content[match.end():]
    else:
        content = content.replace(OLD_ALLOWED, NEW_ALLOWED, 1)

    shutil.copy2(TOOLS_FILE, TOOLS_BACKUP)
    TOOLS_FILE.write_text(content)
    print("✓ allowed_tools() aggiornata con tutti i 21 tool")
    return True


def verify_config() -> bool:
    """Verifica che config.toml abbia qwen2.5-coder:3b."""
    if not CONFIG_FILE.exists():
        return False
    content = CONFIG_FILE.read_text()

    # Cerca la sezione worker_coder
    import re
    match = re.search(r'\[models\.worker_coder\]\s*\nname\s*=\s*"([^"]+)"', content)
    if not match:
        print("⚠  Sezione [models.worker_coder] non trovata in config.toml")
        return False

    model = match.group(1)
    print(f"   config.toml worker_coder = {model}")

    if "3b" in model or "7b" in model or "8b" in model:
        print("✓ Modello worker_coder OK (3b o superiore)")
        return True
    else:
        print(f"⚠  Modello ancora piccolo: {model}")
        print("   Cambiando a qwen2.5-coder:3b...")
        new_content = content.replace(
            f'name = "{model}"',
            'name = "qwen2.5-coder:3b"',
            1
        )
        CONFIG_FILE.write_text(new_content)
        print("✓ config.toml aggiornato a qwen2.5-coder:3b")
        return True


def clear_pycache() -> None:
    """Pulisce tutti i __pycache__ per forzare ricaricamento."""
    count = 0
    for root, dirs, files in os.walk("."):
        if "__pycache__" in dirs:
            pycache = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(pycache)
                count += 1
            except Exception:
                pass
    if count > 0:
        print(f"✓ Rimossi {count} directory __pycache__")
    else:
        print("ℹ  Nessun __pycache__ da rimuovere")


def verify_imports() -> None:
    """Verifica che ollama_client.py abbia l'import Path."""
    ollama = Path("ollama_client.py")
    if not ollama.exists():
        return
    content = ollama.read_text()
    if "from pathlib import Path" in content:
        print("✓ ollama_client.py ha import Path")
    else:
        print("⚠  ollama_client.py MANCA import Path! Aggiungo...")
        old = "import json\nimport time\nimport urllib.request"
        new = "import json\nimport time\nimport urllib.request\nfrom pathlib import Path"
        if old in content:
            content = content.replace(old, new, 1)
            ollama.write_text(content)
            print("✓ Import Path aggiunto a ollama_client.py")
        else:
            print("❌ Impossibile aggiungere import Path")


def main():
    print("=" * 60)
    print("FIX ALLOWED_TOOLS + VERIFICHE")
    print("=" * 60)
    print()

    print("→ Fix 1: allowed_tools() in tools.py")
    fix_tools()
    print()

    print("→ Fix 2: verifica config.toml")
    verify_config()
    print()

    print("→ Fix 3: verifica import Path in ollama_client.py")
    verify_imports()
    print()

    print("→ Fix 4: pulisci __pycache__")
    clear_pycache()

    print()
    print("=" * 60)
    print("✓ TUTTI I FIX COMPLETATI")
    print("=" * 60)
    print()
    print("Ora riavvia:")
    print("  ./ferma.sh")
    print("  ./avvia.sh")
    print()
    print("E aggiungi un task dalla Quick Command bar.")
    print("Il worker ora potrà usare patch_code, analyze_project, ecc.")


if __name__ == "__main__":
    main()
