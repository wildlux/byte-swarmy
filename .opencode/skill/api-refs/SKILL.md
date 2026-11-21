---
name: api-refs
description: Skill per gestire e iniettare riferimenti API (refs) per ridurre le allucinazioni del modello, anche su API nuove, tramite introspezione runtime (api_lookup) e cheat sheet. Usa quando l'utente chiede di seguire API corrette o di generare codice con librerie nuove/sconosciute.
---

# API Refs — skill per seguire API corrette (anche nuove)

Flusso: **identifica libreria → introspezione/ref → inietta nel prompt → genera → gate**.

## 1. Scopo

- Ridurre le allucinazioni su API (nomi/firme inesistenti).
- Funziona per API nuove: tramite introspezione runtime (`api_lookup`) o refs manuali.

## 2. Strategie (dal più forte al più debole)

1. **Introspezione runtime**: `api_lookup(module, symbol)` usa `inspect.signature`/`dir()` sul pacchetto installato → firma reale. Funziona per qualsiasi libreria installata.
2. **Refs (cheat sheet)**: file in `GUI/refs/` o `CORE/refs/` con firme API. Iniettati nel prompt. Per API nuove, creare il ref manualmente o con `tools/gen_api_refs.py`.
3. **Compile gate**: `py_compile`/`make` rifiuta simbodo inesistenti → correction prompt con l'errore + lista tool/API.
4. **Correction loop**: fino a 3 retry con prompt di correzione.

## 3. Workflow

1. Identifica la libreria e il simbodo necessario.
2. Chiama `api_lookup(module, symbol)` per ottenere firma + docstring reali.
3. Se il pacchetto non è installato, cerca/crea un ref in `CORE/refs/` o `GUI/refs/`.
4. Inietta le firme nel prompt (sezione `## API REFS`).
5. Genera il codice.
6. Gate: compile + lint + import-check (nomi indefiniti = allucinazione).

## 4. Quality gates

- Ogni simbodo usato deve esistere (verificato da `import_check`).
- Per API nuove: almeno un ref o una chiamata `api_lookup` nel contesto.
- Nessun simbodo inventato passa il gate compile.

## 5. Comandi chiave

```text
api_lookup("json", "dumps")
api_lookup("pathlib", "Path.read_text")
list_refs()   # elenca i cheat sheet disponibili
```
