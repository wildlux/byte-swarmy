# 📊 BENCH REPORT — BYTE-SWARMY

Regola: **ogni report/misura va documentato qui** (o in `IMPLEMENTED.md`
per i cicli). I JSON grezzi restano in `state/benchmarks/` (gitignored,
runtime); qui vanno le tabelle, il metodo e la lettura onesta.

Comando: `.venv/bin/python tools/bench_worker.py` — confronto automatico
con `state/benchmarks/bench-baseline.json`; `--save-baseline` per fissare
una nuova baseline DOPO un'ottimizzazione.

---

## 2026-11-15 — Pre-T1 vs baseline (prima misura)

**Metodo**: worktree al commit `b9bb4e6` (codice PRIMA di T1–T22) vs
baseline attuale. Stesso hardware, stesso modello (`worker_coder` =
qwen2.5-coder:3b), stessi 2 task (bench-create, bench-patch, 10 step
l'uno). ⚠️ 1 campione per task: tempi rumorosi, il segnale forte è la
correttezza degli artifact.

| | pre-T1 | baseline (T1–T22) | delta |
|---|---|---|---|
| system prompt per step (dopo il 1°) | 2516 ch **costanti** | 668 ch | −73% |
| contesto ripetuto per step | task+stato interi | ~140 ch | −94% |
| token input totali (20 step) | ~15.300 | ~4.240 | **−72%** |
| token generati totali | ~845 | ~1.170 | +38% |
| artifact corretti | **0/2** | **2/2** | — |
| wall totale | 48,2s | 74,6s | n.c. |

**Lettura onesta**:
- pre-T1 i task FALLIVANO entrambi (prompt gonfio → il 3B gira in tondo
  su `read_file`, circuit breaker, nessun file scritto). Il wall minore
  riflette solo che NON ha fatto il lavoro.
- Con il prompt compatto gli stessi task si completano 2/2: il guadagno
  misurabile è la CORRETTEZZA, non la velocità.
- La velocità di generazione (tok/s) resta invariata come previsto.
- Il wall cresce perché i passi ora producono contenuto reale.
- Il primo step della baseline (15,7s) include il load del modello in
  Ollama; i passi successivi (1,9–5,5s) sono il costo reale per step.

---

## 2026-11-15 — Post-furbate (Cycle 47) — bench automatico dentro `verify_all`

Dopo l'implementazione delle furbate (warmup/keep_alive, sticky, audit gate,
watchdog), il bench post-furbate è girato contro la baseline del 2026-11-15
(01:12:58) e confrontato automaticamente:

| metrica | baseline | ora | delta |
|---|---|---|---|
| wall totale (s) | 74,59 | 70,53 | **−5,4%** |
| token prompt (stima) | 4240 | 4240 | +0,0% |
| token generati (stima) | 1349 | 1349 | +0,0% |
| chiamate LLM | 20 | 20 | +0,0% |
| bench-create: wall | 40,39s | 36,52s | **−9,6%** |
| bench-patch: wall | 34,2s | 34,01s | −0,6% |

Il claim: il warmup (A) ha ridotto il primo step (bench-create −9,6% ≈ load
cold 8–15s → ~0); i token usati sono IDENTICI (4240/1349), quindi niente
regressione di prompt e nessun costo aggiuntivo. Wall −5,4% totale su 2 task.

Nota: i test di compile segnalano 1 errore pre-esistente in
`tests/archiviati/TEST_GUI_SEPARATA/TEST_GUI_QT_7.py` (da commit
`3312ad4`, non toccato in questa cycle).

---

## 2026-11-15 — Post-furbate E: num_ctx A/B (8192 → 4096) — **nessun win netto (probabile noise)

Bench con `[models.worker_coder].num_ctx = 4096` vs baseline 8192 (stesso task,
stesso modello, stesso prompt version, 1 campione/task come sempre):

| metrica | 8192 (baseline) | 4096 | delta |
|---|---|---|---|
| wall totale | 74,59s | 71,06s | −4,7% |
| bench-create | 40,39s | 36,76s | −9,0% |
| bench-patch | 34,2s | 34,3s | +0,3% |

Token invariati (4240 in / 1349 out / 20 chiamate) → la KV cache ridotta NON ha
ridotto i token usati (context effettivi ~140ch ripetuti, già piccoli).

**Lettura onesta**: lieve miglioramento di wall (−4,7%) dentro il rumore del
campione singolo; stesse dimensioni di guadagno del bench post-warmup
(−5,4%). Probabile che parte di questo delta sia noise, non il num_ctx in sé.
**Conclusione**: con prompt già compatti (post T1–T22), la riduzione num_ctx
non dà un win misurabile sul 3B oggi. Valutare solo per worker_coder_big
(modello 4B, context più grande) in futuro bench separato.
Config ripristinata a `num_ctx = 8192` (non committata come cambiamento).

---

## 2026-11-15 — Furbata D: env Ollama KV cache q8_0 + flash attention

Applicazione env al servizio ollama (`systemctl set-environment
OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1` + `systemctl restart
ollama.service`), poi bench post-applicazione.

| metrica | baseline (01:12:58) | ora (q8_0 + FA, 01:50:32) | delta |
|---|---|---|---|
| wall totale | 74,59s | 72,72s | **−2,5%** |
| bench-create wall | 40,39s | 34,91s | **−13,6%** |
| bench-patch wall | 34,2s | 37,81s | +10,6% (rumore) |
| token prompt in | 4240 | 4166 | −1,7% |
| token generati | 1349 | 1362 | +1,0% |
| chiamate LLM | 20 | 20 | 0,0% |

