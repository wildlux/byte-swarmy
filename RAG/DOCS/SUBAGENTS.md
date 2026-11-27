# Subagent a un solo livello — policy e verifica (2026-11-22)

Byte-Swarmy può creare **agenti figli** (subagent) con identità e memoria
proprie, riutilizzando i ruoli modello già presenti in `CONFIG/config.toml`.
Non è annidamento ricorsivo: l'orchestratore/worker padre crea figli, i figli
non possono creare a loro volta figli.

## Confini (interpretati in autonomia, nessuna domanda all'utente)

| Regola | Valore | Motivo |
|---|---|---|
| Profondità massima | 1 (`MAX_DEPTH`) | niente deleghe ricorsive |
| Figli per padre | 4 (`MAX_CHILDREN`) | limita fan-out e costo LLM |
| Totale registry | 32 (`MAX_TOTAL`) | tetto globale per sessione |
| Ruoli modello | solo `[models.*]` esistenti, esclusi `orchestrator`/`planner`/`embedding` | non si inventano modelli |
| LLM in `spawn()` | **mai** | il figlio gira solo in `get_subagent_report()` |
| Cap wall-clock | `timeout` (default 60 s) | timeout esplicito, mai `done` con figlio pendente |
| Gate termico | ≤60 °C, `state/pause.flag`, temperatura disponibile | incidente shutdown 90 °C del 2026-11-20 |
| Esecuzione live | **bloccata** finché la ventola non è verificata | coerenza con le altre sessioni LLM |

## API

| Tool | Firma | Effetto |
|---|---|---|
| `spawn_subagent` | `spawn_subagent(model_key, task)` | crea il figlio, ritorna `agent_id`; zero LLM |
| `get_subagent_report` | `get_subagent_report(agent_id)` | applica i gate, esegue il figlio se `pending`, ritorna il report |
| `list_subagents` | `list_subagents()` | elenca figli con stato, modello, timestamp |

Nel system prompt del worker i codici brevi sono `spawn`, `subreport`, `sublist`,
mappati ai nomi completi in `Worker.TOOL_CODE_MAP`. Le keyword
`auto_tool.detect_names("crea subagent")` → `spawn_subagent` abilitano
l'iniezione automatica della firma nel pannello Chat.

## Sicurezza e fail-open

- `spawn()` valida `parent_id` (`^[A-Za-z0-9_-]{1,64}$`), `model_key` contro
  `[models.*]`, task non vuoto e ≤4000 caratteri, profondità e limiti.
- Ogni errore diventa una stringa `ERROR: ...` o `BLOCKED: ...`, mai un'eccezione
  verso il worker: il padre riceve sempre un report leggibile.
- `run()` è idempotente su `done`: ripetere `get_subagent_report()` non riesegue
  l'LLM. Timeout e blocchi sono registrati come `failed`/`BLOCKED`.
- I test (`tests/test_subagent.py`) usano `temp_fn`, `runner` e model client
  **fake**: zero rete, zero Ollama, zero cloud.

## Gate eseguiti

| Gate | Esito |
|---|---|
| `pytest tests/test_subagent.py -q` | 8 passed (1,17 s) |
| `compileall` su 5 file | OK |
| `tools/lint_style.py` | 0 errori |
| `tools/security_scan.py` | S030/S031 puliti |
| `git diff --check` | OK |

Fuori scope: annidamento >1, parallelismo dei figli, nuovi ruoli modello,
credenziali cloud. Esecuzione live solo dopo la verifica della ventola.
