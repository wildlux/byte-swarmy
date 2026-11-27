# 📈 Self-Improvement Report

_Fonte: `data/state` — generato deterministicamente, zero LLM._

## Corpus di feedback

| Metrica | Valore |
|---|---|
| Triple totali | 82 |
| Triple uniche | 26 |
| Task distinti | 20 |
| Tasso primo colpo | 0.841 |
| Tasso correzione | 0.159 |

| Verdetto | Conteggio | Quota |
|---|---|---|
| `corrected` | 13 | 15.9% |
| `done` | 69 | 84.1% |
| `failed_definitively` | 0 | 0.0% |

> ⚠️ **Brutal honesty**: il tasso primo colpo è calcolato sulle 82 triple del corpus (26 uniche, 20 task distinti). Sono **fixture interne** (test, adversarial, regressioni), non task utente reali: non dimostra la soglia '≥50% task chiusi al primo tentativo'. Task GUI live: misurato 1/3 (33%); sotto la soglia del 50%.

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
