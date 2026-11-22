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

## Regola termica: mini-task stadiali (🆕 Cycle 65)

I task dei benchmark futuri si progettano a STADI brevi, non come
generazioni monolitiche — il portatile surriscalda sotto carico LLM
continuo (limite utente: 60°C, mai di più):

1. **Scheletro** — chiedere SOLO la struttura vuota (classe vuota,
   firme dei metodi, funzioni `test_*` con `pass`). Generazione breve
   (~150-250 token).
2. **Verifica host-side** tra gli stadi: `py_compile` /
   `pytest --collect-only` — gratis (zero LLM). Scova subito gli errori
   di import e di struttura, il guasto più comune su modelli 3B, senza
   pagare le generazioni successive.
3. **Definizioni/corpi** — riempire SOLO i corpi mantenendo la struttura
   verificata. Generazione breve (~300-500 token).
4. **Implementazione completa**: mai in un'unica generazione lunga;
   se serve, è l'ultimo stadio, dopo che la struttura è già verificata.

Nel runner del benchmark: un task = uno stadio, con `--cooldown 30
--thermal-limit 60` tra task (già implementato in `external_benchmark.py`,
flag `thermal_abort` su superamento). Se la temperatura sale comunque,
ridurre i task (2-3), aumentare il cooldown (60s), abbassare il limite
(55°C) o cambiare macchina.

Implementazione di riferimento della regola in codice:
`CORE/test_generator.py` (stadio scheletro → collect-check → stadio corpi).

---

## 🎯 PIANO D'AZIONE — Cycle 66 (dati attuali, pre-driver) ⏳ LIVING DOC

> **Nota d'uso**: questo piano è scritto SUI DATI ATTUALI e va AGGIORNATO
> al termine del driver delle sessioni fredde (`tools/bench_cold_sessions.py`,
> log `/tmp/opencode/bench_cold_sessions.txt`). I campi `⏳` sono i
> segnaposto da riempire. Niente feature nuove prima: measure, don't add.

### 1. Dati certi a oggi (misurati, non ipotesi)

**Baseline benchmark (Cycle 59)** — stessa macchina, stessi 8 task:

| metrica | harness (correction loop) | naked | delta |
|---------|---------------------------|-------|-------|
| successo 1° colpo | 12.5% (1/8) | 50% (4/8) | **naked vince** |
| wall medio/task | ~192s | ~14s | **13× più lento** |

→ L'harness COM'ERA era un costo puro: il correction loop scalda 3× per
arrivare a meno successi. Da qui la fast lane (single-shot, max 2 tentativi)
e la decisione "deterministico prima, LLM come riserva".

**Fisica termica (Cycle 66, limite utente 60°C DURO)**:

| condizione | misura | conseguenza operativa |
|------------|--------|----------------------|
| idle fredda | 44°C | finestra di partenza utile: 44-46°C |
| salita da freddo | 49→78°C in 107s (~0,3°C/s) | segmenti continui ≤ ~35s |
| salita da caldo | 51→75°C in 21s (~1°C/s) | NESSUN segmento riparte da caldo |
| pausa adattiva | 78→51°C in 90s | funziona, ma 51°C non basta per ripartire |

→ **Regola operativa**: ogni sessione di benchmark parte da macchina
fredda (≤45.5°C); nessun carico LLM oltre 60°C; mai due sessioni di fila
senza raffreddamento naturale. Benchmark completo in una sessione:
IMPOSSIBILE su questo hardware (2/2 aborti confermati).

**Hardware e modelli**:
- 4GB RAM → qwen2.5-coder:7b (4.7GB) NON entra; swap = morte termica
- unico candidato "LLM potente" locale: `granite4:7b-a1b-h` (MoE, ~1B
  parametri attivi, 4.2GB) → FASE 4
- fast lane: implementata, elegibilità fixata (8/8 task elegibili,
  chiave `file` autorevole), **`enabled = false` finché non validata**

### 2. Decisione presa (utente, Cycle 66)

**Opzione A: sessioni fredde** — 1 task per sessione, driver automatico
aspetta ≤45.5°C prima di ogni sessione, 60°C mai sforato. Utente: la
fast lane "è di un'utilità disarmante" → va validata a tutti i costi
termici, non aggirata alzando il cap.

