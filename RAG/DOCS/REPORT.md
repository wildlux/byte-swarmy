# 📊 REPORT — byte-swarmy Test Suite

**Generato il**: 2026-11-12 20:16:16
**Macchina**: 4 GB RAM / 4 GB VRAM (Kubuntu/Ubuntu)
**Branch**: main

## 1. Modelli testati

| Modello | Ruolo | Parametri | Stato |
|---|---|---|---|
| qwen2.5-coder:3b | Base (titolare) | 3B | ✅ 10/10 suite T1-T10 |
| kirito1/qwen3-coder:4b | Candidato heavy | 4B | ❌ 4/10 (×19 più lento, timeout) |
| granite4:7b-a1b-h | Heavy (scelto) | 7B MoE (~1B attivi) | ✅ 10/10 suite T1-T10 |

## 2. Suite comparativa T1–T10 (routing OFF, stessa pipeline)

| Task | 3B (worker_coder) | 4B (worker_coder_big) | granite4 (worker_granite) |
|---|---|---|---|
| T1 Statistiche numeriche | ✅ 2att 22.4s | ❌ 3att 262.3s | ✅ 1att 35.2s |
| T2 Convertitore temperature | ✅ 1att 9.7s | ✅ 2att 164.5s | ✅ 1att 7.9s |
| T3 Classe Collezione | ✅ 1att 8.6s | ❌ 3att 301.1s | ✅ 2att 32.8s |
| T4 Palindromo + frequenza | ✅ 1att 11.2s | ❌ 3att 315.3s | ✅ 1att 12.7s |
| T5 Rubrica JSON | ✅ 1att 10.3s | ✅ 1att 55.9s | ✅ 1att 9.8s |
| T6 Fibonacci memoizzato | ✅ 1att 7.8s | ✅ 3att 248.6s | ✅ 2att 17.5s |
| T7 GUI PyQt6 | ✅ 1att 26.7s | ✅ 3att 324.4s | ✅ 1att 28.5s |
| T8 Stack + eccezioni | ✅ 2att 22.9s | ❌ 2att 405.0s | ✅ 1att 12.8s |
| T9 Decoratore misura_tempo | ✅ 1att 10.9s | ❌ 1att 300.5s | ✅ 1att 10.9s |
| T10 Trasposizione matrice | ✅ 1att 7.4s | ❌ 1att 300.5s | ✅ 1att 7.0s |
| **Totale** | **10/10** (137.9s) | **4/10** (2678.1s) | **10/10** (175.1s) |

## 3. Spot-check heavy (post-ottimizzazioni)

| Run | Esito | Tempo | Note |
|---|---|---|---|
| worker_coder_big/T9 | ❌ FAIL | 304.6s |  |
| worker_granite/T9 | ✅ ok | 31.2s | Tempo di esecuzione: 1.22 ms SOMMA=5000050000  |
| worker_granite/T1 | ✅ ok | 10.1s | Media: 4.0 Mediana: 4 Moda: [2]  |

## 4. Test e2e routing live (M2)

- **routing_live_alta**: ✅ ok, 3 att, 37.6s, model=worker_granite
  - route: `complessità alta → worker_granite (heavy worker_granite) | impatto alta (2 file, profondità 2, simboli citati: Statistiche, media, mediana)`
  - stdout: `MEDIA=4
MEDIANA=4
`

## 5. Suite complessa T11–T21 (3B)

| Task | Descrizione | Esito | Att. | Tempo |
|---|---|---|---|---|
| T11 | Classe Contatore | ✅ | 1 | 17.9s |
| T12 | Context manager Timer | ✅ | 1 | 10.2s |
| T13 | Decoratore retry | ✅ | 1 | 10.6s |
| T14 | Generatore Fibonacci | ✅ | 1 | 8.3s |
| T15 | Producer-consumer threading | ✅ | 1 | 8.0s |
| T16 | Crivello Eratostene | ✅ | 1 | 9.5s |
| T17 | Parser espressioni | ✅ | 1 | 6.0s |
| T18 | Cache LRU | ✅ | 1 | 12.0s |
| T19 | argparse CLI | ✅ | 3 | 22.6s |
| T20 | unittest self-test | ✅ | 1 | 12.1s |
| T21 | Arch decision (GENERATOR) | ✅ | 2 | 13.7s |
| **Totale** | | **11/11** | | |

