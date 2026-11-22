# 🔍 Sonde di sblocco — M2…M6

Generato (UTC): `2026-11-22T15:05:43+00:00`

> Solo dati letti ora da file/sysfs/comandi locali. Nessun valore
> inventato, nessuna chiamata API, nessun LLM. I blocchi restano aperti
> finché l'azione esterna non è stata eseguita e riverificata.

| ID | Stato | Evidenza | Azione richiesta |
|---|---|---|---|
| M2 suite completa | 🔒 | VIETATA dalla regola termica 2026-11-20 | trigger CI: `gh workflow run profile.yml -R wildlux/byte-swarmy` |
| M3 ventole | 🔒 | CPU 65.0 °C, RPM 0, nbfc `inactive` | avviare nbfc con pkexec, poi `tools/blocker_probe.py --write-fan` |
| M4 credenziali | 🔒 | gh: interprete shebang assente: /usr/local/bin/python3.14; remote token-free: ✅ | riparare gh, `gh auth login`, revocare la PAT su GitHub |
| M5 hardening | 🔒 | utente ❌, slice ❌ | `sudo scripts/setup/hardening.sh --all` |
| M6 profiling CI | 🔒 | run #2 fallito: Profilazione completa (--durations=0) — run #2 | interprete shebang assente: /usr/local/bin/python3.14; poi `gh workflow run profile.yml -R wildlux/byte-swarmy` |

## Dettaglio termico (M3)

| Misura | Valore |
|---|---|
| Temperatura CPU (coretemp) | 65.0 °C |
| Sorgente temperatura | `/sys/class/hwmon/hwmon3/temp1_input, /sys/class/hwmon/hwmon3/temp2_input, /sys/class/hwmon/hwmon3/temp3_input, /sys/class/hwmon/hwmon3/temp4_input, /sys/class/hwmon/hwmon3/temp5_input` |
| RPM ventola | 0 (nessuna sorgente) |
| Dettaglio nbfc | ERROR: nbfc: connect(): No such file or directory: /var/run/nbfc_service.socket |
| PWM sysfs | 0 nodi (indizio, non RPM) |
| `fan_rpm > 0` | ❌ |
| `temp_c <= 60` | ❌ |
| Gate verificabile | ❌ |
| `fan_verified.json` salvato | ❌ |

Il file di gate non viene mai scritto con valori passati a mano:
`--write-fan` rilegge i sensori e rifiuta se il gate non è verificato.

## Dettaglio credenziali (M4)

| Controllo | Valore |
|---|---|
| Eseguibile gh | `/home/wildlux/.local/bin/gh` — interprete shebang assente: /usr/local/bin/python3.14 |
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
