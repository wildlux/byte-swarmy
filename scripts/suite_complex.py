"""Suite COMPLESSA T11–T20: task più difficili dei T1–T10, pensati per
stressare skill, gate, correction loop e routing.

Eseguita su un modello alla volta (CLI arg), routing OFF (confronta i
MODELLI, non il sistema instradato). Output incrementale in
state/suite_complex/results.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from CORE.skill_executor import run_direct  # noqa: E402

PROJECT = "project/PR_TEST_progetto"

TASKS = [
    ("T11", "Crea una classe Contatore con metodi incrementa, decrementa, "
            "reset e valore. Nel main: crea un contatore, incrementa 3 "
            "volte, decrementa 1 volta, stampa VALORE=2, poi reset e stampa "
            "VALORE=0."),
    ("T12", "Crea un context manager Timer che misura i millisecondi di "
            "esecuzione di un blocco with. Nel main: usa il Timer per "
            "misurare una funzione che somma i numeri da 1 a 100000 e "
            "stampa SOMMA=5000050000 e TEMPO in millisecondi (numero "
            "positivo)."),
    ("T13", "Implementa un decoratore retry che ritenta una funzione fino "
            "a 3 volte se solleva un'eccezione, stampando TENTATIVO=n ad "
            "ogni retry. Applicalo a una funzione che fallisce le prime 2 "
            "volte e riesce la terza, stampando RISULTATO=ok."),
    ("T14", "Crea un generatore infinito di numeri di Fibonacci. Nel main: "
            "prendi i primi 10 numeri e stampali uno per riga, poi stampa "
            "SOMMA=122 (somma dei primi 10)."),
    ("T15", "Implementa un produttore-consumatore con threading e una "
            "coda (queue.Queue) con capacità 3. Il produttore produce i "
            "numeri 1..6, il consumatore li consuma. Stampa PRODOTTO=6 e "
            "CONSUMATO=6."),
    ("T16", "Crea una funzione che trova tutti i numeri primi fino a N "
            "usando il crivello di Eratostene. Nel main: stampa i primi "
            "usando N=30 e poi stampa COUNT=10 (i primi <= 30 sono 10)."),
    ("T17", "Parser di espressioni: dato un dizionario di variabili "
            "{'x': 5, 'y': 3}, valuta l'espressione 'x * y + 2' e stampa "
            "RISULTATO=17. Supporta +, -, *, / e variabili."),
    ("T18", "Implementa una classe Cache LRU con capacità 2: metodi get e "
            "put. Nel main: put(1, 'a'), put(2, 'b'), get(1) stampa 'a', "
            "put(3, 'c') (evict 2), get(2) stampa None, get(3) stampa 'c'."),
    ("T19", "Crea un argparse CLI con sottocomandi 'add' (aggiunge numero "
            "a lista) e 'sum' (somma la lista). Nel main: simula add 5, "
            "add 3, add 2, poi sum e stampa TOTALE=10."),
    ("T20", "Implementa un unittest.TestCase con 3 test: test_somma, "
            "test_sottrazione, test_moltiplicazione. Nel main esegui i "
            "test con unittest.main(exit=False) e stampa TEST_PASSATI=3."),
    ("T21", "Crea un sistema che legge un file grande riga per riga e conta "
            "le parole uniche, stampa COUNT=5. Scegli il pattern architetturale "
            "migliore per memoria O(1)."),
]


def main() -> int:
    models = sys.argv[1:] or ["worker_coder"]
    out_dir = Path("state/suite_complex")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.json"
    results: dict = {}
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            results = {}
    for model in models:
        results.setdefault(model, {})
        for tid, text in TASKS:
            if tid in results[model] and results[model][tid].get("done"):
                continue
            t0 = time.monotonic()
            try:
                res = run_direct(
                    {"title": text}, PROJECT, model_key=model,
                    max_retries=3, enable_routing=False)
            except Exception as e:
                res = {"ok": False, "attempts": 0, "error": f"runner: {e}",
                       "stdout": "", "history": []}
            dt = round(time.monotonic() - t0, 1)
            res["done"] = True
            res["secs"] = dt
            results[model][tid] = res
            out_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False),
                encoding="utf-8")
            print(f"[{model}] {tid}: "
                  f"{'ok' if res['ok'] else 'FAIL'} "
                  f"(attempts {res.get('attempts')}, {dt}s)", flush=True)
            if not res["ok"]:
                print(f"   error: {(res.get('error') or '')[:160]}",
                      flush=True)
                for h in res.get("history", []):
                    print(f"   └ {h.get('attempt')} | "
                          f"{(h.get('error') or '')[:140]}", flush=True)
    print(f"\nRISULTATI SALVATI: {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
