# A/B varianti prompt — Fase G

Modalità: **DRY-RUN / SIMULAZIONE**
Task set congelato: `182ae2a82284` (11 casi della eval suite con expected_marker)

| Variante | Passati | Totale | Tasso |
|---|---:|---:|---:|
| `baseline` | 1 | 11 | 0.09 |
| `refs_off` | 0 | 11 | 0.00 |
| `refs_first` | 3 | 11 | 0.27 |
| `plan_compact` | 5 | 11 | 0.45 |

| Variante vs baseline | Delta | Verdetto |
|---|---:|---|
| `refs_off` | -0.09 | **REJECT** |
| `refs_first` | +0.18 | **INCONCLUSIVE** |
| `plan_compact` | +0.36 | **INCONCLUSIVE** |

Regola: rate >= 0.60 e delta >= 0.20 → PROMOTE; delta <= 0 → REJECT; altrimenti INCONCLUSIVE.

> ⚠️ Il solver è **finto**: l'HINT è assegnato per hash del case_id. Questo verdetto **NON è un esperimento reale** e non autorizza alcuna promozione di prompt.
> Il live richiede `data/state/fan_verified.json` con `fan_rpm > 0` e `temp_c <= 60`, più un solver reale passato dal chiamante.

