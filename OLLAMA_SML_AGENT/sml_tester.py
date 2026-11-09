"""
sml_tester.py — Esegue i 3 test atomici contro un modello SML su Ollama API.

Livelli:
  1 — Parsing JSON puro (output solo JSON, niente testo extra)
  2 — Safe project path (valida se un path è dentro project/)
  3 — Refactoring minuscolo (divide una funzione in due)

I risultati vengono salvati su CORE/state_repository stile (JSON in
OLLAMA_SML_AGENT/results/) e nel database sml_models.db.

Dipendenze: solo stdlib (json, urllib.request, sqlite3 via sml_database).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from CORE.state_repository import save_json
from OLLAMA_SML_AGENT.sml_database import (
    init_db,
    aggiungi_modello,
    get_modello_id,
    salva_parametri,
    salva_risultato,
    salva_benchmark,
    ultimo_benchmark,
)

BASE_DIR = Path(__file__).resolve().parent.parent
OLLAMA_HOST = "http://localhost:11434"
RESULTS_DIR = BASE_DIR / "OLLAMA_SML_AGENT" / "results"
SYSTEM_PROMPT_PATH = BASE_DIR / "OLLAMA_SML_AGENT" / "system_prompt.txt"

# Parametri di default per i test SML (modelli piccoli = deterministi)
DEFAULT_TEMPERATURE = 0.1
DEFAULT_NUM_PREDICT = 512
DEFAULT_NUM_CTX = 2048
DEFAULT_REPEAT_PENALTY = 1.15
DEFAULT_SEED = 42


def _leggi_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "Rispondi solo con JSON valido, niente testo extra."


def _chiamata_ollama(
    modello: str,
    prompt: str,
    temperatura: float = DEFAULT_TEMPERATURE,
    num_predict: int = DEFAULT_NUM_PREDICT,
    num_ctx: int = DEFAULT_NUM_CTX,
    repeat_penalty: float = DEFAULT_REPEAT_PENALTY,
    seed: int = DEFAULT_SEED,
    system: Optional[str] = None,
    timeout: int = 60,
) -> str:
    """Chiama /api/generate di Ollama e ritorna il campo 'response'."""
    payload = {
        "model": modello,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperatura,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "repeat_penalty": repeat_penalty,
            "seed": seed,
        },
    }
    if system:
        payload["system"] = system

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data_risposta = json.loads(resp.read().decode("utf-8"))
    return data_risposta.get("response", "")


def _prova_json(testo: str) -> Optional[dict]:
    """Prova a parsificare il testo come JSON. Ritorna None se non valido."""
    try:
        return json.loads(testo)
    except json.JSONDecodeError:
        return None


def test_livello_1(modello: str, system_prompt: str) -> dict:
    """Livello 1: Parsing JSON puro."""
    prompt = 'RISPONDI SOLO CON: {"nome":"prova","valore":42}'
    try:
        output = _chiamata_ollama(modello, prompt, system=system_prompt)
    except Exception as e:
        return {
            "livello": 1,
            "test": "parsing_json",
            "esito": "errore",
            "punteggio": 0.0,
            "output_grezzo": "",
            "errore": str(e),
        }

    parsato = _prova_json(output)
    if parsato is None:
        return {
            "livello": 1,
            "test": "parsing_json",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "errore": "Output non è JSON valido",
        }

    # Verifica che contenga le chiavi attese
    if parsato.get("nome") != "prova" or parsato.get("valore") != 42:
        return {
            "livello": 1,
            "test": "parsing_json",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Chiavi/valori non corrispondono",
        }

    return {
        "livello": 1,
        "test": "parsing_json",
        "esito": "promosso",
        "punteggio": 1.0,
        "output_grezzo": output,
        "output_parsato": parsato,
    }


def test_livello_2(modello: str, system_prompt: str) -> dict:
    """Livello 2: Safe project path."""
    prompt = (
        "Il percorso 'sub/file.txt' è sicuro dentro project/? "
        "Rispondi SOLO con JSON {\"sicuro\": true/false, \"motivo\": \"...\"}"
    )
    try:
        output = _chiamata_ollama(modello, prompt, system=system_prompt)
    except Exception as e:
        return {
            "livello": 2,
            "test": "safe_project_path",
            "esito": "errore",
            "punteggio": 0.0,
            "output_grezzo": "",
            "errore": str(e),
        }

    parsato = _prova_json(output)
    if parsato is None:
        return {
            "livello": 2,
            "test": "safe_project_path",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "errore": "Output non è JSON valido",
        }

    if "sicuro" not in parsato or "motivo" not in parsato:
        return {
            "livello": 2,
            "test": "safe_project_path",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Mancano chiavi 'sicuro' o 'motivo'",
        }

    # sub/file.txt è relativo, non assoluto, niente .. -> sicuro
    if parsato["sicuro"] is True:
        esito = "promosso"
        punteggio = 1.0
    else:
        esito = "bocciato"
        punteggio = 0.0

    return {
        "livello": 2,
        "test": "safe_project_path",
        "esito": esito,
        "punteggio": punteggio,
        "output_grezzo": output,
        "output_parsato": parsato,
    }


def test_livello_3(modello: str, system_prompt: str) -> dict:
    """Livello 3: Refactoring minuscolo."""
    prompt = (
        'Dividi questa funzione Python in due: una che legge e una che scrive. '
        'Rispondi SOLO con JSON {"funzione_lettura": "...", "funzione_scrittura": "..."}'
    )
    try:
        output = _chiamata_ollama(modello, prompt, system=system_prompt)
    except Exception as e:
        return {
            "livello": 3,
            "test": "refactoring_minuscolo",
            "esito": "errore",
            "punteggio": 0.0,
            "output_grezzo": "",
            "errore": str(e),
        }

    parsato = _prova_json(output)
    if parsato is None:
        return {
            "livello": 3,
            "test": "refactoring_minuscolo",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "errore": "Output non è JSON valido",
        }

    if "funzione_lettura" not in parsato or "funzione_scrittura" not in parsato:
        return {
            "livello": 3,
            "test": "refactoring_minuscolo",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Mancano chiavi 'funzione_lettura' o 'funzione_scrittura'",
        }

    # Controllo basilare: i valori sono stringhe non vuote
    if not parsato["funzione_lettura"] or not parsato["funzione_scrittura"]:
        return {
            "livello": 3,
            "test": "refactoring_minuscolo",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Valori vuoti",
        }

    return {
        "livello": 3,
        "test": "refactoring_minuscolo",
        "esito": "promosso",
        "punteggio": 1.0,
        "output_grezzo": output,
        "output_parsato": parsato,
    }


def esegui_tutti_i_test(
    modello: str,
    salva_db: bool = True,
    salva_json_file: bool = True,
) -> dict:
    """Esegue i 3 livelli in sequenza. Se il livello 1 fallisce, si ferma."""
    init_db()
    system_prompt = _leggi_system_prompt()

    modello_id = get_modello_id(modello)
    if modello_id is None:
        # Registra automaticamente il modello se non c'è
        modello_id = aggiungi_modello(modello)

    # Salva parametri di default usati
    salva_parametri(
        modello_id,
        DEFAULT_TEMPERATURE,
        DEFAULT_NUM_PREDICT,
        DEFAULT_NUM_CTX,
        DEFAULT_REPEAT_PENALTY,
        DEFAULT_SEED,
    )

    risultati = {}
    l1 = test_livello_1(modello, system_prompt)
    risultati["livello_1"] = l1
    salva_risultato(
        modello_id, 1, "parsing_json", l1["esito"], l1["punteggio"],
        l1.get("output_grezzo"), l1.get("output_parsato"), l1.get("errore"),
    )

    if l1["esito"] != "promosso":
        # Ferma qui: non ha senso provare i livelli successivi
        salva_benchmark(modello_id, False, False, False, False)
        return {
            "modello": modello,
            "modello_id": modello_id,
            "promosso": False,
            "livello_raggiunto": 1,
            "risultati": risultati,
        }

    l2 = test_livello_2(modello, system_prompt)
    risultati["livello_2"] = l2
    salva_risultato(
        modello_id, 2, "safe_project_path", l2["esito"], l2["punteggio"],
        l2.get("output_grezzo"), l2.get("output_parsato"), l2.get("errore"),
    )

    if l2["esito"] != "promosso":
        salva_benchmark(modello_id, True, False, False, False)
        return {
            "modello": modello,
            "modello_id": modello_id,
            "promosso": False,
            "livello_raggiunto": 2,
            "risultati": risultati,
        }

    l3 = test_livello_3(modello, system_prompt)
    risultati["livello_3"] = l3
    salva_risultato(
        modello_id, 3, "refactoring_minuscolo", l3["esito"], l3["punteggio"],
        l3.get("output_grezzo"), l3.get("output_parsato"), l3.get("errore"),
    )

    promosso = l3["esito"] == "promosso"
    salva_benchmark(modello_id, True, True, True, promosso)

    return {
        "modello": modello,
        "modello_id": modello_id,
        "promosso": promosso,
        "livello_raggiunto": 3,
        "risultati": risultati,
    }


def salva_risultato_json(report: dict) -> str:
    """Salva il report su file JSON in OLLAMA_SML_AGENT/results/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    import time

    ts = datetime_str = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_file = f"test_{report['modello'].replace(':', '_')}_{ts}.json"
    path = RESULTS_DIR / nome_file
    save_json(str(path), report)
    return str(path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test atomici per modello SML su Ollama")
    parser.add_argument("--modello", required=True, help="Nome modello Ollama (es. qwen2.5:1.5b)")
    parser.add_argument("--livello", type=int, choices=[1, 2, 3], help="Esegue solo un livello")
    args = parser.parse_args()

    if args.livello == 1:
        r = test_livello_1(args.modello, _leggi_system_prompt())
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.livello == 2:
        r = test_livello_2(args.modello, _leggi_system_prompt())
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.livello == 3:
        r = test_livello_3(args.modello, _leggi_system_prompt())
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        report = esegui_tutti_i_test(args.modello)
        path = salva_risultato_json(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\nReport salvato in: {path}")
        print(f"Promosso: {report['promosso']}")