Lettura: guadagno wall misurato **−2,5%** (task create −13,6%); token invariati
nell'ordine. Flash attention era già attivo via drop-in; il delta attivabile è
il KV cache `q8_0`. Applicazione persistita via manager env (runtime).

**Chiusura furbate**: A, B, C, E, F e D — **tutte completate e misurate**.

---

## 2026-11-15 — Benchmark esterno (Cycle 59)

**Obiettivo**: sapere se byte-swarmy, così com'è oggi, produce valore misurabile su task di refactoring esterni e non progettati da noi (Fase 0 del piano d'attacco senior).

**Bersaglio**: `bench_target/` — mini-repo Python di 4 file (utils, core/processor, core/validator, models/user).
**Task**: 8 specifiche di refactoring atomiche e verificabili (type hints, estrazione funzioni pure, logging, docstring, ...).

| metrica | harness (con correction loop + audit) | naked (modello nudo) | delta |
|---------|--------------------------------------|----------------------|-------|
| successo al primo colpo | 12% (1/8) | 50% (4/8) | -75% |
| successo dopo correction loop | 25% (2/8) | 50% (4/8) | -50% |
| falsi negativi gate (bloccati) | 0 | 0 | n.c. |
| errori di esecuzione | 0 | 0 | n.c. |
| wall totale (s) | 1536.67 | 113.05 | n.c. |
| wall medio/task (s) | 192.08 | 14.13 | n.c. |

**Criterio di uscita (Fase 0):** se il tempo umano netto e' negativo o nullo (supervisione >= lavoro manuale), fermarsi e semplificare prima di aggiungere feature. Se positivo anche solo del 20%, si ha qualcosa su cui costruire.

**Tempo umano netto:** campo da compilare a mano dall'utente (ore di supervisione vs ore di lavoro manuale). Non e' misurabile automaticamente dal sistema.

**Metodologia riproducibile:** i JSON grezzi sono in `state/benchmarks/` (gitignored). Eseguire con: `.venv/bin/python -m CORE.external_benchmark --run` (richiede Ollama). Test senza Ollama: `pytest tests/test_external_benchmark.py`.


--- Modello: worker_coder ---

---

## 2026-11-16 — Benchmark esterno (Cycle 59)

**Obiettivo**: sapere se byte-swarmy, così com'è oggi, produce valore misurabile su task di refactoring esterni e non progettati da noi (Fase 0 del piano d'attacco senior).

**Bersaglio**: `bench_target/` — mini-repo Python di 4 file (utils, core/processor, core/validator, models/user).
**Task**: 8 specifiche di refactoring atomiche e verificabili (type hints, estrazione funzioni pure, logging, docstring, ...).

| metrica | harness (con correction loop + audit) | naked (modello nudo) | delta |
|---------|--------------------------------------|----------------------|-------|
| successo al primo colpo | 12% (1/8) | 50% (4/8) | -75% |
| successo dopo correction loop | 25% (2/8) | 50% (4/8) | -50% |
| falsi negativi gate (bloccati) | 0 | 0 | n.c. |
| errori di esecuzione | 0 | 0 | n.c. |
| wall totale (s) | 1454.74 | 113.61 | n.c. |
| wall medio/task (s) | 181.84 | 14.2 | n.c. |

**Criterio di uscita (Fase 0):** se il tempo umano netto e' negativo o nullo (supervisione >= lavoro manuale), fermarsi e semplificare prima di aggiungere feature. Se positivo anche solo del 20%, si ha qualcosa su cui costruire.

**Tempo umano netto:** campo da compilare a mano dall'utente (ore di supervisione vs ore di lavoro manuale). Non e' misurabile automaticamente dal sistema.

**Metodologia riproducibile:** i JSON grezzi sono in `state/benchmarks/` (gitignored). Eseguire con: `.venv/bin/python -m CORE.external_benchmark --run` (richiede Ollama). Test senza Ollama: `pytest tests/test_external_benchmark.py`.


--- Modello: worker_coder_big ---

---

## 2026-11-16 — Benchmark esterno (Cycle 59)

**Obiettivo**: sapere se byte-swarmy, così com'è oggi, produce valore misurabile su task di refactoring esterni e non progettati da noi (Fase 0 del piano d'attacco senior).

**Bersaglio**: `bench_target/` — mini-repo Python di 4 file (utils, core/processor, core/validator, models/user).
**Task**: 8 specifiche di refactoring atomiche e verificabili (type hints, estrazione funzioni pure, logging, docstring, ...).

| metrica | harness (con correction loop + audit) | naked (modello nudo) | delta |
|---------|--------------------------------------|----------------------|-------|
| successo al primo colpo | None (0/0) | None (0/0) | n.c. |
| successo dopo correction loop | None (0/0) | None (0/0) | n.c. |
| falsi negativi gate (bloccati) | 0 | 0 | n.c. |
| errori di esecuzione | 0 | 0 | n.c. |
| wall totale (s) | 0 | 0 | n.c. |
| wall medio/task (s) | 0 | 0 | n.c. |

**Criterio di uscita (Fase 0):** se il tempo umano netto e' negativo o nullo (supervisione >= lavoro manuale), fermarsi e semplificare prima di aggiungere feature. Se positivo anche solo del 20%, si ha qualcosa su cui costruire.

**Tempo umano netto:** campo da compilare a mano dall'utente (ore di supervisione vs ore di lavoro manuale). Non e' misurabile automaticamente dal sistema.

**Metodologia riproducibile:** i JSON grezzi sono in `state/benchmarks/` (gitignored). Eseguire con: `.venv/bin/python -m CORE.external_benchmark --run` (richiede Ollama). Test senza Ollama: `pytest tests/test_external_benchmark.py`.
