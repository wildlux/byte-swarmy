# 🔍 Sonde di sblocco — M2…M6

Generato (UTC): `2026-11-22T15:12:45+00:00`

> Solo dati letti ora da file/sysfs/comandi locali. Nessun valore
> inventato, nessuna chiamata API, nessun LLM. I blocchi restano aperti
> finché l'azione esterna non è stata eseguita e riverificata.

| ID | Stato | Evidenza | Azione richiesta |
|---|---|---|---|
| M2 suite completa | 🔒 | VIETATA dalla regola termica 2026-11-20 | trigger CI: `gh workflow run profile.yml -R wildlux/byte-swarmy` |
| M3 ventole | 🔒 | CPU 64.0 °C, RPM 0, nbfc `daemon attivo` | avviare nbfc con pkexec, poi `tools/blocker_probe.py --write-fan` |
| M4 credenziali | 🔒 | gh: `gh` trovato ma NON è GitHub CLI: apre solo il browser; remote token-free: ✅ | installare la CLI (`sudo apt install gh`), `gh auth login`, revocare la PAT |
| M5 hardening | 🔒 | utente ❌, slice ❌ | `sudo scripts/setup/hardening.sh --all` |
| M6 profiling CI | 🔒 | run #2 fallito: Profilazione completa (--durations=0) — run #2 | `gh` trovato ma NON è GitHub CLI: apre solo il browser; poi `gh workflow run profile.yml -R wildlux/byte-swarmy` |

## Dettaglio termico (M3)

| Misura | Valore |
|---|---|
| Temperatura CPU (coretemp) | 64.0 °C |
| Sorgente temperatura | `/sys/class/hwmon/hwmon3/temp1_input, /sys/class/hwmon/hwmon3/temp2_input, /sys/class/hwmon/hwmon3/temp3_input, /sys/class/hwmon/hwmon3/temp4_input, /sys/class/hwmon/hwmon3/temp5_input` |
| RPM ventola | 0 (nbfc status (Current Fan Speed)) |
| Duty richiesto | 10.0 % (Target Fan Speed) |
| Unità systemd | `inactive` |
| Dettaglio nbfc | Read-only                : false |
| PWM sysfs | 0 nodi (indizio, non RPM) |
| `fan_rpm > 0` | ❌ |
| `temp_c <= 60` | ❌ |
| Gate verificabile | ❌ |
| `fan_verified.json` salvato | ❌ |

Il file di gate non viene mai scritto con valori passati a mano:
`--write-fan` rilegge i sensori e rifiuta se il gate non è verificato.

Su questa macchina il daemon nbfc è stato avviato via pkexec, ma
`Current Fan Speed` resta 0.00 anche con duty al 100% e non esiste
alcun `fan*_input` in sysfs: il tachimetro non è leggibile. Pertanto
`fan_rpm > 0` NON è dimostrabile con i sensori disponibili: il gate
resta chiuso finché non si decide una misura alternativa verificabile.

## Dettaglio credenziali (M4)

| Controllo | Valore |
|---|---|
| Eseguibile gh | `/home/wildlux/.local/bin/gh` — `gh` trovato ma NON è GitHub CLI: apre solo il browser |
| GitHub CLI ufficiale | ❌ (script-browser) |
| Installazione suggerita | `sudo apt install gh` |
| Autenticazione gh | ❌ |
| Remote origin | `git@github.com:wildlux/byte-swarmy.git` |
| Token nel remote | ❌ |
| `state/cloud_api.json` 0600 | ✅ |
| `~/.git-credentials` 0600 | ✅ |
| Rotazione PAT confermata | ❌ — La revoca della PAT va verificata su GitHub, non deducibile dal FS |

## Regole di onestà

- Nessun asse del radar viene alzato da questa sonda.
- Nessuna suite completa locale viene lanciata per aggirare il gate termico.
- M2 resta non misurato finché il workflow CI non produce un artifact.
- Il 0600 dei file locali NON dimostra che un token esposto sia stato revocato.
