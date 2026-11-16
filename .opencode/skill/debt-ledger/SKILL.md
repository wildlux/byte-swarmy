---
name: debt-ledger
description: Registro del debito tecnico di byte-swarmy (SQLite). Usa quando trovi un pezzo da rifattorizzare/ottimizzare, quando devi scegliere su cosa lavorare, o quando l'utente parla di refactoring, debito tecnico, ottimizzazioni da tracciare.
---

# Registro del debito tecnico (debt ledger)

SQLite in `state/debt_ledger.db`, gestito SOLO via `CORE/debt_ledger.py`
(API o CLI). **Mai SQL libero**: le query sono deterministiche, gratis,
zero calore — la pianificazione avviene a macchina fredda, l'esecuzione
in un item per sessione (regola stadiale, limite 60°C).

## Le 3 regole

1. **Registra trovando**: ogni volta che noti un pezzo da rifattorizzare
   o ottimizzare, un comando `add` (5 secondi). Il ledger vale più del
   ricordo.
2. **`file_hash` protegge dalla marcium**: il modulo calcola l'hash del
   file ALLA registrazione; se il file cambia, l'item va in `stale`
   automaticamente e non viene mai proposto alla cieca. Se un item è
   stale: riverifica la premessa e ri-registralo (il vecchio resta in
   storia).
3. **Il "next" viene da una query, non da un'idea**: prima di scegliere
   lavoro, chiedi al ledger. `prefer_kind` ripriorizza un tipo di lavoro
   senza violare le priorità.

## CLI (l'interfaccia ufficiale per l'LLM)

```bash
# registra (il file può anche non esistere ancora)
.venv/bin/python -m CORE.debt_ledger add \
    --kind refactor|optimization|test|docs \
    --file PERCORSO/relativo.py \
    --title "Cosa" --rationale "Perché" \
    --priority 1|2|3 --effort xs|s|m|l

# scegli su cosa lavorare (con check anti-stantio automatico)
.venv/bin/python -m CORE.debt_ledger next [--kind test]

# lista e stato
.venv/bin/python -m CORE.debt_ledger list [--status open]
.venv/bin/python -m CORE.debt_ledger stats

# avanzamento di un item
.venv/bin/python -m CORE.debt_ledger progress <id>   # inizio lavoro
.venv/bin/python -m CORE.debt_ledger done <id>       # fine (dopo verifica)

# contesto del file dal code_map (simboli esistenti, fail-open)
.venv/bin/python -m CORE.debt_ledger context PERCORSO/relativo.py
```

## Flusso di una sessione di rifattorizzazione (stadiale, 60°C)

1. `next` → prendi UN item.
2. `progress <id>` → inizio.
3. `context <file>` → simboli dal code_map: RIUSA le API esistenti
   invece di allucinarle.
4. Esegui lo stadio (generazione breve, verifica host-side:
   `py_compile` + test mirati, mai generazioni monolitiche).
5. Verifica verde → `done <id>`. Fallita → ri-registra l'item con la
   premessa corretta e lascia `in_progress` con nota nel rationale.

## Integrazione con il resto del progetto

- `CORE/code_map.py` (AST→SQLite): fonte del contesto simboli —
  il ledger NON duplica la mappa, la riusa.
- `todo.md`: resta il piano di progetto; il ledger è il pezzo-level
  (file/funzione) e si aggiorna da solo via CLI.
- `tools/verify_cycle.sh`: la verifica del punto 4 è lo stesso ciclo
  standard (py_compile → test → boot smoke).
