# 📈 Self-Improvement Report

_Fonte: `data/state` — generato deterministicamente, zero LLM._

## Corpus di feedback

| Metrica | Valore |
|---|---|
| Triple totali | 72 |
| Triple uniche | 24 |
| Task distinti | 20 |
| Tasso primo colpo | 0.958 |
| Tasso correzione | 0.042 |

| Verdetto | Conteggio | Quota |
|---|---|---|
| `done` | 69 | 95.8% |
| `failed_definitively` | 0 | 0.0% |
| `corrected` | 3 | 4.2% |

> ⚠️ **Brutal honesty**: il tasso primo colpo è calcolato sulle 72 triple del corpus (24 uniche, 20 task distinti). Sono **fixture interne** (test, adversarial, regressioni), non task utente reali: non dimostra la soglia '≥50% task chiusi al primo tentativo'. Task GUI live: non misurato.

## Gate e apprendimento

| Metrica | Valore |
|---|---|
| Gate verdi (skill) | 0 |
| Gate rossi (skill) | 0 |
| Proposte pending | 2 |
| Proposte approvate | 0 |
| Proposte rifiutate | 0 |
| Override non conformi | 0 |

## Copertura retrieval

| Metrica | Valore |
|---|---|
| Task con testo indicizzabile | 20/20 |
| Copertura | 100.0% |

> ⚠️ La copertura indica solo che `title`/`description` sono indicizzabili; **non misura la qualità del retrieval** né che il contesto migliori le risposte.
