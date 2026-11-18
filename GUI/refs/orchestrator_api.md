# Namespace: Orchestrator
# Modulo: CORE.orchestrator
# Orchestrator API — cheat sheet (byte-swarmy)

Modulo: CORE.orchestrator. Il worker NON istanzia l'orchestratore (è il
processo padre); questo ref serve per scrivere codice che lo richiama o
per capire le sue funzioni di bootstrap.

## Funzioni di modulo
- `setup_logger(config)` → logger
- `load_config(path="CONFIG/config.toml")` → dict
- `main()` → entry point CLI

## Classe `Orchestrator`
Costruttore: `Orchestrator(config_path="CONFIG/config.toml")`.

Metodi pubblici (API stabile):
- `preflight_and_queue(prompt, params)`
- `run()`

## Note
- Non istanziare `Orchestrator` dal worker: è già in esecuzione come
  processo padre (PID in `state/orchestrator.pid`).
- Per interagire dal worker: tool swarm_status, swarm_time, pause,
  resume, cancel_task, approve_task, run_audit (vedi toolset_api.md).

## Regola d'oro
L'orchestratore è il supervisore: il worker non lo tocca direttamente.
Se serve uno stato, usa `state/` o i tool swarm_*.
