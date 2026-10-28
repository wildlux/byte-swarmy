#!/usr/bin/env python3
"""
fix_sandbox_v2.py — Fix CORRETTO per sandbox escape.

La fix v1 (--tmpfs /etc) era insufficiente: un tmpfs è scrivibile.
Questa fix usa --remount-ro /etc e --remount-ro /opt DOPO i bind selettivi,
rendendo le directory stesse read-only (non solo i file bindati).
"""
import re
import shutil
from pathlib import Path

SANDBOX_FILE = Path("sandbox.py")
BACKUP = Path("sandbox.py.bak2")


def main():
    if not SANDBOX_FILE.exists():
        print(f"❌ {SANDBOX_FILE} non trovato")
        return 1

    content = SANDBOX_FILE.read_text()
    original = content

    shutil.copy2(SANDBOX_FILE, BACKUP)
    print(f"✓ Backup creato: {BACKUP}")

    # 1. Rimuovi --tmpfs /etc se presente (dalla fix v1, non sufficiente)
    old_block = '''        # /etc come tmpfs vuoto: i singoli file necessari sono ro-bindati sotto.
        # Cosi qualsiasi file non esplicitamente montato (es. /etc/.sandbox-escape)
        # NON ESISTE nel sandbox, invece di esistere come file scrivibile.
        "--tmpfs", "/etc",
'''
    if old_block in content:
        content = content.replace(old_block, '')
        print("✓ Rimossa fix v1 insufficiente (--tmpfs /etc)")

    # 2. Verifica se --remount-ro è già presente
    if '"--remount-ro", "/etc"' in content:
        print("ℹ  --remount-ro /etc già presente, nessuna modifica necessaria")
        if content != original:
            SANDBOX_FILE.write_text(content)
        return 0

    # 3. Trova il punto di inserimento: prima del project_root bind
    # Pattern flessibile con regex per gestire variazioni di whitespace
    insert_pattern = r'(\s*)"--bind",\s*str\(project_root\),\s*WORKSPACE,'
    match = re.search(insert_pattern, content)

    if not match:
        print("❌ Pattern project_root bind non trovato.")
        print("  Cerca manualmente la riga con:")
        print('    "--bind", str(project_root), WORKSPACE,')
        print("  e aggiungi PRIMA di essa:")
        print('    "--remount-ro", "/etc",')
        print('    "--remount-ro", "/opt",')
        shutil.copy2(BACKUP, SANDBOX_FILE)
        return 1

    indent = match.group(1)
    insertion = (
        f'{indent}# 🛡️ FIX v2: /etc e /opt read-only come directory '
        f'(non solo i file bindati).\n'
        f'{indent}# Previene la creazione di file arbitrari '
        f'(es. /etc/.sandbox-escape, /opt/.sandbox-escape).\n'
        f'{indent}"--remount-ro", "/etc",\n'
        f'{indent}"--remount-ro", "/opt",\n'
        f'{indent}"--bind", str(project_root), WORKSPACE,'
    )

    content = content[:match.start()] + insertion + content[match.end():]
    print("✓ Aggiunto --remount-ro /etc e --remount-ro /opt prima del bind project_root")

    if content != original:
        SANDBOX_FILE.write_text(content)
        print(f"\n✓ Fix v2 applicato a {SANDBOX_FILE}")
        print("\n Ora testa con:")
        print("  python -m pytest tests/test_sandbox.py::TestSandboxSelfTest::test_all_isolation_checks_pass -v")
    else:
        print("\nℹ  Nessuna modifica necessaria")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