## 6. Suite dati complessi (campione 3 task/categoria)

| Categoria | OK | Totale | % |
|---|---|---|---|
| programmazione_complessa | 3 | 3 | 100% |
| programmazione_enterprise | 3 | 3 | 100% |
| qt_python_complessi | 0 | 3 | 0% |
| qt_python_enterprise | 2 | 2 | 100% |
| sicurezza_rete_compless | 2 | 3 | 67% |
| sicurezza_software_alto_enterprise | 2 | 3 | 67% |
| **Totale** | **12** | **17** | **71%** |

## 7. Batterie di test (unit, senza LLM)

| Batteria | Test | Stato |
|---|---|---|
| test_usability_hardcore.py | 35 | ✅ OK |
| test_correction.py | 7 | ✅ OK |
| test_routing.py | 39 | ✅ OK |
| test_skill_proposer.py | 8 | ✅ OK |
| test_model_selector.py | 24 | ✅ OK |
| test_oracle_gate.py | 7 | ✅ OK |
| test_behavioral_diff.py | 8 | ✅ OK |
| test_behavioral_check.py | 4 | ✅ OK |
| test_diagnosis.py | 6 | ✅ OK |
| test_task_atomizer.py | 12 | ✅ OK |
| test_memory_compaction.py | 5 | ✅ OK |
| test_relevant_symbols.py | 5 | ✅ OK |
| **Totale** | **160** | **✅ tutti verdi** |

## 8. Miglioramenti applicati (P1–P15)

| # | Area | Descrizione | Stato |
|---|---|---|---|
| P1 | Prompt | SYSTEM_DIRECT: output deve iniziare col fence, placeholder = syntax error | ✅ |
| P2 | Tool | extract_code: tronca prosa alla prima riga Python | ✅ |
| P3 | Skill | py-text-analyze: placeholder in prosa → commento inerte | ✅ |
| P4 | Prompt | Regola istanza: usa oggetto = Class() | ✅ |
| P5 | Skill | py-class-module: except Exception di default | ✅ |
| P6 | Tool | Timeout per-modello in ollama_client | ✅ |
| P7 | Prompt | No input(), marker letterale | ✅ |
| P8 | Skill | Drain sicuro (iteratore unico, no loop infinito) | ✅ |
| P9 | Skill | Context manager: self. esplicito | ✅ |
| P10 | Skill | py-decorator ripristinato a timing-only | ✅ |
| P11 | Skill | py-argparse: template concreto con subparser | ✅ |
| P12 | Skill | py-unittest: blocco __main__ concreto | ✅ |
| P13 | Skill | py-expr-eval (nuova skill) | ✅ |
| P14 | Gate | Marker con valore-variabile (TENTATIVO=n) | ✅ |
| P15 | Skill | py-arch-decision (decision tree + template) | ✅ |

## 9. Miglioramenti Fase 8 (A–G)

| # | Area | Descrizione | Stato |
|---|---|---|---|
| A1 | Validazione | Oracle test in verify_runtime | ✅ |
| A2 | Validazione | Diff semantico (snapshot pre/post) | ✅ |
| D1 | Diagnosi | Suggerimento riga da aggiungere per marker mancante | ✅ |
| C1 | Decomposizione | Atomizzatore moduli (decompose_module) | ✅ |
| C2 | Decomposizione | Ordine topologico (dependency_order) | ✅ |
| B2-B5 | Skill | 4 nuove skill di trasformazione | ✅ |
| E1-E2 | Prompt | System prompt compatto + skill on-demand | ✅ |
| F1-F2 | Memoria | Compaction intelligente + contesto per modulo | ✅ |
| G1-G2 | M8 | Skill suggerite con template + auto-approvazione | ✅ |

## 10. Configurazione modelli

| Modello | Ruolo | Timeout | Stato |
|---|---|---|---|
| qwen2.5-coder:3b | Base (titolare) | 300s (default) | ✅ 10/10 suite base, 11/11 complessa |
| granite4:7b-a1b-h | Heavy (complessità alta) | 600s | ✅ 10/10 suite, e2e routing PASS |
| kirito1/qwen3-coder:4b | Candidato heavy (scartato) | 600s | ❌ 4/10 (×19 più lento, timeout) |

---

*Report generato automaticamente da `scripts/generate_report.py`*