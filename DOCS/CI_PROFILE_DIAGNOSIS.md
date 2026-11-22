# Diagnosi run CI #2 — `profile.yml` (2026-11-22)

Fonti: GitHub Actions REST API (pubblica, sola lettura) e git locale. **Nessun
trigger, nessuna credenziale, nessun log letto senza auth**: l'artifact resta
privato e il suo contenuto non è stato scaricato.

| Dato | Valore | Fonte |
|---|---|---|
| Run #2 | `44838701460`, `workflow_dispatch`, `main` | `GET /actions/workflows/profile.yml/runs` |
| Commit | `e3f90bed97e1a31f48e8a64e7acc65ef18a864e8` | API + `git show` |
| Esito | `failure`, job `profile`, 26 s totali | `GET /actions/runs/44838701460/jobs` |
| Step 4 (Install dependencies) | ✅ 14 s | API jobs |
| Step 5 (pausa e2e) | ✅ <1 s | API jobs |
| Step 6 (`Profilazione completa`) | ❌ **3 s** (23:42:26 → 23:42:29) | API jobs |
| Artifact `pytest-profile` | 1227 byte, `expired: false` | `GET /actions/runs/44838701460/artifacts` |
| Download artifact / job logs | 🔒 `401 Requires authentication` / `403` | tentativo di lettura, non ripetuto |

## Interpretazione (onesta)

Uno step che decade in **3 secondi** non può aver eseguito la suite (in locale
la sola raccolta richiede ~1,7 s e la suite completa ~17 min). Il log di 1227
byte è coerente con un errore di **collezione/import**, non con test falliti.
**Non possiamo leggere il messaggio esatto** senza credenziali GitHub: la causa
è un'ipotesi, non un verdetto.

## Mitigazioni già nel repo (dopo il run #2)

| Commit | Modifica |
|---|---|
| `f35f9dd` | Aggiunto step `Diagnostica collezione (--collect-only)`, con `collect.log` separato |
| `b3ec027` | Artifact ampliato a `pytest_profile.log` + `collect.log` |

## Verifica locale successiva (senza eseguire test)

```
QT_QPA_PLATFORM=offscreen timeout 120 .venv/bin/python -m pytest tests/ \
  --collect-only -q -p no:cacheprovider
EXIT=0 · 1094 tests collected in 1.71s
```

Quindi la collezione **nell'ambiente locale attuale** funziona: se la causa del
run #2 era un import rotto, non è più riproducibile su `HEAD`. Resta da provare
su runner GitHub, dove le dipendenze vengono reinstallate da `requirements.txt`.

## Stato M6

- 🔒 **Trigger ancora bloccato**: serve CLI GitHub ufficiale + auth
  (`gh workflow run profile.yml -R wildlux/byte-swarmy`). Il `gh` presente è uno
  script browser 0.0.4, non la CLI.
- ✅ Diagnosi, strumenti di diagnosi e lock del workflow: fatti (Cycle 112).
- ⛔ Nessun nuovo run avviato, nessuna suite locale completa, nessun LLM.
