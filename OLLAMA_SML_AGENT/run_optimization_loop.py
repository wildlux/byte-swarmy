"""
run_optimization_loop.py — Entry point principale per l'ottimizzazione SML.

Esegue il loop completo di ottimizzazione su tutti i modelli SML disponibili.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from OLLAMA_SML_AGENT.config import BASE_DIR, DEFAULT_SML_MODELS
from OLLAMA_SML_AGENT.model_discovery import (
    scopri_modelli_ollama,
    filtra_modelli_piccoli,
)
from OLLAMA_SML_AGENT.sml_database import init_db
from OLLAMA_SML_AGENT.sml_tester_senior import esegui_tutti_i_test_senior


def main():
    init_db()

    print("Scoperta modelli Ollama disponibili...")
    modelli_trovati = scopri_modelli_ollama()
    modelli_piccoli = filtra_modelli_piccoli(modelli_trovati, max_parametri="7B")

    if not modelli_piccoli:
        print("Nessun modello piccolo trovato. Uso modelli di default.")
        modelli_test = DEFAULT_SML_MODELS
    else:
        modelli_test = [m["nome"] for m in modelli_piccoli]

    print(f"\nModelli da testare: {modelli_test}")

    task_esempio = (
        'Crea una funzione Python che legga un file di testo dentro project/ '
        'e restituisca le righe non vuote. Include type hints, docstring e '
        'gestione errore per file inesistente.'
    )

    risultati_totali = {}

    for modello in modelli_test:
        print(f"\n{'='*60}")
        print(f"Modello: {modello}")
        print(f"{'='*60}")
        try:
            res = esegui_tutti_i_test_senior(modello)
            risultati_totali[modello] = res
            promosso = res.get("promosso", False)
            livello = res.get("livello_raggiunto", "N/A")
            print(f"Esito: {'PROMOSSO' if promosso else 'NON PROMOSSO'}")
            print(f"Livello raggiunto: {livello}")
        except Exception as e:
            print(f"Errore critico: {e}")
            risultati_totali[modello] = {"esito": "errore", "errore": str(e)}

    import datetime as _dt
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(BASE_DIR) / "OLLAMA_SML_AGENT" / "results" / f"evolution_report_{ts}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(risultati_totali, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nReport salvato: {report_path}")

    print("\n" + "=" * 60)
    print("RIEPILOGO FINALE")
    print("=" * 60)
    for modello, res in risultati_totali.items():
        promosso = res.get("promosso", False)
        livello = res.get("livello_raggiunto", "N/A")
        print(f"  {modello}: {'PROMOSSO' if promosso else 'NON PROMOSSO'} (Livello: {livello})")


if __name__ == "__main__":
    main()
