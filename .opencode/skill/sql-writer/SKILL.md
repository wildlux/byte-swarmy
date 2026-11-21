---
name: sql-writer
description: Skill per leggere e scrivere in SQL (MySQL, PostgreSQL, NOSQL, SQLite, engine generico) con query parametrizzate e gestione connessioni sicure. Usa quando serve scrivere/eseguire query SQL o nosql in un motore di database.
---

# SQL Writer — lettura/scrittura in SQL (qualsiasi motore)

Flusso: **connessione → schema → query (parametrizzata) → esecuzione → validazione**.

## 1. Scopo
- Leggere ed eseguire query SELECT in qualsiasi motore SQL (MySQL, PostgreSQL,
  SQLite, engine generico).
- Scrivere/edificare query INSERT/UPDATE/DELETE (o nosql equivalente) con
  **query parametrizzate** (mai string concat).

## 2. Workflow
1. Identificare motore (dialetto: mysql / postgres / sqlite / nosql).
2. Leggere schema (information_schema / equivalente).
3. Scrivere query parametrizzata (driver: psycopg2/sqlite3/pymysql/driver nosql).
4. Eseguire e validare; rollback su errore.

## 3. Quality gates
- Query parametrizzate: zero interpolazione di stringhe in SQL.
- Solo engine dichiarato: niente dialect switching silenzioso.
- Transazioni con rollback.

## 4. Comandi chiave
```bash
# es. PostgreSQL
psql "postgresql://user@host/db" -c "SELECT 1"
python - <<'PY'
import psycopg2
conn = psycopg2.connect("postgresql://...")
cur = conn.cursor(); cur.execute("SELECT %s", (1,)); cur.fetchall()
PY
```