### 3. Stato attuale del piano

| FASE | cosa | stato |
|------|------|-------|
| 0 | driver 8 sessioni fredde ext-01..08 in background | ✅ **CHIUSO con verdetto §8** (2/8 fatte, stop definitivo utente) |
| 1 | tabella 8 task fast lane vs naked + verdetto | ✅ **FATTO** (tabella compilata 2/8, verdetto §8: fast lane NON validata → OFF) |
| 2 | `temp_before`/`temp_after` per fase nel JSON benchmark | [x] **FATTO Cycle 66 parte 3** (in entrambi i runner, ogni sessione registra i propri picchi) |
| 3 | micro-ciclo config: `num_ctx` planner 3072→2048, toggle Timestral/SystemMonitor, `keep_alive_sec` | [ ] config-only, zero Ollama → **prossimo lavoro** |
| 4 | benchmark granite4:7b-a1b-h, regola stadiale, stesso protocollo sessioni fredde | ⛔ **BLOCCATO dallo stesso muro termico** (60°C sforato nelle fasi) — solo con cap di frequenza (sudo) o altra macchina |
| 5 | architettura 3 modelli (vedi §5) | decision deterministico-first resta la direzione; implementazione locale non validata |

### 4. Criteri di verdetto PRE-SCRITTI (l'aggiornamento sarà meccanico)

Al termine del driver si compila la tabella ⏳ e si applica la PRIMA
regola verificata (ordine = priorità):

| # | condizione (su 8 task) | verdetto `fast_lane.enabled` |
|---|------------------------|------------------------------|
| 1 | ≥40% 1° colpo E <60s/task medio | `true` → subito FASE 2 |
| 2 | ≥40% ma ≥60s/task | `true` + FASE 3 ottimizzazione (keep_alive KV cache) |
| 3 | <40% MA ≥ naked (50%) su qualche metrica | resta `false`, analisi prompt fast lane, 1 retry |
| 4 | < naked | resta `false` DEFINITIVO, fast lane archiviata (risultato onesto) |
| 5 | >2 sessioni in thermal abort | protocollo rivisto: cold start 45°C, resume-offset 16 |

Tabella da compilare ⏳ — **COMPILATA con i dati reali (verdetto §8)**:

| task | fast lane 1° colpo | wall | naked 1° colpo | wall | temp picco |
|------|--------------------|------|----------------|------|------------|
| ext-01 | NO (fallback loop, attempts=3) | 95.25s | SKIPPED (max wait 900s scaduto) | - | 79.0°C |
| ext-02 | NO (fallback loop, attempts=3) | 94.19s | NO | 21.41s | 80.0°C |
| ext-03..08 | — sessioni mai eseguite (utente: stop definitivo) — | | | | |

## 8. VERDETTO FINALE — fast lane NON validata (🆕 Cycle 66 chiusura)

**Decisione utente (16/11/2026 ~13:10): stop definitivo del benchmark
su questo hardware.** Ragioni misurate, non opinioni:

1. **Il limite 60°C è inviolabile e i picchi lo sforano sempre**:
   79-80°C durante le fasi anche con `num_thread=2` — su i7-7700HQ il
   turbo compensa (meno thread = frequenza per core più alta = stessa
   potenza, pendenza 0,27-0,29°C/s INVARIATA). L'unica leva reale è il
   cap di frequenza (sudo) o altra macchina: leve non disponibili ora.
2. **Fast lane 0/2 con fallback al correction loop** (attempts=3):
   campione insufficiente per un verdetto statistico, MA zero successi
   primo colpo — nessuna evidenza pro.
3. **Costo tempo**: ~21-23 min/sessione (dominati dalle attese di
   raffreddamento al mezzogiorno), 8 sessioni ≈ 3h+ per un campione
   minimo, con est-01 naked perso (max wait 900s).

**Esito**: `fast_lane.enabled = false` (rollback permanente finché non
cambino le condizioni: cap di frequenza, altra macchina, o giornata
fresca). Regola "measure, don't add" rispettata: l'idea
"deterministico-first" della FASE 5 resta la direzione, ma questa
implementazione locale non è validata — NON si usa in produzione.

