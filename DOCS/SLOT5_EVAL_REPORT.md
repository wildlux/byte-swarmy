# SLOT-5 — pass@1 per tipo di slot

Modalità: **DRY-RUN / SIMULAZIONE**
Casi con expected_marker: **11** (2 casi gate/chiarimento esclusi: pass@1 non si applica)

| Tipo slot | Passati | Totale | pass@1 |
|---|---:|---:|---:|
| `class` | 1 | 1 | 1.00 |
| `function` | 5 | 5 | 1.00 |
| `statement` | 0 | 2 | 0.00 |
| `widget` | 1 | 3 | 0.33 |

| Dimensione output | Passati | Totale | pass@1 |
|---|---:|---:|---:|
| `large` (121+ righe) | 3 | 4 | 0.75 |
| `medium` (41-120 righe) | 2 | 4 | 0.50 |
| `small` (0-40 righe) | 2 | 3 | 0.67 |

Dimensioni: small 0-40, medium 41-120, large 121+ righe. Nessun asse del radar viene alzato da questo report.

> ⚠️ Risultati **sintetici**: `passed` deriva da un hash del case_id. Questa tabella **non è una misura** e non chiude SLOT-5.
> Serve un file `--results` con `source: "live"`, evidenza termica (`fan_rpm > 0`, `temp_c <= 60`) e 12+ casi reali.

