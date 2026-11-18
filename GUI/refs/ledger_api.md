# Modulo: CORE.debt_ledger
# Debt Ledger API — cheat sheet (byte-swarmy)

Modulo: CORE.debt_ledger. Registro del debito tecnico (SQLite) — il
worker lo usa per tracciare pezzi da rifattorizzare.

## Costanti
- `ROOT` — root del progetto
- `DB_NAME` — nome del file SQLite
- `KINDS`, `EFFORTS`, `STATUSES` — enumerazioni ammesse

## Funzioni (tutte operano su `state/debt_ledger.db` o path dato)
- `init(db_path=None)` → crea schema
- `add(item)` → registra un item (kind, effort, status, ...)
- `get(item_id)` → dict | None
- `list_items(status=None, kind=None)` → list[dict]
- `next()` → prossimo item da lavorare (priorità)
- `mark(item_id, status)` → aggiorna stato
- `stats()` → {total, open, in_progress, done, ...}
- `context_for_file(path)` → lista item che toccano quel file
- `main()` → entry point CLI

## Regola d'oro
Un item per sessione. Mai generazioni monolitiche. Usare `debt-ledger`
skill per next/progress/context/stadio/done.
