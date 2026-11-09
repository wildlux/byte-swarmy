"""
logbook.py — Gestione del diario di bordo per i test SML.

Ogni test viene registrato come file JSON in OLLAMA_SML_AGENT/logbook/.
Permette di tracciare iterazioni, confrontare versioni del prompt
e capire perché un modello fallisce o successo.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGBOOK_DIR = BASE_DIR / "OLLAMA_SML_AGENT" / "logbook"


def _ensure_dir() -> None:
    LOGBOOK_DIR.mkdir(parents=True, exist_ok=True)


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
    errore: Optional[str],
    note_miglioramento: Optional[str] = None,
) -> Path:
    """Salva un tentativo di test nel diario di bordo.

    Ritorna il path del file creato.
    """
    _ensure_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    modello_sicuro = modello.replace(":", "_").replace("/", "_")
    nome_file = f"test_{ts}_{modello_sicuro}_L{livello}.json"
    path = LOGBOOK_DIR / nome_file

    record = {
        "modello": modello,
        "quantizzazione": quantizzazione,
        "dimensione_gb": dimensione_gb,
        "prompt_versione": prompt_versione,
        "livello": livello,
        "prompt_inviato": prompt_inviato,
        "output_grezzo": output_grezzo,
        "output_parsato": output_parsato,
        "esito": esito,
        "punteggio": punteggio,
        "errore": errore,
        "timestamp": datetime.now().isoformat(),
        "note_miglioramento": note_miglioramento,
    }

    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def leggi_tutti() -> list:
    """Ritorna tutti i record del logbook ordinati per data."""
    _ensure_dir()
    record = []
    for f in sorted(LOGBOOK_DIR.glob("test_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            record.append(data)
        except Exception:
            continue
    return record


def riepilogo_per_modello(modello: str) -> dict:
    """Ritorna statistiche per un modello specifico."""
    tutti = leggi_tutti()
    filtratati = [r for r in tutti if r["modello"] == modello]
    if not filtratati:
        return {"modello": modello, "totale": 0, "promossi": 0, "bocciati": 0}

    promossi = sum(1 for r in filtratati if r["esito"] == "promosso")
    bocciati = sum(1 for r in filtratati if r["esito"] == "bocciato")
    errori = sum(1 for r in filtratati if r["esito"] == "errore")
    return {
        "modello": modello,
        "totale": len(filtratati),
        "promossi": promossi,
        "bocciati": bocciati,
        "errori": errori,
        "tasso_successo": round(promossi / len(filtratati), 2) if filtratati else 0,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        modello = sys.argv[1]
        r = riepilogo_per_modello(modello)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        tutti = leggi_tutti()
        print(f"Tentativi totali: {len(tutti)}")
        for r in tutti[:5]:
            print(f"  {r['timestamp']} | {r['modello']} | L{r['livello']} | {r['esito']}")
