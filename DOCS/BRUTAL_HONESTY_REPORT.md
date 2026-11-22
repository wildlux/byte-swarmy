# 🧾 Brutal honesty — verifica dei report

_Generato deterministicamente da `tools/brutal_honesty_report.py` — zero LLM, zero rete, zero GPU, zero timestamp._

Scopo: dire cosa è **veramente verificabile** nei report e nei documenti di `DOCS/`. Quando un numero cambia, cambia questo file: non si scrive a mano un verdetto diverso dai dati.

## Verdetto sintetico

| Affermazione | Verdetto | Evidenza |
|---|---|---|
| Zero Warning (pyflakes) | ✅ PASS | 0 finding di pyflakes |
| best-of-N 'attivo (fast lane)' | ⚠️ DISABILITATO | `fast_lane.enabled=false`, `best_of_n=1` |
| First-try 0.958 come task reali | ⚠️ FIXTURE INTERNE | 77 triple, 25 uniche, 20 task distinti; 0.950 sugli unici |
| Copertura retrieval 100% | ⚠️ DEFINIZIONE RISTRETTA | 20/20: solo presenza di testo indicizzabile, non qualità del retrieval |
| Meccanismi 'attivi' (storico 41) | ⚠️ DOCUMENTATI/IMPLEMENTATI | 42 righe contate; non tutti abilitati a runtime |
| Auto-skill 23 / auto-tool 30 (Cycle 86) | ⚠️ STALE | oggi 27 skill / 36 tool |

## Correzione applicata ai documenti

| Controllo | Stato |
|---|---|
| Link al report da `DOCS/MIGLIORAMENTI.md` | ✅ |
| Claim '0 warning ✅ raggiunto' rimosso | ✅ |
| Claim 'fast lane attivo' rimosso | ✅ |
| Meccanismi definiti 'documentati/implementati' | ✅ |
| Caveat 'fixture interne' nel report self-improvement | ✅ |
| Caveat 'non misura la qualità' nel report retrieval | ✅ |

## Da dove viene il 0.958

Il tasso `first_try` è `0.896` su 77 triple. Il corpus contiene **fixture interne** (test, adversarial, regressioni), non task utente reali: non può dimostrare la soglia '≥50% task chiusi al primo tentativo' del radar. Sugli unici task distinti il valore è `0.950`; il task GUI live resta 🔒 non misurato.

| File corpus | Triple | First-try |
|---|---:|---:|
| `m3-test.jsonl` | 30 | 25 |
| `adv-tests.test_security_hardcore.TestPromptInjectionAdversarial..jsonl` | 15 | 15 |
| `inject-1.jsonl` | 7 | 5 |
| `cb-1.jsonl` | 4 | 4 |
| `e2e-1.jsonl` | 4 | 4 |
| `env-1.jsonl` | 4 | 4 |

## Limiti che NON sono stati toccati

- I valori del radar restano **giudizi espliciti**, non misure derivate: il Cycle 100 ha corretto le frasi; il Cycle 101 ha aggiunto l'asse Mobile a 2/4 come scaffold offline, non come build verificata.
- La suite completa non è stata rieseguita in questo ciclo: l'ultima green resta il run3 del 2026-11-19.
- E1/E2 sono gate validati su campioni sintetici, non una garanzia repo-wide; E3 live e A/B live restano 🔒 bloccati termicamente.
