# OLLAMA_SML_AGENT — Test e benchmark modelli piccoli (SML)

Questa cartella contiene tutto il necessario per testare, valutare e catalogare
modelli linguistici locali piccoli (1.5B–4B) per l'uso dentro BYTE-SWARMY.

## Struttura

| File | Scopo |
|------|-------|
| `system_prompt.txt` | System prompt rigido da usare con i modelli SML |
| `sml_database.py` | Gestione database SQLite (modelli, parametri, risultati) |
| `sml_tester.py` | Esegue i 3 test atomici contro l'API Ollama e salva i risultati |
| `sml_benchmark.py` | Confronta più modelli e genera un report di benchmark |
| `results/` | Risultati JSON dei singoli test |
| `sml_models.db` | Database SQLite (viene creato automaticamente) |

## Livelli di test (atomici)

1. **Livello 1 — Parsing JSON**: il modello deve rispondere SOLO con JSON valido.
2. **Livello 2 — Safe project path**: il modello valida se un path è sicuro dentro `project/`.
3. **Livello 3 — Refactoring minuscolo**: il modello divide una funzione in due.

Un modello viene "promosso" solo se supera tutti e 3 i livelli.

## Avvio rapido

```bash
# 1. Assicurati che Ollama sia attivo e il modello caricato
ollama pull qwen2.5:1.5b
ollama run qwen2.5:1.5b

# 2. Registra un modello nel database
.venv/bin/python OLLAMA_SML_AGENT/sml_database.py --aggiungi qwen2.5:1.5b --quantizzazione Q4_K_M --dimensione_gb 1.1

# 3. Esegui i test atomici
.venv/bin/python OLLAMA_SML_AGENT/sml_tester.py --modello qwen2.5:1.5b --livello 1
.venv/bin/python OLLAMA_SML_AGENT/sml_tester.py --modello qwen2.5:1.5b --livello 2
.venv/bin/python OLLAMA_SML_AGENT/sml_tester.py --modello qwen2.5:1.5b --livello 3

# 4. Esegui benchmark completo su tutti i modelli registrati
.venv/bin/python OLLAMA_SML_AGENT/sml_benchmark.py --tutti

# 5. Report
cat OLLAMA_SML_AGENT/results/report_ultimo.json
```
