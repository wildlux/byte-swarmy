"""
CORE/sml_database.py — Database SQLite per i modelli SML.

Tabelle:
- modelli: anagrafica modelli testati
- risultati_test: risultati di ogni test eseguito
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "state" / "sml_database.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
                ts_inserimento TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS risultati_test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modello_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                categoria TEXT,
                difficolta INTEGER,
                passato INTEGER NOT NULL,
                punteggio REAL NOT NULL,
                latenza REAL NOT NULL,
                output TEXT,
                errore TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (modello_id) REFERENCES modelli(id)
            )
            """
        )
        c.commit()


def aggiungi_modello(nome: str, quantizzazione: str = "", dimensione_gb: float = 0.0) -> int:
    """Aggiunge un modello e restituisce il suo ID."""
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO modelli (nome, quantizzazione, dimensione_gb, ts_inserimento) "
            "VALUES (?, ?, ?, ?)",
            (nome, quantizzazione, dimensione_gb, datetime.now().isoformat()),
        )
        if cur.lastrowid:
            return cur.lastrowid
        # Se già esiste, restituisci l'ID esistente
        row = c.execute("SELECT id FROM modelli WHERE nome = ?", (nome,)).fetchone()
        return row[0] if row else -1


def get_modello_id(nome: str) -> Optional[int]:
    """Ritorna l'ID di un modello esistente, oppure None."""
    with _conn() as c:
        row = c.execute("SELECT id FROM modelli WHERE nome = ?", (nome,)).fetchone()
        return row[0] if row else None


def salva_parametri(modello_id: int, **kwargs) -> None:
    """Placeholder per salvare parametri di test (estendibile)."""
    pass


def salva_risultato(
    modello_id: int,
    task_id: str,
    categoria: str,
    difficolta: int,
    passato: bool,
    punteggio: float,
    output: str = "",
    errore: str = "",
    db_path: Optional[Path] = None,
) -> None:
    """Salva il risultato di un singolo test."""
    with _conn() as c:
        c.execute(
            """
            INSERT INTO risultati_test (
                modello_id, task_id, categoria, difficolta,
                passato, punteggio, latenza_secondi, output_grezzo, errore, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                modello_id,
                task_id,
                categoria,
                difficolta,
                1 if passato else 0,
                punteggio,
                0.0,  # latenza sarà aggiornata dal chiamante se necessario
                output[:2000] if output else "",
                errore or "",
                datetime.now().isoformat(),
            ),
        )


def salva_benchmark(
    modello_id: int,
    l1: bool = False,
    l2: bool = False,
    l3: bool = False,
    promosso: bool = False,
) -> None:
    """Placeholder per salvataggio benchmark (estendibile)."""
    pass


def salva_tentativo(
    modello: str,
    quantizzazione: str,
    dimensione_gb: float,
    prompt_versione: str,
    livello: int,
    prompt_inviato: str,
    output_grezzo: str,
    output_parsato: Optional[dict],
    esito: str,
    punteggio: float,
    errore: Optional[str] = None,
    note_miglioramento: Optional[str] = None,
) -> None:
    """Alias compatto per salva_risultato (interfaccia usata da sml_tester_senior)."""
    salva_risultato(
        modello_id=get_modello_id(modello) or aggiungi_modello(modello, quantizzazione, dimensione_gb),
        task_id=f"livello_{livello}",
        categoria=prompt_versione,
        difficolta=livello,
        passato=(esito == "promosso"),
        punteggio=punteggio,
        output=output_grezzo or "",
        errore=errore or "",
    )


def leggi_tutti() -> list[dict]:
    """Ritorna tutti i modelli registrati."""
    with _conn() as c:
        rows = c.execute("SELECT * FROM modelli ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def riepilogo_per_modello(modello: str) -> dict:
    """Ritorna statistiche per un modello."""
    with _conn() as c:
        modello_id = get_modello_id(modello)
        if not modello_id:
            return {"modello": modello, "totale": 0, "promossi": 0, "bocciati": 0}
        tot = c.execute(
            "SELECT COUNT(*) FROM risultati_test WHERE modello_id = ?", (modello_id,)
        ).fetchone()[0]
        promossi = c.execute(
            "SELECT COUNT(*) FROM risultati_test WHERE modello_id = ? AND passato = 1",
            (modello_id,),
        ).fetchone()[0]
        bocciati = tot - promossi
        return {
            "modello": modello,
            "totale": tot,
            "promossi": promossi,
            "bocciati": bocciati,
        }


__all__ = [
    "init_db",
    "aggiungi_modello",
    "get_modello_id",
    "salva_parametri",
    "salva_risultato",
    "salva_benchmark",
    "salva_tentativo",
    "leggi_tutti",
    "riepilogo_per_modello",
]
