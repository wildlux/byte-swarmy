"""
sml_database.py — Database SQLite per catalogare modelli SML e i loro risultati di test.

Tabelle:
- modelli: anagrafica del modello (nome, quantizzazione, dimensione, fonte)
- parametri: parametri di inferenza usati per ogni test
- risultati_test: esito di ogni test atomico (livello 1, 2, 3)
- benchmark_complessivo: sintesi per modello (quali livelli superati, promosso sì/no)

Tutto in stdlib (sqlite3, json), nessun dipendenza esterna.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "OLLAMA_SML_AGENT" / "sml_models.db"
RESULTS_DIR = BASE_DIR / "OLLAMA_SML_AGENT" / "results"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea le tabelle se non esistono."""
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS modelli (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                quantizzazione TEXT,
                dimensione_gb REAL,
                fonte TEXT DEFAULT 'ollama',
                data_aggiunta TEXT NOT NULL,
                note TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS parametri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modello_id INTEGER NOT NULL,
                temperatura REAL,
                num_predict INTEGER,
                num_ctx INTEGER,
                repeat_penalty REAL,
                seed INTEGER,
                data_test TEXT NOT NULL,
                FOREIGN KEY (modello_id) REFERENCES modelli(id)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS risultati_test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modello_id INTEGER NOT NULL,
                livello INTEGER NOT NULL,
                test_nome TEXT NOT NULL,
                esito TEXT NOT NULL,           -- 'promosso' / 'bocciato' / 'errore'
                punteggio REAL DEFAULT 0.0,
                output_grezzo TEXT,
                output_parsato TEXT,           -- JSON parsato se valido
                errore TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (modello_id) REFERENCES modelli(id)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS benchmark_complessivo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modello_id INTEGER NOT NULL,
                livello_1_ok INTEGER DEFAULT 0,
                livello_2_ok INTEGER DEFAULT 0,
                livello_3_ok INTEGER DEFAULT 0,
                promosso INTEGER DEFAULT 0,
                data_benchmark TEXT NOT NULL,
                FOREIGN KEY (modello_id) REFERENCES modelli(id)
            )
            """
        )
        c.commit()


def aggiungi_modello(
    nome: str,
    quantizzazione: Optional[str] = None,
    dimensione_gb: Optional[float] = None,
    fonte: str = "ollama",
    note: Optional[str] = None,
) -> int:
    """Inserisce un modello e ritorna il suo ID."""
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO modelli (nome, quantizzazione, dimensione_gb, fonte, data_aggiunta, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome, quantizzazione, dimensione_gb, fonte, datetime.now().isoformat(), note),
        )
        return int(cur.lastrowid)


def get_modello_id(nome: str) -> Optional[int]:
    with _conn() as c:
        row = c.execute("SELECT id FROM modelli WHERE nome = ?", (nome,)).fetchone()
        return int(row["id"]) if row else None


def salva_parametri(
    modello_id: int,
    temperatura: float,
    num_predict: int,
    num_ctx: int,
    repeat_penalty: float,
    seed: int,
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO parametri (modello_id, temperatura, num_predict, num_ctx,
                                   repeat_penalty, seed, data_test)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                modello_id,
                temperatura,
                num_predict,
                num_ctx,
                repeat_penalty,
                seed,
                datetime.now().isoformat(),
            ),
        )


def salva_risultato(
    modello_id: int,
    livello: int,
    test_nome: str,
    esito: str,
    punteggio: float = 0.0,
    output_grezzo: Optional[str] = None,
    output_parsato: Optional[dict] = None,
    errore: Optional[str] = None,
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO risultati_test
                (modello_id, livello, test_nome, esito, punteggio,
                 output_grezzo, output_parsato, errore, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                modello_id,
                livello,
                test_nome,
                esito,
                punteggio,
                output_grezzo,
                json.dumps(output_parsato, ensure_ascii=False)
                if output_parsato is not None
                else None,
                errore,
                datetime.now().isoformat(),
            ),
        )


def salva_benchmark(
    modello_id: int,
    l1: bool,
    l2: bool,
    l3: bool,
    promosso: bool,
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO benchmark_complessivo
                (modello_id, livello_1_ok, livello_2_ok, livello_3_ok,
                 promosso, data_benchmark)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                modello_id,
                1 if l1 else 0,
                1 if l2 else 0,
                1 if l3 else 0,
                1 if promosso else 0,
                datetime.now().isoformat(),
            ),
        )


def elenco_modelli() -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, nome, quantizzazione, dimensione_gb, data_aggiunta FROM modelli ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def risultati_modello(modello_id: int) -> list:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT livello, test_nome, esito, punteggio, timestamp
            FROM risultati_test WHERE modello_id = ? ORDER BY id
            """,
            (modello_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def ultimo_benchmark(modello_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            """
            SELECT livello_1_ok, livello_2_ok, livello_3_ok, promosso, data_benchmark
            FROM benchmark_complessivo
            WHERE modello_id = ? ORDER BY id DESC LIMIT 1
            """,
            (modello_id,),
        ).fetchone()
        return dict(row) if row else None


if __name__ == "__main__":
    import sys

    init_db()
    if len(sys.argv) > 1 and sys.argv[1] == "--aggiungi":
        nome = sys.argv[2]
        quant = sys.argv[3] if len(sys.argv) > 3 else None
        dim = float(sys.argv[4]) if len(sys.argv) > 4 else None
        mid = aggiungi_modello(nome, quant, dim)
        print(f"Modello '{nome}' aggiunto con ID {mid}")
    elif len(sys.argv) > 1 and sys.argv[1] == "--elenco":
        for m in elenco_modelli():
            print(m)
    else:
        print("Database inizializzato:", DB_PATH)
        print("Uso: python sml_database.py --aggiungi <nome> [quant] [dim_gb]")
        print("     python sml_database.py --elenco")
