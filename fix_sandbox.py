#!/usr/bin/env python3
"""
fix_sandbox.py — Fix per bug sandbox: /etc non era tmpfs, permetteva escape.

Aggiunge --tmpfs /etc nei mount args PRIMA dei bind selettivi, così
qualsiasi file non esplicitamente montato NON esiste nel sandbox.

Anche fix per /opt: era tmpfs ma i bind successivi lo rendevano scrivibile.
Con --tmpfs /opt + --ro-bind /opt/venv + --ro-bind /opt/byte-swarmy,
/opt/.sandbox-escape non può esistere.
"""
import shutil
from pathlib import Path

SANDBOX_FILE = Path("sandbox.py")
BACKUP = Path("sandbox.py.bak")

# Pattern da cercare (sezione "Scrivibili ma volatili" in _mount_args)
OLD = '''        # Scrivibili ma volatili: niente persistenza fuori dal progetto.
        "--tmpfs", "/tmp",
        "--tmpfs", "/home",
        "--tmpfs", "/run",
        "--dir", SANDBOX_HOME,
        # /opt contiene solo bind read-only (venv, helper): tmpfs temporaneo
        # rimontato read-only subito dopo i bind.
        "--tmpfs", "/opt",
    ]'''

NEW = '''        # Scrivibili ma volatili: niente persistenza fuori dal progetto.
        "--tmpfs", "/tmp",
        "--tmpfs", "/home",
        "--tmpfs", "/run",
        "--dir", SANDBOX_HOME,
        # /opt contiene solo bind read-only (venv, helper): tmpfs temporaneo
        # rimontato read-only subito dopo i bind.
        "--tmpfs", "/opt",
        # /etc come tmpfs vuoto: i singoli file necessari sono ro-bindati sotto.
        # Cosi qualsiasi file non esplicitamente montato (es. /etc/.sandbox-escape)
        # NON ESISTE nel sandbox, invece di esistere come file scrivibile.
        "--tmpfs", "/etc",
    ]'''


def main():
    if not SANDBOX_FILE.exists():
        print(f"❌ {SANDBOX_FILE} non trovato")
        return 1

    content = SANDBOX_FILE.read_text()

    if '"--tmpfs", "/etc"' in content:
        print("✓ Fix già applicato (--tmpfs /etc presente)")
        return 0

    if OLD not in content:
        print("❌ Pattern non trovato. Il file è stato modificato rispetto all'atteso.")
        print("   Cerca manualmente la sezione '--tmpfs /opt' in sandbox.py")
        print("   e aggiungi '--tmpfs /etc' subito dopo.")
        return 1

    # Backup
    shutil.copy2(SANDBOX_FILE, BACKUP)
    print(f"✓ Backup creato: {BACKUP}")

    # Applica fix
    content = content.replace(OLD, NEW, 1)
    SANDBOX_FILE.write_text(content)
    print("✓ Fix applicato: aggiunto --tmpfs /etc in _mount_args")
    print("  Ora /etc è un tmpfs vuoto; solo i file ro-bindati esistono.")
    print("  /etc/.sandbox-escape NON esisterà più nel sandbox.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
