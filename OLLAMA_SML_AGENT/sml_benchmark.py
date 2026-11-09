"""
sml_benchmark.py — Confronta più modelli SML e genera un report di benchmark.

Legge i modelli registrati in sml_models.db, esegue i test su ciascuno
e produce un report comparativo in OLLAMA_SML_AGENT/results/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from OLLAMA_SML_AGENT.sml_database import (
    init_db,
    elenco_modelli,
    ultimo_benchmark,
)
from OLLAMA_SML_AGENT.sml_tester import esegui_tutti_i_test, salva_risultato_json


def benchmark_tutti() -> dict:
    init_db()
    modelli = elenco_modelli()
    if not modelli:
        print("Nessun modello registrato. Aggiungine uno con:")
        print("  python OLLAMA_SML_AGENT/sml_database.py --aggiungi <nome> [quant] [dim_gb]")
        return {}

    report = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "modelli_testati": [],
        "riepilogo": {},
    }

    for m in modelli:
        nome = m["nome"]
        print(f"\n=== Test modello: {nome} (ID {m['id']}) ===")
        res = esegui_tutti_i_test(nome, salva_db=True, salva_json_file=True)
        report["modelli_testati"].append(res)

        # Salva JSON individuale già fatto dentro esegui_tutti_i_test

        # Aggiorna riepilogo
        report["riepilogo"][nome] = {
            "promosso": res["promosso"],
            "livello_raggiunto": res["livello_raggiunto"],
            "modello_id": res["modello_id"],
        }

    # Salva report complessivo
    from OLLAMA_SML_AGENT.sml_tester import RESULTS_DIR

    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    path_report = RESULTS_DIR / f"report_benchmark_{ts}.json"
    from CORE.state_repository import save_json

    save_json(str(path_report), report)
    print(f"\nReport complessivo salvato in: {path_report}")
    return report


def stampa_riepilogo() -> None:
    """Stampa lo stato attuale di tutti i modelli registrati."""
    init_db()
    modelli = elenco_modelli()
    print("\n=== Riepilogo modelli SML registrati ===\n")
    print(f"{'ID':<4} {'Nome':<25} {'Quant':<12} {'Dim(GB)':<8} {'Promosso':<9} {'Livello'}")
    print("-" * 70)
    for m in modelli:
        b = ultimo_benchmark(m["id"])
        promosso = "SÌ" if b and b["promosso"] else "NO"
        livello = b["data_benchmark"] if b else "-"
        print(
            f"{m['id']:<4} {m['nome']:<25} "
            f"{str(m['quantizzazione']):<12} {str(m['dimensione_gb']):<8} "
            f"{promosso:<9} {livello}"
        )
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark modelli SML su Ollama")
    parser.add_argument("--tutti", action="store_true", help="Esegue test su tutti i modelli registrati")
    parser.add_argument("--riepilogo", action="store_true", help="Stampa riepilogo stato modelli")
    args = parser.parse_args()

    if args.riepilogo:
        stampa_riepilogo()
    elif args.tutti:
        benchmark_tutti()
    else:
        parser.print_help()
