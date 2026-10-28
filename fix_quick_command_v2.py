#!/usr/bin/env python3
"""
fix_quick_command_v2.py — Fix corretto: inserisce il metodo _on_quick_command
PRIMA di def _on_add_task, senza toccare altri return.

Usa un pattern più stretto per evitare il bug della v1.
"""
import shutil
from pathlib import Path

GUI_FILE = Path("gui.py")
BACKUP = Path("gui.py.bak.quickfix2")


# Metodo da inserire (con newline finale corretto)
QUICK_COMMAND_METHOD = '''    def _on_quick_command(self) -> None:
        """Quick command: parse multilingue -> add_task con metadata."""
        if not INTENT_ROUTER_AVAILABLE:
            QMessageBox.warning(self, "Modulo mancante",
                                "intent_bridge.py non caricato.\\\\n"
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


# Pattern ESATTO: def _on_add_task con eventuale docstring sulla riga dopo
# Usiamo stringa semplice per evitare problemi di regex
INSERT_BEFORE = "    def _on_add_task(self) -> None:"


def main():
    if not GUI_FILE.exists():
        print(f"❌ {GUI_FILE} non trovato")
        return 1

    content = GUI_FILE.read_text()

    # Verifica se il metodo esiste già
    if "def _on_quick_command(self)" in content:
        print("✓ Metodo _on_quick_command già presente")
        return 0

    # Verifica che il punto di inserimento esista
    occurrences = content.count(INSERT_BEFORE)
    if occurrences == 0:
        print(f"❌ Punto di inserimento non trovato: '{INSERT_BEFORE}'")
        print("   Verifica che _on_add_task esista in gui.py")
        return 1
    if occurrences > 1:
        print(f"⚠  Trovati {occurrences} punti di inserimento, userò il primo")

    # Backup
    shutil.copy2(GUI_FILE, BACKUP)
    print(f"✓ Backup: {BACKUP}")

    # Inserisci il metodo PRIMA di _on_add_task
    # Sostituisci solo la PRIMA occorrenza
    new_content = content.replace(
        INSERT_BEFORE,
        QUICK_COMMAND_METHOD + INSERT_BEFORE,
        1,  # solo la prima occorrenza!
    )

    # Verifica che la sostituzione abbia prodotto codice valido
    if new_content == content:
        print("❌ Sostituzione non riuscita")
        return 1

    # Sanity check: il metodo deve essere presente una sola volta
    method_count = new_content.count("def _on_quick_command(self)")
    if method_count != 1:
        print(f"❌ Numero metodi _on_quick_command errato: {method_count}")
        shutil.copy2(BACKUP, GUI_FILE)
        return 1

    # Sanity check: non devono esserci 'return def' su stessa riga
    if "return    def" in new_content or "return def _on_quick" in new_content:
        print("❌ ERRORE: 'return def' rilevato! Ripristino backup.")
        shutil.copy2(BACKUP, GUI_FILE)
        return 1

    GUI_FILE.write_text(new_content)
    print("✓ Metodo _on_quick_command aggiunto prima di _on_add_task")
    print("✓ Sanity check superato (no 'return def')")

    print("\nOra prova:")
    print("  python -c \"import gui; print('OK')\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
