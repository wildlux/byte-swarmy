#!/usr/bin/env python3
"""
fix_quick_command.py — Aggiunge il metodo _on_quick_command mancante
a TaskQueueTab in gui.py.

Viene inserito PRIMA di _on_add_task.
"""
import re
import shutil
from pathlib import Path

GUI_FILE = Path("gui.py")
BACKUP = Path("gui.py.bak.quickfix")


QUICK_COMMAND_METHOD = '''    def _on_quick_command(self) -> None:
        """Quick command: parse multilingue -> add_task con metadata."""
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

'''


def main():
    if not GUI_FILE.exists():
        print(f"❌ {GUI_FILE} non trovato")
        return 1

    content = GUI_FILE.read_text()

    # Verifica se il metodo esiste già
    if "def _on_quick_command(self)" in content:
        print("✓ Metodo _on_quick_command già presente")
        return 0

    # Backup
    shutil.copy2(GUI_FILE, BACKUP)
    print(f"✓ Backup: {BACKUP}")

    # Cerca il punto di inserimento: prima di _on_add_task
    # Pattern flessibile con regex
    pattern = r'(\s+)(def _on_add_task\(self\) -> None:)'

    match = re.search(pattern, content)
    if not match:
        print("❌ Punto di inserimento (def _on_add_task) non trovato")
        print("   Cerca manualmente 'def _on_add_task' e aggiungi prima:")
        print("   def _on_quick_command(self) -> None: ...")
        return 1

    # Inserisci il metodo con la stessa indentazione di _on_add_task
    indent = match.group(1)
    insertion = QUICK_COMMAND_METHOD.rstrip() + "\n\n" + indent + match.group(2)

    content = content[:match.start()] + insertion + content[match.end():]

    GUI_FILE.write_text(content)
    print("✓ Metodo _on_quick_command aggiunto prima di _on_add_task")

    # Verifica
    new_content = GUI_FILE.read_text()
    if "def _on_quick_command" in new_content:
        print("\n✓ Verifica OK: metodo presente")
    else:
        print("\n❌ Verifica FALLITA: il metodo non è stato aggiunto")
        shutil.copy2(BACKUP, GUI_FILE)
        return 1

    print("\nOra prova:")
    print("  python -c \"import gui; print('OK')\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
