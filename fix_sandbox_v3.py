#!/usr/bin/env python3
"""
fix_sandbox_v3.py — Fix DEFINITIVO per sandbox escape.

Combina:
- --tmpfs /etc (crea /etc come mount point vuoto)
- --ro-bind file specifici (passwd, hosts, ecc.)
- --remount-ro /etc (rendo /etc read-only come directory)

Senza --tmpfs, /etc non è un mount point e --remount-ro fallisce.
"""
import re
import shutil
from pathlib import Path

SANDBOX_FILE = Path("sandbox.py")
BACKUP = Path("sandbox.py.bak3")


def main():
    if not SANDBOX_FILE.exists():
        print(f"❌ {SANDBOX_FILE} non trovato")
        return 1

    content = SANDBOX_FILE.read_text()
    original = content

    shutil.copy2(SANDBOX_FILE, BACKUP)
    print(f"✓ Backup creato: {BACKUP}")

    # 1. Ri-aggiungi --tmpfs /etc DOPO --tmpfs /opt (se non già presente)
    if '"--tmpfs", "/etc"' not in content:
        # Cerca la riga "--tmpfs", "/opt", e aggiungi /etc dopo
        pattern = r'(\s*)"--tmpfs",\s*"/opt",'
        match = re.search(pattern, content)
        if not match:
            print("❌ Non trovo '--tmpfs /opt' a cui aggiungere /etc")
            shutil.copy2(BACKUP, SANDBOX_FILE)
            return 1
        indent = match.group(1)
        insertion = (
            f'{match.group(0)}\n'
            f'{indent}# /etc come tmpfs vuoto: serve come mount point per --remount-ro.\n'
            f'{indent}# I file necessari sono ro-bindati sotto; --remount-ro finale\n'
            f'{indent}# rende la directory stessa read-only (no /etc/.sandbox-escape).\n'
            f'{indent}"--tmpfs", "/etc",'
        )
        content = content[:match.start()] + insertion + content[match.end():]
        print("✓ Riaggiunto --tmpfs /etc dopo --tmpfs /opt")
    else:
        print("ℹ  --tmpfs /etc già presente")

    # 2. Verifica che --remount-ro /etc e /opt siano ancora presenti (dalla v2)
    if '"--remount-ro", "/etc"' not in content:
        # Se mancano (es. file ripristinato), aggiungili prima del project_root bind
        insert_pattern = r'(\s*)"--bind",\s*str\(project_root\),\s*WORKSPACE,'
        match = re.search(insert_pattern, content)
        if match:
            indent = match.group(1)
            insertion = (
                f'{indent}"--remount-ro", "/etc",\n'
                f'{indent}"--remount-ro", "/opt",\n'
                f'{indent}"--bind", str(project_root), WORKSPACE,'
            )
            content = content[:match.start()] + insertion + content[match.end():]
            print("✓ Riaggiunto --remount-ro /etc e /opt (mancavano)")
        else:
            print("⚠  --remount-ro non trovato ma pattern project_root non matcha")
    else:
        print("ℹ  --remount-ro /etc e /opt già presenti (v2)")

    # 3. Salva se ci sono state modifiche
    if content != original:
        SANDBOX_FILE.write_text(content)
        print(f"\n✓ Fix v3 applicato a {SANDBOX_FILE}")
    else:
        print("\nℹ  Nessuna modifica necessaria")

    # 4. Verifica l'ordine: --tmpfs /etc deve venire PRIMA di --remount-ro /etc
    tmpfs_pos = content.find('"--tmpfs", "/etc"')
    remount_pos = content.find('"--remount-ro", "/etc"')
    if tmpfs_pos == -1:
        print("⚠  ATTENZIONE: --tmpfs /etc non trovato!")
        return 1
    if remount_pos == -1:
        print("⚠  ATTENZIONE: --remount-ro /etc non trovato!")
        return 1
    if tmpfs_pos > remount_pos:
        print("⚠  ATTENZIONE: --tmpfs /etc viene DOPO --remount-ro /etc (ordine sbagliato!)")
        return 1
    print(f"\n✓ Ordine corretto: tmpfs={tmpfs_pos} < remount-ro={remount_pos}")

    print("\n Ora testa con:")
    print("  python -m pytest tests/test_sandbox.py::TestSandboxSelfTest::test_all_isolation_checks_pass -v")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

