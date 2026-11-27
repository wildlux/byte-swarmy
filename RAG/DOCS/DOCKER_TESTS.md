# Test in container — riferimento comandi

Ambiente isolato per eseguire i test deterministici fuori dalla sessione GUI.
**Nessun LLM**: il `Dockerfile` crea `state/pause.flag`, quindi gli e2e live
vengono saltati come su GitHub Actions.

## Stato verification (2026-11-22)

| Gate | Esito |
|---|---|
| `docker compose config -q` | ✅ YAML valido |
| `docker buildx build --check .` | ✅ `Check complete, no warnings found` |
| Immagine costruita | ❌ No (nessun `docker compose build` eseguito) |
| Suite eseguita | ❌ No: regola termica del 2026-11-20 vieta la suite completa in locale; usare `.github/workflows/profile.yml` |

I comandi sotto sono quindi **documentati e validati nella sintassi**, non
eseguiti: la build richiede il pull di `python:3.11-slim` (~50 MB) e spazio
disco, oggi non disponibile (17 GB liberi su `/home`, 95% usato).

## Prerequisiti

Docker con plugin Compose e Buildx. Nessun modello Ollama, nessuna rete
nell'esecuzione dei test (solo nella fase di build per `pip install`).

## Comandi

Validazione senza build (sempre sicura, zero download):

```bash
docker compose config -q
docker buildx build --check .
```

Build dell'immagine (una sola volta):

```bash
docker compose build
```

Suite completa — **solo su GitHub Actions**, non in locale:

```bash
docker compose run --rm tests
```

Sottoinsieme mirato (esempio, nessun LLM):

```bash
docker compose run --rm tests \
  python -m pytest tests/test_config_gates.py tests/test_slot_planner.py -q
```

Lint e nomi indefiniti:

```bash
docker compose run --rm tests python tools/lint_style.py CORE tools tests
docker compose run --rm tests \
  python -m pyflakes $(find CORE GUI tools SAFETY tests -name '*.py' -not -path '*/archiviati/*' | sort)
```

Compile di tutte le fonti:

```bash
docker compose run --rm tests \
  python -m compileall -q CORE GUI tools scripts SAFETY INTENT tests
```

## Regole

- `QT_QPA_PLATFORM=offscreen` è già impostato nell'immagine.
- `state/pause.flag` è creato al build: i test live e2e restano saltati.
- `.dockerignore` esclude `.venv`, `.git`, `state/`, `data/state/`, `logs/`,
  `project/` e i cache: il contesto di build resta piccolo e riproducibile.
- Nessun volume scrivibile: ogni run parte da uno stato pulito.
