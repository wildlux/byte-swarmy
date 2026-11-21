---
name: markdown-formatter
description: Stile e scrittura pulita di Markdown per risposte, report e documenti (formattatore di risposte/report). Usa quando l'utente chiede di scrivere/testare markdown pulito, report in markdown, o risposte ben strutturate.
---

# Markdown Formatter — stile e scrittura pulita di Markdown

Unico flusso per scrivere risposte, report e documenti Markdown puliti.

## 1. Scopo

- Formattare risposte, report e documenti in Markdown di alta qualità.
- Standard per risposte dell'agente e deliverable dei report (vedi skill
  `research-report`).

## 2. Regole di scrittura pulita

- Un solo `#` per documento; gerarchia `# > ## > ### > ####` senza salti.
- Liste: coerenza di marcatori (`-`, `*` o `+`) per blocco, numerati per
  sequenza.
- Tabelle: intestazioni con separatori `|---|`; una riga di separatore minima.
- Code fence: linguaggio dichiarato (`python`, `bash`, `json`, `sql`).
- Link: inline `[test](url)` o reference; mai bare URL.
- Lunghezza riga < 100; no trailing whitespace; newline finale.
- Paragrafi brevi; no ripetizioni; heading descrittivi.

## 3. Workflow

1. Bozza → controlli stilistici → revisione → output.
2. Per report: mettere in ordine titolo → executive summary → sezioni → fonti.

## 4. Quality gates

- Markdown renderabile (fence bilanciati, tabelle con separatori).
- Leggibilità: una riga <= 100 caratteri dove possibile.
- Coerenza con la skill `research-report` per i deliverable report.

## 5. Comandi chiave

```bash
# controllo rapido di formattazione markdown (stdlib)
grep -rnE ' +$' --include="*.md" . | head
python - <<'PY'
import re, pathlib
bad = [p for p in pathlib.Path('.').rglob('*.md') if p.is_file() and p.stat().st_size > 0 and (p.read_text().endswith('\n') is False or '\t' in p.read_text())]
print(bad)
PY
```
