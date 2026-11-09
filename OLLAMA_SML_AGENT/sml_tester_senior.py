"""
sml_tester_senior.py — Test atomici "senior" per modelli SML.

Valuta il formato testo strutturato (ANALISI, CODICE, TEST, SICUREZZA,
FIDUCIA, TASK_COMPLETO) definito nel system_prompt.txt di livello senior v3.1.

Dipendenze: solo stdlib.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from OLLAMA_SML_AGENT.sml_database import (
    init_db,
    aggiungi_modello,
    get_modello_id,
    salva_parametri,
    salva_risultato,
    salva_benchmark,
)
from OLLAMA_SML_AGENT.sml_tester import _leggi_system_prompt, _chiamata_ollama
from OLLAMA_SML_AGENT.logbook import salva_tentativo

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = BASE_DIR / "OLLAMA_SML_AGENT" / "results"

CAMPI_OBBLIGATORI = [
    "analisi", "codice", "test",
]

CAMPI_OPZIONALI = ["rischi", "piano", "alternative", "fiducia", "task_completo", "sicurezza"]

DEFAULT_TEMPERATURE = 0.1
DEFAULT_NUM_PREDICT = 512
DEFAULT_NUM_CTX = 2048
DEFAULT_REPEAT_PENALTY = 1.15
DEFAULT_SEED = 42


def _pulizia_blocchi_markdown(testo: str) -> str:
    """Estrae il contenuto del primo blocco ```python ... ``` da un testo.
    Se non ci sono blocchi markdown, restituisce il testo così com'è."""
    if not testo:
        return testo
    lines = testo.splitlines()
    in_code_block = False
    code_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```python") or stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                continue
            else:
                break
        if in_code_block:
            code_lines.append(line)
    if code_lines:
        return "\n".join(code_lines)
    return testo.strip()


def _parsifica_testo_strutturato(testo: str) -> dict:
    """Parsifica il formato testo strutturato in un dizionario."""
    risultato = {c: "" for c in CAMPI_OBBLIGATORI}
    for c in CAMPI_OPZIONALI:
        if c in ("rischi", "alternative"):
            risultato[c] = []
        else:
            risultato[c] = ""

    campo_corrente: Optional[str] = None
    righe = testo.splitlines()

    for riga in righe:
        riga_strip = riga.strip()

        # Rileva inizio di un nuovo campo
        if riga_strip.upper().startswith("ANALISI:"):
            campo_corrente = "analisi"
            valore = riga_strip[len("ANALISI:"):].strip()
            if valore:
                risultato["analisi"] = valore
            continue
        if riga_strip.upper().startswith("RISCHI:"):
            campo_corrente = "rischi"
            valore = riga_strip[len("RISCHI:"):].strip()
            if valore:
                if valore.startswith("- "):
                    risultato["rischi"].append(valore[2:].strip())
                else:
                    risultato["rischi"].append(valore)
            continue
        if riga_strip.upper().startswith("PIANO:"):
            campo_corrente = "piano"
            valore = riga_strip[len("PIANO:"):].strip()
            if valore:
                risultato["piano"] += valore + "\n"
            continue
        if riga_strip.upper().startswith("CODICE:"):
            campo_corrente = "codice"
            valore = riga_strip[len("CODICE:"):].strip()
            if valore:
                risultato["codice"] += valore + "\n"
            continue
        if riga_strip.upper().startswith("TEST:"):
            campo_corrente = "test"
            valore = riga_strip[len("TEST:"):].strip()
            if valore:
                risultato["test"] += valore + "\n"
            continue
        if riga_strip.upper().startswith("SICUREZZA:"):
            campo_corrente = "sicurezza"
            valore = riga_strip[len("SICUREZZA:"):].strip()
            if valore:
                risultato["sicurezza"] = valore
            continue
        if riga_strip.upper().startswith("ALTERNATIVE:"):
            campo_corrente = "alternative"
            valore = riga_strip[len("ALTERNATIVE:"):].strip()
            if valore:
                if valore.startswith("- "):
                    risultato["alternative"].append(valore[2:].strip())
                else:
                    risultato["alternative"].append(valore)
            continue
        if riga_strip.upper().startswith("FIDUCIA:"):
            campo_corrente = "fiducia"
            valore = riga_strip[len("FIDUCIA:"):].strip()
            try:
                risultato["fiducia"] = float(valore)
            except ValueError:
                risultato["fiducia"] = 0.0
            continue
        if riga_strip.upper().startswith("TASK_COMPLETO:"):
            campo_corrente = "task_completo"
            valore = riga_strip[len("TASK_COMPLETO:"):].strip().lower()
            risultato["task_completo"] = valore in ("true", "1", "sì", "si")
            continue

        # Se siamo dentro un campo multilinea, aggiungi la riga
        if campo_corrente == "rischi" and riga_strip.startswith("- "):
            risultato["rischi"].append(riga_strip[2:].strip())
        elif campo_corrente == "alternative" and riga_strip.startswith("- "):
            risultato["alternative"].append(riga_strip[2:].strip())
        elif campo_corrente == "piano" and riga_strip:
            risultato["piano"] += riga_strip + "\n"
        elif campo_corrente == "codice" and riga_strip:
            risultato["codice"] += riga + "\n"
        elif campo_corrente == "test" and riga_strip:
            risultato["test"] += riga + "\n"
        elif campo_corrente == "analisi" and riga_strip:
            risultato["analisi"] += riga_strip + " "
        elif campo_corrente == "sicurezza" and riga_strip:
            if riga_strip.startswith("- "):
                risultato["sicurezza"] += riga_strip[2:].strip() + " "
            else:
                risultato["sicurezza"] += riga_strip + " "

    # Pulizia finale
    if isinstance(risultato["piano"], str):
        risultato["piano"] = risultato["piano"].strip()
    if isinstance(risultato["codice"], str):
        risultato["codice"] = _pulizia_blocchi_markdown(risultato["codice"]).strip()
    if isinstance(risultato["test"], str):
        risultato["test"] = _pulizia_blocchi_markdown(risultato["test"]).strip()

    return risultato


def _valida_campi(parsato: dict) -> list:
    """Ritorna lista dei campi obbligatori mancanti o vuoti."""
    mancanti = []
    for c in CAMPI_OBBLIGATORI:
        if c not in parsato or parsato[c] is None or parsato[c] == "":
            mancanti.append(c)
    return mancanti


def _valida_fiducia(parsato: dict) -> bool:
    f = parsato.get("fiducia")
    if f is None or f == "":
        return True  # mancante, uso default 0.5 nelle funzioni di test
    return isinstance(f, (int, float)) and 0.0 <= f <= 1.0


def test_senior_livello_1(
    modello: str, system_prompt: str
) -> dict:
    """
    Livello 1 senior: task semplice — somma due interi con tipi, docstring,
    gestione errore.
    """
    prompt = (
        'Task: "Crea una funzione Python che sommi due numeri interi e '
        'restituisca il risultato. Include type hints, docstring e '
        'gestione errore se gli argomenti non sono interi."\n'
        'Rispondi SOLO con il formato testo strutturato richiesto.'
    )
    try:
        output = _chiamata_ollama(modello, prompt, system=system_prompt, num_predict=512)
    except Exception as e:
        return {
            "livello": 1,
            "test": "senior_somma_interi",
            "esito": "errore",
            "punteggio": 0.0,
            "output_grezzo": "",
            "errore": str(e),
            "prompt_inviato": prompt,
        }

    parsato = _parsifica_testo_strutturato(output)
    parsato["codice"] = _pulizia_blocchi_markdown(parsato.get("codice", ""))
    parsato["test"] = _pulizia_blocchi_markdown(parsato.get("test", ""))
    if not parsato.get("sicurezza"):
        parsato["sicurezza"] = "non specificato"
    mancanti = _valida_campi(parsato)
    if mancanti:
        return {
            "livello": 1,
            "test": "senior_somma_interi",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": f"Campi mancanti o vuoti: {mancanti}",
            "prompt_inviato": prompt,
        }

    # Applica default per campi opzionali mancanti
    if not parsato.get("fiducia"):
        parsato["fiducia"] = 0.5
    if not parsato.get("task_completo"):
        parsato["task_completo"] = bool(parsato.get("codice") and parsato.get("test"))

    codice = parsato.get("codice", "")
    test = parsato.get("test", "")
    if "def " not in codice or "return" not in codice:
        return {
            "livello": 1,
            "test": "senior_somma_interi",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Il campo 'codice' non contiene una funzione con return",
            "prompt_inviato": prompt,
        }
    if "assert" not in test:
        return {
            "livello": 1,
            "test": "senior_somma_interi",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Il campo 'test' non contiene assert",
            "prompt_inviato": prompt,
        }

    return {
        "livello": 1,
        "test": "senior_somma_interi",
        "esito": "promosso",
        "punteggio": 1.0,
        "output_grezzo": output,
        "output_parsato": parsato,
        "prompt_inviato": prompt,
    }


def test_senior_livello_2(
    modello: str, system_prompt: str
) -> dict:
    """
    Livello 2 senior: valida path sicuro.
    """
    prompt = (
        'Task: "Valida se il percorso relative "docs/readme.md" è sicuro '
        'dentro project/. Non importa se il file esiste: conta solo la forma '
        'del path."\nRispondi SOLO con il formato testo strutturato.'
    )
    try:
        output = _chiamata_ollama(modello, prompt, system=system_prompt, num_predict=512)
    except Exception as e:
        return {
            "livello": 2,
            "test": "senior_safe_path",
            "esito": "errore",
            "punteggio": 0.0,
            "output_grezzo": "",
            "errore": str(e),
            "prompt_inviato": prompt,
        }

    parsato = _parsifica_testo_strutturato(output)
    parsato["codice"] = _pulizia_blocchi_markdown(parsato.get("codice", ""))
    parsato["test"] = _pulizia_blocchi_markdown(parsato.get("test", ""))
    if not parsato.get("sicurezza"):
        parsato["sicurezza"] = "non specificato"
    mancanti = _valida_campi(parsato)
    if mancanti:
        return {
            "livello": 2,
            "test": "senior_safe_path",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": f"Campi mancanti o vuoti: {mancanti}",
            "prompt_inviato": prompt,
        }

    # Applica default per campi opzionali mancanti
    if not parsato.get("fiducia"):
        parsato["fiducia"] = 0.5
    if not parsato.get("task_completo"):
        parsato["task_completo"] = bool(parsato.get("codice") and parsato.get("test"))

    # Il modello dovrebbe identificare che docs/readme.md è sicuro
    # Verifica che il codice generato contenga logica corretta:
    codice = parsato.get("codice", "")

    # Se il codice dice esplicitamente che il path NON è sicuro, boccia
    if "non sicuro" in (parsato.get("sicurezza", "") + " " + parsato.get("analisi", "")).lower() and "docs/readme.md" in parsato.get("analisi", "").lower():
        return {
            "livello": 2,
            "test": "senior_safe_path",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Modello dichiara docs/readme.md come non sicuro",
            "prompt_inviato": prompt,
        }

    # Il codice deve contenere una funzione di validazione path con return booleano
    if "def " not in codice or "return" not in codice:
        return {
            "livello": 2,
            "test": "senior_safe_path",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Il codice non contiene una funzione di validazione path con return booleano",
            "prompt_inviato": prompt,
        }

    return {
        "livello": 2,
        "test": "senior_safe_path",
        "esito": "promosso",
        "punteggio": 1.0,
        "output_grezzo": output,
        "output_parsato": parsato,
        "prompt_inviato": prompt,
    }


def test_senior_livello_3(
    modello: str, system_prompt: str
) -> dict:
    """
    Livello 3 senior: refactoring con valutazione di design.
    """
    prompt = (
        'Task: "Ecco una funzione che fa troppo cose:\\n\\n'
        'def elabora_dati(dati):\\n'
        '    risultato = []\\n'
        '    for d in dati:\\n'
        '        if d > 0:\\n'
        '            risultato.append(d * 2)\\n'
        '        else:\\n'
        '            risultato.append(0)\\n'
        '    return risultato\\n\\n'
        'Dividila in due funzioni: una che trasforma e una che filtra. '
        'Spiega perché la separazione migliora manutenibilità e testabilità.'
        'Rispondi SOLO con il formato testo strutturato.'
    )
    try:
        output = _chiamata_ollama(modello, prompt, system=system_prompt, num_predict=512)
    except Exception as e:
        return {
            "livello": 3,
            "test": "senior_refactoring",
            "esito": "errore",
            "punteggio": 0.0,
            "output_grezzo": "",
            "errore": str(e),
            "prompt_inviato": prompt,
        }

    parsato = _parsifica_testo_strutturato(output)
    parsato["codice"] = _pulizia_blocchi_markdown(parsato.get("codice", ""))
    parsato["test"] = _pulizia_blocchi_markdown(parsato.get("test", ""))
    if not parsato.get("sicurezza"):
        parsato["sicurezza"] = "non specificato"
    mancanti = _valida_campi(parsato)
    if mancanti:
        return {
            "livello": 3,
            "test": "senior_refactoring",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": f"Campi mancanti o vuoti: {mancanti}",
            "prompt_inviato": prompt,
        }

    # Applica default per campi opzionali mancanti
    if not parsato.get("fiducia"):
        parsato["fiducia"] = 0.5
    if not parsato.get("task_completo"):
        parsato["task_completo"] = bool(parsato.get("codice") and parsato.get("test"))

    # Il codice deve contenere almeno 2 funzioni definite
    codice = parsato.get("codice", "")
    if codice.count("def ") < 2:
        return {
            "livello": 3,
            "test": "senior_refactoring",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": f"Il codice contiene solo {codice.count('def ')} definizioni di funzione, serve almeno 2",
            "prompt_inviato": prompt,
        }

    # L'analisi deve menzionare separazione, complessità, manutenibilità o testabilità
    analisi_testo = (
        str(parsato.get("analisi", "")) + " " +
        str(parsato.get("piano", "")) + " " +
        str(parsato.get("sicurezza", ""))
    ).lower()
    parole_chiave = ["manuten", "test", "leggibil", "separaz", "modular", "complessa", "troppo", "dividi", "semplifica"]
    if not any(p in analisi_testo for p in parole_chiave):
        return {
            "livello": 3,
            "test": "senior_refactoring",
            "esito": "bocciato",
            "punteggio": 0.0,
            "output_grezzo": output,
            "output_parsato": parsato,
            "errore": "Nessuna motivazione di separazione/complessità nell'analisi",
            "prompt_inviato": prompt,
        }

    return {
        "livello": 3,
        "test": "senior_refactoring",
        "esito": "promosso",
        "punteggio": 1.0,
        "output_grezzo": output,
        "output_parsato": parsato,
        "prompt_inviato": prompt,
    }


def esegui_tutti_i_test_senior(
    modello: str, salva_db: bool = True, salva_json_file: bool = True
) -> dict:
    init_db()
    system_prompt = _leggi_system_prompt()

    modello_id = get_modello_id(modello)
    if modello_id is None:
        modello_id = aggiungi_modello(modello)

    salva_parametri(
        modello_id,
        DEFAULT_TEMPERATURE,
        DEFAULT_NUM_PREDICT,
        DEFAULT_NUM_CTX,
        DEFAULT_REPEAT_PENALTY,
        DEFAULT_SEED,
    )

    risultati = {}
    l1 = test_senior_livello_1(modello, system_prompt)
    risultati["livello_1"] = l1
    salva_risultato(
        modello_id, 1, "senior_somma_interi", l1["esito"], l1["punteggio"],
        l1.get("output_grezzo"), l1.get("output_parsato"), l1.get("errore"),
    )
    salva_tentativo(
        modello=modello,
        quantizzazione="Q4_K_M",
        dimensione_gb=1.0,
        prompt_versione="v3.1",
        livello=1,
        prompt_inviato=l1.get("prompt_inviato", ""),
        output_grezzo=l1.get("output_grezzo", ""),
        output_parsato=l1.get("output_parsato"),
        esito=l1["esito"],
        punteggio=l1["punteggio"],
        errore=l1.get("errore"),
        note_miglioramento=None,
    )

    if l1["esito"] != "promosso":
        salva_benchmark(modello_id, False, False, False, False)
        return {"modello": modello, "modello_id": modello_id,
                "promosso": False, "livello_raggiunto": 1, "risultati": risultati}

    l2 = test_senior_livello_2(modello, system_prompt)
    risultati["livello_2"] = l2
    salva_risultato(
        modello_id, 2, "senior_safe_path", l2["esito"], l2["punteggio"],
        l2.get("output_grezzo"), l2.get("output_parsato"), l2.get("errore"),
    )
    salva_tentativo(
        modello=modello,
        quantizzazione="Q4_K_M",
        dimensione_gb=1.0,
        prompt_versione="v3.1",
        livello=2,
        prompt_inviato=l2.get("prompt_inviato", ""),
        output_grezzo=l2.get("output_grezzo", ""),
        output_parsato=l2.get("output_parsato"),
        esito=l2["esito"],
        punteggio=l2["punteggio"],
        errore=l2.get("errore"),
        note_miglioramento=None,
    )

    if l2["esito"] != "promosso":
        salva_benchmark(modello_id, True, False, False, False)
        return {"modello": modello, "modello_id": modello_id,
                "promosso": False, "livello_raggiunto": 2, "risultati": risultati}

    l3 = test_senior_livello_3(modello, system_prompt)
    risultati["livello_3"] = l3
    salva_risultato(
        modello_id, 3, "senior_refactoring", l3["esito"], l3["punteggio"],
        l3.get("output_grezzo"), l3.get("output_parsato"), l3.get("errore"),
    )
    salva_tentativo(
        modello=modello,
        quantizzazione="Q4_K_M",
        dimensione_gb=1.0,
        prompt_versione="v3.1",
        livello=3,
        prompt_inviato=l3.get("prompt_inviato", ""),
        output_grezzo=l3.get("output_grezzo", ""),
        output_parsato=l3.get("output_parsato"),
        esito=l3["esito"],
        punteggio=l3["punteggio"],
        errore=l3.get("errore"),
        note_miglioramento=None,
    )

    promosso = l3["esito"] == "promosso"
    salva_benchmark(modello_id, True, True, True, promosso)

    return {"modello": modello, "modello_id": modello_id,
            "promosso": promosso, "livello_raggiunto": 3, "risultati": risultati}


def salva_risultato_json(report: dict) -> str:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_file = f"senior_v31_test_{report['modello'].replace(':', '_')}_{ts}.json"
    path = RESULTS_DIR / nome_file
    from CORE.state_repository import save_json
    save_json(str(path), report)
    return str(path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test SENIOR v3.1 per modello SML su Ollama")
    parser.add_argument("--modello", required=True, help="Nome modello Ollama")
    parser.add_argument("--livello", type=int, choices=[1, 2, 3],
                        help="Esegue solo un livello")
    args = parser.parse_args()

    if args.livello == 1:
        r = test_senior_livello_1(args.modello, _leggi_system_prompt())
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.livello == 2:
        r = test_senior_livello_2(args.modello, _leggi_system_prompt())
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.livello == 3:
        r = test_senior_livello_3(args.modello, _leggi_system_prompt())
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        report = esegui_tutti_i_test_senior(args.modello)
        path = salva_risultato_json(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\nReport salvato in: {path}")
        print(f"Promosso: {report['promosso']}")
