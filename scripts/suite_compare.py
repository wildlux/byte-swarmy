"""Suite comparativa T1-T10: worker_coder (3B) vs worker_coder_big (4B).

Fase 7 punto 4 (valutazione): gli stessi 10 task della suite storica
(esatti testi di todo.md) eseguiti su ENTRAMBI i modelli con la stessa
pipeline (skill + mappa + gate statico/runtime), routing OFF per
confrontare i MODELLI e non il sistema instradato.

Output: state/suite_compare/results.json — mai solleva per singolo task.
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
    ("T1", "fammi un software in python che calcola media, mediana e moda "
           "di una lista di numeri. Usa la lista [4, 2, 7, 2, 5] come dati "
           "di esempio e stampa i tre valori."),
    ("T2", "convertitore che trasforma gradi celsius in fahrenheit con "
           "gestione degli errori per input non numerico. Converti 25 gradi "
           "e stampa il risultato, poi prova a convertire la stringa "
           "\"abc\" gestendo l'errore senza crash."),
    ("T3", "Creare una classe Collezione che implementa __len__, "
           "__contains__ e __iter__. Nel main: aggiungi \"a\", \"b\", \"c\", "
           "stampa LEN=3, verifica che contenga \"b\" stampando HAS=True e "
           "itera gli elementi stampandoli uno per riga."),
    ("T4", "software che verifica se una frase è palindroma ignorando spazi "
           "e maiuscole, e conta la frequenza delle parole. Frase: "
           "\"I topi non avevano nipoti\". Stampa PALINDROMO=True e la "
           "parola più frequente."),
    ("T5", "Gestione rubrica con persistenza su file json: aggiungi Mario "
           "Rossi 12345 e Luca Bianchi 67890, salva su rubrica.json, "
           "rileggi dal file e cerca \"Mario\" stampando TROVATO=12345."),
    ("T6", "calcolo della sequenza di fibonacci con memoizzazione "
           "(dizionario). Stampa il valore per n=50."),
    ("T7", "crea una finestra gui con un campo testo, un pulsante che "
           "aggiunge l'articolo a una lista e un pulsante che pulisce la "
           "lista. Titolo: Lista della spesa."),
    ("T8", "Classe Stack con capacity=3, metodi push/pop/peek, eccezioni "
           "personalizzate StackOverflowError e StackUnderflowError. Nel "
           "main: push di 4 elementi gestendo l'overflow stampando "
           "OVERFLOW=ok, poi pop di tutti e gestisci lo stack vuoto "
           "stampando UNDERFLOW=ok."),
    ("T9", "Decoratore misura_tempo che stampa i millisecondi di "
           "esecuzione di una funzione. Applicalo a una funzione che somma "
           "i numeri da 1 a 100000 e stampa SOMMA=5000050000."),
    ("T10", "software per trasporre una matrice: matrice [[1,2,3],[4,5,6]] "
            "trasformata in [[1,4],[2,5],[3,6]], stampa ogni riga della "
            "trasposta su una riga separata."),
]

MODELS = ["worker_coder", "worker_coder_big"]


def main() -> int:
    # Modelli da CLI (es. `python3 scripts/suite_compare.py worker_granite`),
    # default: la comparativa storica 3B vs 4B.
    models = sys.argv[1:] or MODELS
    out_dir = Path("state/suite_compare")
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
                continue  # riprendibile: salta i task già finiti
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
            # salvataggio incrementale: interrompere non perde il lavoro
            out_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False),
                encoding="utf-8")
            print(f"[{model}] {tid}: "
                  f"{'ok' if res['ok'] else 'FAIL'} "
                  f"(attempts {res.get('attempts')}, {dt}s)",
                  flush=True)
    print(f"\nRISULTATI SALVATI: {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
