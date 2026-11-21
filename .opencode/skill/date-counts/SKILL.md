---
name: date-counts
description: Skill per conteggi e calcoli tra date (differenza giorni, somma/sottrazione date, fasce temporali). Usa per conteggi tra date, scadenze, intervalli.
---

# Date Counts — skill per conteggi tra date

Flusso: **input date → calcolo → verifica**.

## 1. Scopo

- Contare giorni (e giorni lavorativi) tra due date.
- Sommare/sottrarre date (es. +7 giorni).

## 2. Workflow

1. Normalizzare le date in ISO (YYYY-MM-DD).
2. Calcolare la differenza in giorni: `(b - a).days`.
3. Verificare intervalli ammessi.

## 3. Quality gates

- Date sempre in ISO.
- Conteggi come intero.

## 4. Comandi chiave

```bash
python - <<'PY'
from datetime import date
a = date(2026, 11, 1)
b = date(2026, 11, 21)
print((b - a).days)  # 20
PY
```
