# Namespace: SchedulerWorker
# Modulo: CORE.scheduler_worker
# Scheduler API — cheat sheet (byte-swarmy)

Modulo: CORE.scheduler_worker. Scheduler deterministico dei task periodici.

## Costanti
- `SCHEDULED_FILE` — path del file di schedule
- `DEFAULT_INTERVAL` — intervallo default (secondi)

## Classe `SchedulerLogic`
- `is_due(task, now)` → bool
- `mark_run(task, now)` → aggiorna last_run
- `build_queue_task(task)` → dict (task per la coda)

## Classe `SchedulerWorker`
- `tick_once()` → esegue un ciclo
- `run()` → loop principale
- `stop()` → ferma

## Regola d'oro
Lo scheduler non è il worker: schedula, non esegue. I task schedulati
entrano nella coda come task normali.
