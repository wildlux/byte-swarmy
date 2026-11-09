"""
cli.py — Interfaccia a linea di comando per l'ottimizzatore SML.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from OLLAMA_SML_AGENT.config import DEFAULT_SML_MODELS
from OLLAMA_SML_AGENT.model_discovery import (
    scopri_modelli_ollama,
    filtra_modelli_piccoli,
    stampa_modelli,
)
from OLLAMA_SML_AGENT.sml_tester_senior import esegui_tutti_i_test_senior
from OLLAMA_SML_AGENT.auto_optimizer import AutoOptimizer
from OLLAMA_SML_AGENT.ensemble_runner import EnsembleRunner


def cmd_scopri(args):
    modelli = scopri_modelli_ollama()
    piccoli = filtra_modelli_piccoli(modelli, max_parametri=args.max)
    stampa_modelli(piccoli)


def cmd_testa(args):
    from OLLAMA_SML_AGENT.sml_database import init_db
    init_db()
    print(f"Testando modello: {args.modello}")
    report = esegui_tutti_i_test_senior(args.modello)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_ottimizza(args):
    from OLLAMA_SML_AGENT.sml_database import init_db
    init_db()
    opt = AutoOptimizer(args.modello)
    report = opt.testa_singolo(args.task, _leggi_system_prompt())
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_ensemble(args):
    from OLLAMA_SML_AGENT.sml_tester import _leggi_system_prompt
    system_prompt = open(args.system, encoding="utf-8").read()
    ens = EnsembleRunner(args.modelli)
    risultati = ens.esegui_su_tutti(args.task, system_prompt)
    voto = ens.vota(risultati)
    print(json.dumps(voto, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="SML Optimizer CLI")
    sub = parser.add_subparsers(dest="comando")

    p_scopri = sub.add_parser("scopri", help="Scopri modelli Ollama disponibili")
    p_scopri.add_argument("--max", default="7B", help="Max parametri (default 7B)")
    p_scopri.set_defaults(func=cmd_scopri)

    p_testa = sub.add_parser("testa", help="Testa un modello singolo")
    p_testa.add_argument("--modello", required=True)
    p_testa.add_argument("--task", default="Crea una funzione Python che sommi due numeri interi.")
    p_testa.set_defaults(func=cmd_testa)

    p_opt = sub.add_parser("ottimizza", help="Ottimizza un modello con loop iterativo")
    p_opt.add_argument("--modello", required=True)
    p_opt.add_argument("--task", required=True)
    p_opt.set_defaults(func=cmd_ottimizza)

    p_ens = sub.add_parser("ensemble", help="Esegue ensemble su più modelli")
    p_ens.add_argument("--modelli", nargs="+", required=True)
    p_ens.add_argument("--task", required=True)
    p_ens.add_argument("--system", required=True)
    p_ens.set_defaults(func=cmd_ensemble)

    args = parser.parse_args()
    if args.comando:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
