---
name: py-gui-scaffold
description: Skill per creare interfacce PyQt6 partendo da template curati (finestra, layout, segnali, QThread) con gate offscreen. Usa quando l'utente chiede di creare una finestra, un widget, un layout, collegare segnali Qt o aggiungere un worker in thread.
---

# Scaffolding GUI PyQt6 — template, non invenzione

Il modello 3b non è affidabile quando deve **creare** codice Qt da zero
(4/4 fallimenti nel Cycle 72). La policy è: riempire un template curato,
non generare la struttura.

## 1. Scegli il template

| File in `GUI/refs/templates/` | Quando usarlo |
|---|---|
| `finestra.py.tpl` | finestra minima, QMainWindow, central widget |
| `layout.py.tpl` | form + pulsanti, layout annidati |
| `segnali.py.tpl` | QLineEdit → pyqtSignal → QLabel |
| `thread.py.tpl` | QThread + Worker(QObject) con `quit` sul segnale di fine |

## 2. Compila e verifica le API

1. Copia il template: i valori da sostituire sono marcati `# SLOT:`.
2. Non scrivere simboli Qt a memoria: `api_lookup('PyQt6.QtWidgets',
   simbolo)` (senza `strict`: le classi C++ di Qt non hanno firma
   introspettabile e `strict=True` le bloccherebbe tutte). Un output che
   **non** inizia con `ERROR` conferma che il simbolo esiste; incrociare
   sempre con `GUI/refs/pyqt6.md`. `strict=True` resta obbligatorio per le
   librerie Python con firme introspettabili (gate E2).
3. `compile()` del file e `tools/lint_style.py`: zero errori e zero
   warning nuovi.

## 3. Gate offscreen (obbligatorio prima di dire "fatto")

- `QT_QPA_PLATFORM=offscreen pytest tests/test_gui_templates.py -q`
- snapshot della struttura (classi/testi) e prova dei segnali; il semplice
  click di un pulsante non basta: verificare il risultato osservabile.
- Il thread deve fermarsi (`thread.isRunning() == False`) e passare il
  risultato solo via segnale: mai toccare widget dal worker. Collegare
  `done → thread.quit` con `Qt.ConnectionType.DirectConnection`, altrimenti
  `quit` resta in coda al main loop e `wait()` non termina (Qt abort).

## 4. Limiti

- I template sono punti di partenza, non applicazioni complete.
- Nessun `app.exec()` nei test: la finestra si costruisce, non si mostra.
- Il collaudo con LLM live resta 🔒 bloccato finché le ventole non sono
  verificate (≤60 °C). Qui si verifica solo la struttura dello scaffold.
