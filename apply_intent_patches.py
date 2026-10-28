#!/usr/bin/env python3
"""
apply_intent_patches.py — Applica le 3 patch a gui.py per integrare
il IntentRouter (Quick Command bar multilingue).

Sicuro: fa backup automatico di gui.py prima di modificare.
Se qualcosa va storto, ripristina il backup.
"""
import shutil
import sys
from pathlib import Path

GUI_FILE = Path("gui.py")
BACKUP_FILE = Path("gui.py.bak")

# === PATCH 1: import in cima (dopo MCP_AVAILABLE = False) ===
PATCH1_SEARCH = """    MCP_AVAILABLE = False"""
PATCH1_ADD = """    MCP_AVAILABLE = False


# ------------------------------------------------------------------
# Intent Router integration (multilingual IT/EN/ZH)
# ------------------------------------------------------------------
try:
    from intent_bridge import add_task_with_intent, parse_input, localize
    INTENT_ROUTER_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: intent_bridge non disponibile: {e}")
    INTENT_ROUTER_AVAILABLE = False"""

# === PATCH 2: Quick Command bar in TaskQueueTab._build_ui ===
PATCH2_SEARCH = """    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
 
        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Aggiungi Task")"""
PATCH2_REPLACE = """    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 🆕 Quick Command Bar (multilingue IT/EN/ZH via IntentRouter)
        if INTENT_ROUTER_AVAILABLE:
            quick_group = QGroupBox("⚡ Comando Rapido (IT/EN/ZH)")
            quick_layout = QHBoxLayout(quick_group)
            self.quick_input = QLineEdit()
            self.quick_input.setPlaceholderText(
                "Scrivi in qualsiasi lingua: 'crea funzione X', "
                "'optimize Y', '用python写一个函数', 'swarm status'..."
            )
            self.quick_input.returnPressed.connect(self._on_quick_command)
            btn_quick = QPushButton("🐝 Aggiungi")
            btn_quick.clicked.connect(self._on_quick_command)
            quick_layout.addWidget(self.quick_input, stretch=1)
            quick_layout.addWidget(btn_quick)
            self.quick_status = QLabel("")
            self.quick_status.setStyleSheet("color: #666; padding: 2px;")
            quick_layout.addWidget(self.quick_status, stretch=1)
            layout.addWidget(quick_group)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Aggiungi Task")"""

# === PATCH 3: metodo _on_quick_command prima di _on_add_task ===
PATCH3_SEARCH = """    def _on_add_task(self) -> None:
        dialog = AddTaskDialog(self)"""
PATCH3_ADD = """    def _on_quick_command(self) -> None:
        \"\"\"Quick command: parse multilingue -> add_task con metadata.\"\"\"
        if not INTENT_ROUTER_AVAILABLE:
            QMessageBox.warning(self, "Modulo mancante",
                                "intent_bridge.py non caricato.\\n"
                                "Verifica che intent_router.py, intent_bridge.py "
                                "e intents.json siano nella cartella del progetto.")
            return

        raw = self.quick_input.text().strip()
        if not raw:
            return

        try:
            result = add_task_with_intent(raw, add_task)

            # Feedback localizzato
            if result["is_swarm_command"]:
                msg = localize("swarm_command", result["lang"],
                               intent=result["intent"])
                color = "#9966cc"
            elif result["fallback"]:
                msg = localize("fallback", result["lang"])
                color = "#cc6600"
            else:
                msg = localize("task_added", result["lang"],
                               intent=result["intent"],
                               conf=result["confidence"])
                color = "#008800"

            self.quick_status.setText(msg)
            self.quick_status.setStyleSheet(
                f"color: {color}; padding: 2px; font-weight: bold;"
            )
            self.quick_input.clear()
            self._refresh()
        except Exception as e:
            self.quick_status.setText(f"❌ Errore: {e}")
            self.quick_status.setStyleSheet("color: #cc0000; padding: 2px;")

    def _on_add_task(self) -> None:
        dialog = AddTaskDialog(self)"""


def main():
    if not GUI_FILE.exists():
        print(f"❌ {GUI_FILE} non trovato. Esegui dalla cartella byte-swarmy.")
        sys.exit(1)

    # 1. Backup
    shutil.copy2(GUI_FILE, BACKUP_FILE)
    print(f"✓ Backup creato: {BACKUP_FILE}")

    content = GUI_FILE.read_text()
    original_content = content
    applied = []

    # 2. Applica PATCH 1
    if "INTENT_ROUTER_AVAILABLE" in content:
        print("ℹ️  PATCH 1 già applicata (INTENT_ROUTER_AVAILABLE trovato), skip")
    elif PATCH1_SEARCH in content:
        content = content.replace(PATCH1_SEARCH, PATCH1_ADD, 1)
        applied.append("PATCH 1: import intent_bridge")
    else:
        print("❌ PATCH 1: pattern non trovato. Ripristino backup.")
        shutil.copy2(BACKUP_FILE, GUI_FILE)
        sys.exit(1)

    # 3. Applica PATCH 2
    if "Quick Command Bar" in content or "quick_input" in content:
        print("ℹ️  PATCH 2 già applicata (quick_input trovato), skip")
    elif PATCH2_SEARCH in content:
        content = content.replace(PATCH2_SEARCH, PATCH2_REPLACE, 1)
        applied.append("PATCH 2: Quick Command bar in TaskQueueTab")
    else:
        print("❌ PATCH 2: pattern non trovato. Ripristino backup.")
        shutil.copy2(BACKUP_FILE, GUI_FILE)
        sys.exit(1)

    # 4. Applica PATCH 3
    if "_on_quick_command" in content:
        print("ℹ️  PATCH 3 già applicata (_on_quick_command trovato), skip")
    elif PATCH3_SEARCH in content:
        content = content.replace(PATCH3_SEARCH, PATCH3_ADD, 1)
        applied.append("PATCH 3: metodo _on_quick_command")
    else:
        print("❌ PATCH 3: pattern non trovato. Ripristino backup.")
        shutil.copy2(BACKUP_FILE, GUI_FILE)
        sys.exit(1)

    # 5. Salva solo se ci sono state modifiche
    if content != original_content:
        GUI_FILE.write_text(content)
        print(f"\n✓ {len(applied)} patch applicate a {GUI_FILE}:")
        for p in applied:
            print(f"   - {p}")
    else:
        print("\nℹ️  Nessuna modifica necessaria (tutte le patch già presenti)")

    print(f"\nBackup originale: {BACKUP_FILE}")
    print("Se qualcosa non funziona, ripristina con:")
    print(f"  cp {BACKUP_FILE} {GUI_FILE}")


if __name__ == "__main__":
    main()
