# Fase H — giudice di qualità (mai sovrano)

Modalità: **DRY-RUN / SIMULAZIONE**

Il gate deterministico è l'unica autorità: il parere del giudice è consultivo e non cambia mai il verdetto finale.

| Metrica | Valore |
|---|---:|
| Casi | 13 |
| Giudice consultato | 7 |
| Concordi | 4 |
| Tasso accordo | 0.5714 |
| Override bloccati | 2 |
| Gate invariato | True |

| Classificazione | Conteggio |
|---|---:|
| `concur_pass` | 4 |
| `judge_ignored_gate_fail` | 3 |
| `not_consulted` | 6 |

> ⚠️ Pareri **sintetici** derivati da un hash del case_id: questa tabella **non è una misura** e non chiude Fase H.
> Criterio done: report accordo gate↔giudice su **20 casi reali** con pareri `source: "live"` e gate termico verificato.

