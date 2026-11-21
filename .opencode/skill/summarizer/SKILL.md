---
name: summarizer
description: Riassumi e condensa testi/report da fonti multilingue con modello LLM (eventualmente multilingue), riducendo il volume di input/output per report e risposte. Usa per la fase di sintesi dei report e per la riduzione di token prima di ulteriore elaborazione.
---

# Summarizer — riassunto e condensazione di testi

Flusso per: **testi/fonti multilingue → riassunto condensato → output strutturato**.

## 1. Scopo

- Condensare testi, report, articoli, chat, log in riassunti focalizzati.
- Gestire fonti **multilingue** (IT/EN, miste) con un modello LLM potenzialmente
  multilingue.
- Ridurre il volume di token in ingresso/uscita per i passi successivi
  (report, risposte, pianificazione).

## 2. Workflow

1. Raccogli fonti (URL, file, testo) → normalizza lingua.
2. Sintetizza: punti salienti, dati, opinioni, decisioni; fonti citate.
3. Condensazione: obiettivo → 3-7 punti; contesto → dettagli essenziali.
4. Output: riassunto in linguaggio di destinazione (IT/EN) + numeri/dati.
5. Passa al `markdown-formatter` per la formattazione del riassunto.

## 3. Quality gates

- Fonti verificate; date contestuali.
- Nessun dato inventato.
- Lunghezza dichiarata del riassunto.

## 4. Comandi chiave

```bash
# esempio di condensa (pseudo)
python - <<'PY'
# input: testi -> output: riassunto strutturato
PY
```