**Cosa resta di utile** (non buttato):
- `temp_before`/`temp_after` per fase nel JSON: ogni sessione registra
  i propri picchi (strumento attivo per qualunque test futuro)
- Pausa termica adattiva + fisica documentata (0,27-0,29°C/s sotto
  load LLM su questa CPU, turbo compreso)
- `tools/bench_cold_sessions.py` + `tools/progress_reporter.py`
  riusabili per il prossimo tentativo (cap di frequenza / altra macchina)
- Dati parziali in `state/benchmarks/` (baseline harness-completo
  est-01/02 delle 11:xx + fast lane fallback est-01/02 delle 12:xx)

### 5. Architettura 3 modelli (direzione confermata dall'utente)

| ruolo utente | implementazione attuale | prossima mossa |
|--------------|------------------------|----------------|
| **1. Timestral** — controllo termico in loop | `thermal_manager` (gate reattivo + history 662KB) + `llm_tuner` (parametri ridotti da caldo) | già suono e a costo 0; ⏳ opzione: farlo campionare ANCHE durante i benchmark (ora il benchmark bypassa l'orchestrator e la sua history si ferma) |
| **2. Decision model** — divide i problemi | planner 1.5b, atomizer, risk classifier, euristica elegibilità fast lane | deterministico-FIRST: l'euristica a costo ~0 decide, l'LLM di decisione resta riserva. È già la direzione presa |
| **3. LLM potente** — implementazione | worker_coder 3b, escalation 4b | FASE 4: granite4 MoE. Se insufficiente → vertice mancante: esecutore REMOTO via API (il calore lo fa altro silicio); costo: internet/soldi — decisione utente |

### 6. Cosa NON fare (vincoli permanenti)

- Mai sopra 60°C. Nessuna eccezione, nemmeno per finire un benchmark.
- Mai generazioni LLM monolitiche: stadi brevi con verifica host-side.
- Nessuna feature nuova non misurata; `enabled = false` finché valido.
- Nessun lavoro CPU-heavy mentre il driver gira (inquinerebbe le misure).

### 7. CorrezioneCycle 66 parte 3 — cosa è cambiato prima del rilancio

Le prime 2 sessioni (ext-01, ext-02) hanno evidenziato 2 problemi:

1. **Fast lane era OFF nel driver** (rollback fatto prima del lancio →
   il driver ha ereditato `enabled=false` e ha girato il correction
   loop completo: wall 190s/117s, attempts=3). Le 2 sessioni valgono
   come baseline "harness completo" ma NON misurano la fast lane.
2. **La fisica reale è più severa del previsto**: la generazione LLM
   scalda ~1°C/s da QUALSIASI partenza (il dato 0,3°C/s includeva il
   setup). Anche da 46°C freddi, un naked di 14-21s → 65-66°C, e il
   correction loop → 78-82°C. Il limite 60°C veniva sforato DURANTE
   i task (la guardia ferma solo dopo).

**Fix prima del rilancio (opzione confermata dall'utente)**:
- `num_thread = 2` iniettato SOLO in memoria per il benchmark
  (CLI `--num-thread`, config.toml intatto): ~metà del calore,
  inferenza più lenta ma sotto i 60°C. Stessa condizione per fast
  lane e naked → confronto equo.
- `fast_lane.enabled = true` (per la validazione).
- `temp_before`/`temp_after` per fase nel JSON (verifica empirica del
  fix: se una sessione supera 60°C, si vede subito e si abbassa a 1).
- Le prime 2 sessioni restano nei JSON come baseline harness-completo.

---

## Robustezza #8 — pytest-xdist (verdetto: NO-GO per la suite completa, 2026-11-18)

- **Baseline (non-Qt subset, 78 test)**: -n1 1.5s · -n2 1.4s · -n4 1.4s
  (speedup ~0: i test sono troppo veloci per beneficiare del parallelismo).
- **Instabilità**: `TestClarificationDialogSmoke::test_dialog_creation` (Qt
  QApplication per worker) crasha sotto xdist (worker crash) con -n2/-n4.
  Confermato in 3 run consecutivi.
- **Verdetto: NO-GO** per la suite completa (fail-open onesto, come da
  criterio). Il parallelismo non porta beneficio misurabile e instabilizza
  i test Qt. Mantenere `pytest` seriale per la suite intera.
- **Uso ammesso**: sottoinsieme puramente non-Qt (es. i nuovi test
  deterministici) con `-n 2/4` per feedback rapido in sviluppo, mai in CI
  sulla suite completa.

---

## Fedeltà API (E2) — Cycle 97, verdetto deterministico (2026-11-22)

| Metrica | Valore |
|---|---:|
| Librerie fuori cheat sheet | `json`, `csv` (2) |
| Simboli usati negli eval case | 7 (`dumps`, `loads`, `JSONEncoder`, `reader`, `DictWriter`, `QUOTE_MINIMAL`, `excel`) |
| Simboli verificati con `api_lookup(strict=True)` | 7/7 |
| **Simboli indefiniti** | **0** |
| Ref generati e validati | 2 (`GUI/refs/json_api.md`, `GUI/refs/csv_api.md`) |
| Firme confrontate via `inspect.signature` | 22 (8 + 14), 0 discrepanze |
| Test | 8 offline, zero LLM/rete/GPU |

Comando: `.venv/bin/python tools/api_fidelity_eval.py --out DOCS/API_FIDELITY_REPORT.md`
(exit 0 = PASS). Nota: `strict=True` ora verifica le costanti reali come
valori (`csv.QUOTE_MINIMAL`) senza accettare simboli inventati; i callabili
con firma non introspettabile restano bloccati. Nessuna misura live: il
verdetto riguarda la fedeltà delle API, non la qualità delle risposte LLM.

---

## Scaffolding GUI (E3) — Cycle 98, struttura verificata (2026-11-22)

| Metrica | Valore |
|---|---:|
| Template PyQt6 curati | 4 (`finestra`, `layout`, `segnali`, `thread`) |
| Snapshot offscreen | 4 (titolo/dimensioni, gerarchia layout, segnali, thread) |
| Test E3 | 7 (6 template/GUI + 1 skill/keyword), zero LLM/rete/GPU |
| Task GUI chiusi al primo colpo con LLM | non misurato — 🔒 ventole da verificare (≤60 °C) |

Nota: `api_lookup(strict=True)` blocca le classi C++ di PyQt6 (firme non
introspettabili); per i simboli Qt la verifica deterministica è `api_lookup`
senza `strict` (esistenza) + `GUI/refs/pyqt6.md`. Il passaggio da 2/4 a 3/4
dell'asse Task GUI richiede un task reale con modello, non questo gate.

---

## Memoria/contesto (E4) — Cycle 99, harness pronto (2026-11-22)

| Parametro | Valore |
|---|---|
| Task set congelato | `5e6051bfc33d` — 10 task, 8 con contesto utile, 2 senza |
| Bracci | `with_context` vs `without_context`, stesso solver e stesso task set |
| Soglia GO | tasso with ≥ **0.60** e delta ≥ **0.20** |
| Soglia NO-GO | delta ≤ 0 |
| Esito dry-run | solver finto: 0.80 vs 0.00 — **simulazione, non verdetto reale** |
| Test | 8 offline, zero LLM/rete/GPU |
| Esecuzione live | 🔒 bloccata: serve `data/state/fan_verified.json` con `fan_rpm > 0` e `temp_c <= 60` |

Comando di preparazione: `.venv/bin/python tools/memory_ab.py --dry-run --out
DOCS/MEMORY_AB_REPORT.md`. Le soglie sono state scritte **prima** di qualsiasi
run live: il passaggio di Memoria/contesto da 3/4 a 4/4 richiede il verdetto
reale sui 10 task, non il dry-run.

---

## Varianti prompt (Fase G) — Cycle 116, harness pronto (2026-11-22)

| Parametro | Valore |
|---|---|
| Strumento | `tools/eval_prompt_variants.py` + `tests/test_prompt_variants.py` (9 test) |
| Varianti | `baseline`, `refs_off`, `refs_first`, `plan_compact` |
| Task set congelato | `182ae2a82284` — 11 casi della eval suite con `expected_marker` |
| Regola PROMOTE | tasso ≥ **0.60** e delta ≥ **0.20** rispetto a baseline |
| Regola REJECT | delta ≤ 0 |
| Esito dry-run | `refs_off` REJECT, `refs_first`/`plan_compact` INCONCLUSIVE — **simulazione, nessuna promozione** |
| Report | `DOCS/PROMPT_VARIANTS_REPORT.md` (rigenerato dal tool, non scritto a mano) |
| Esecuzione live | 🔒 bloccata: serve `fan_verified.json` (`fan_rpm > 0`, `temp_c ≤ 60`) e un solver reale passato dal chiamante |

Il solver del dry-run assegna l'HINT per hash del `case_id`: serve solo a
esercitare le diramazioni della regola, **non** è una misura di qualità. Nessun
prompt viene promosso finché non arriva un esperimento reale con gate termico.

---

## Eval per-slot (SLOT-5) — Cycle 117, reporter pronto (2026-11-22)

| Parametro | Valore |
|---|---|
| Strumento | `tools/eval_by_slot.py` + `tests/test_eval_by_slot.py` (9 test) |
| Casi classificati | 11 con `expected_marker`; 2 casi gate/chiarimento esclusi (pass@1 non applicabile) |
| Tipi slot | `function`, `method`, `handler`, `widget`, `import`, `class`, `statement` |
| Dimensioni | small 0-40, medium 41-120, large 121+ righe |
| Accettazione risultati live | Richiede `source: "live"` **e** `fan_rpm > 0`, `temp_c ≤ 60`; altrimenti exit 2 |
| Esito dry-run | tabelle per slot e per dimensione da hash del `case_id` — **simulazione, non misura** |
| Report | `DOCS/SLOT5_EVAL_REPORT.md` (rigenerato dal tool) |
| Criterio done | 🔒 incompleto: servono 12+ casi reali con modello e ventole verificate |

Il reporter rifiuta `case_id` sconosciuti/duplicati, `slot_kind` non ammessi e
qualsiasi `source` diverso da `live`/`simulation`. Nessun asse del radar viene
alzato: SLOT-5 resta `[~]` finché la tabella non contiene dati misurati.

---

## Distill occasionale (Fase E) — Cycle 118, tool pronto (2026-11-22)

| Parametro | Valore |
|---|---|
| Strumento | `tools/distill_task.py` + `tests/test_distill_task.py` (10 test) |
| Gate deterministici | file leggibile, ≤ 200 righe, AST valido, pyflakes 0, security_scan 0 errori, `expected_marker` presente |
| Scrittura | `--commit` richiede `fan_verified.json` (`fan_rpm > 0`, `temp_c ≤ 60`), modello dichiarato e dedup per contenuto |
| Corpus | `state/feedback_corpus/<task>.jsonl`, tripla `verdict=done`, `ts=0.0` (nessun timestamp inventato) |
| Esempi reali | **0** — 🔒 servono ≥3 soluzioni da modello 7b/14b con gate termico |
| Stato | `[~]`: tool verificato, criterio done incompleto |

Il tool NON esegue il modello più grande: riceve una soluzione già prodotta
esternamente e la rifiuta se anche uno solo dei sei gate fallisce. Le soluzioni
dei test sono file sintetici e non entrano nel corpus versionato.

---

## Prompt per-slot (SLOT-4) — Cycle 119, builder pronto (2026-11-22)

| Parametro | Valore |
|---|---|
| Strumento | `tools/slot_prompt.py` + `tests/test_slot_prompt.py` (9 test) |
| Input | `SlotPlan` deterministico da `CORE/slot_planner.py` (già lockato da SLOT-3) |
| Output | Un prompt per chiamata: sole refs dello slot corrente, anchor reale del template, regole di output ≤40 righe |
| Fail-closed | Piani rifiutati dal planner non generano prompt; indice slot fuori range → errore |
| Onestà | Nessun client LLM; il report dichiara che il benchmark reale resta 🔒 termico |
| Esempio | `DOCS/SLOT4_PROMPTS.md` (task "finestra con titolo", 2 slot) generato dal tool |
| Stato | `[~]`: struttura dei prompt verificata; 🔒 restano 3 task reali misurati con pass@1 |

Il builder cambia **solo il prompt**, non il motore: ogni chiamata vede le ref
del proprio slot e l'anchor del template, senza le ref degli altri slot. Nessun
modello è stato invocato: il pass@1 per tipo di slot richiede il benchmark live
con ventole verificate.
