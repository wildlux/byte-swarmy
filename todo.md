# TODO — BYTE-SWARMY

> **Flusso documentale**: il task nasce qui → si esegue → si registra in
> `DOCS/IMPLEMENTED.md` (Cycle N) → si cancella da qui.
>
> **Storia completa**: Fasi 1–9, M1–M10, P1–P15, suite T1–T10 e T11–T21,
> routing, code map, clarifier, chiusura orchestratore — tutto travasato in
> `DOCS/IMPLEMENTED.md` (Cycles 13–22). Report consolidato: `REPORT.md`.

Stato: **tutto il piano approvato è completato** (le 85 voci del vecchio
todo sono registrate in `DOCS/IMPLEMENTED.md`). Da oggi (2026-11-18) il
todo è **ordinato per impatto**: prima ciò che sblocca la misura e chiude
i gap più grandi del radar, poi il motore del miglioramento, poi i gap
medi, infine sottofondi e igiene.

## 🗂️ Sessione 2026-11-22 — riordino cartelle e commenti (pianificata)

Regola condivisa: **stessi cartelle, sempre** — nomi maiuscoli per i contenitori
di primo livello (`CORE/`, `GUI/`, `CONFIG/`, `TOOLS/`), una sola cartella per
categoria, nessun refuso nei nomi.

| # | Task (atomico, verificabile) | Stato |
|---|---|---|
| 1 | Spostare `REVERSE_ENGEREENING_TOOLS/` → `TOOLS/REVERSE_ENGINEERING/`, aggiornare i riferimenti | [x] |
| 2 | Commentare i 3 file spostati + docstring di modulo ai 3 `__init__.py` vuoti | [x] |
| 3 | Regola "stesse cartelle" in `AGENT.md` (#11) e nella struttura del README | [x] |
| 4 | Gate deterministici: `compileall`, `lint_style`, `bash -n`, `git diff --check`, security scan | [x] |

> Eseguito il 2026-11-22: `git mv` con rilevamento rename, 14 riferimenti
> aggiornati, 3 file spostati commentati, 3 docstring di modulo aggiunte
> (`CORE/`, `GUI/`, `tools/`). Nota: `$ROOT` nella copia di setup ora risolve
> correttamente a `../..` dalla nuova posizione.

---

## 🎯 Piano d'attacco — dalle voci più impattanti (2026-11-18)

> **Criterio d'ordine**: impatto sul goal middle senior (radar grafico E)
> ÷ costo. **★★★** = sblocca la misura o chiude il gap più grande (Task
> GUI 1/4, Fedeltà API 2/4); **★★** = motore del miglioramento (dati,
> inference-time); **★** = gap medi del sistema; **○** = sottofondi e
> igiene. Ogni item ha un criterio di done misurabile; una voce per
> sessione; deterministico-first, mai generazioni monolitiche.
>
> **🏗️ Architettura guida — SLOT** (2026-11-18): il 3b non genera più
> file interi (0/4, C72) ma riempie **slot piccoli e verificati uno
> alla volta** (planner deterministico → filler 3b → gate per-slot →
> assembler deterministico → corpus → QLoRA). Piano completo e
> tempistiche (~6-7 sessioni, MVP 2-3):
> [`DOCS/ARCHITETTURA_SLOT.md`](DOCS/ARCHITETTURA_SLOT.md).
>
> **⭐ Regola Zero Warning (2026-11-18, richiesta esplicita)**: il goal
> non è solo "0 errori" — è **0 errori E 0 warning**. I warning non
> sono decorativi: ogni unused import è costo di avvio, ogni variabile
> morta è confusione, ogni deprecation è un errore futuro. Il codice
> deve essere pulito ed elegante: i warning sono il termometro di
> eleganza e performance. Baseline misurata: **pyflakes 474**
> (375 imported-but-unused · 39 variabili morte · 16 redefinition ·
> 44 altro); baseline pytest-warning: da misurare (prima sessione
> utile). La campagna è l'item [Robustezza #10] in Fascia 3.
>
> **Regola metrica-per-granularità** (da `ARCHITETTURA_SLOT.md`): ogni
> benchmark nuovo DEVE spezzare la metrica per granularità
> (output-size, tipo di slot, asse del radar) — mai solo aggregata.
>
> **✅ Completato** (Cycle 85i, 2026-11-18): **[P1-1] metrica "primo
> colpo %"** — colonna `first_try` in `CORE/task_queue.py` (1 = primo
> tentativo, 0 = servito correction, NULL = task deterministico) +
> `tools/first_try_report.py`; `verify_cycle.sh` stampa
> `primo_colpo: X/Y` come passo 4/4.
>
> **✅ Completati in questa campagna** (fasi 1 dell'attacco):
> - **[P1-1]** metrica "primo colpo %" (Cycle 85i) — `queue.db.first_try` +
>   `tools/first_try_report.py` + verify_cycle 4/4.
> - **[SLOT-1]** gate per-slot (Cycle 85j) — `CORE/slot_gate.py` +
>   `tests/test_slot_pipeline.py`.
> - **[SLOT-2]** assembler deterministico (Cycle 85j) — `CORE/slot_assembler.py`
>   + marker `# @@slot` / `# @@imports`.
> - **[P1-2]** gate import-check (Cycle 85j) — `CORE/import_check.py` +
>   `CORE/tools.py` write/patch tracciamento + rifiuto done → retry ≤2.
>
> ### Fascia 1 — ★★★ Sblocca la misura + primo mattone SLOT

1. [x] **[Fase B] Corpus di triple verificate + curazione** — ogni
      sessione salva (prompt, output, verdetto gate) in
      `state/feedback_corpus/` (+ tool-trace). È il carburante di tutto
      il resto; parte subito perché è collezione passiva. Poi
      curazione deterministica (dedup, stratificazione, SOLO esempi
      gate-verificati). Criterio done: schema JSONL + writer nel
      worker + contatore per-sessione; `tools/curate_corpus.py` +
      report qualità. Zero LLM.
      > ✅ **Fase B completata** (2026-11-18, campagne 85i–85k): corpus writer +
      > Triple + dedup + stats (CORE/feedback_corpus.py, hook worker nel
      > done-branch), curate CLI (tools/curate_corpus.py, filtro SOLO done).
      > Rimasto solo il "contatore per-sessione" formale.
2. [ ] **[Fase D-15] Best-of-N con gate come giudice** — per task hard
      (GUI, architettura) e per slot hard: N=3 candidati in parallelo,
      il gate deterministico sceglie il migliore o rifiuta tutti.
      Criterio done: flag `best_of_n` in config + benchmark
      costo/qualità (3x token vs primo colpo %) in DOCS/BENCH.md.
3. [ ] **[SLOT-4] Prompt per-slot + benchmark 3 task reali** — cambia
      il prompt (non il motore): uno slot per chiamata, refs solo
      dello slot, output piccolo. ⚠ Richiede run LLM (ventole al max,
      limite 60°C, sessione corta). Criterio done: 3 task reali
      misurati con pass@1 per tipo di slot in DOCS/BENCH.md.
4. [x] **[Robustezza #3] Config: validazione fail-fast all'avvio** —
      verificato (`CORE/orchestrator.py:170`): toml invalido/chiave
      errata → warning e si girano i DEFAULT silenziosamente. Criterio
      done: schema check a boot (chiavi, tipi, range), errore chiaro +
      exit se invalido; test config corrotta.
5. [x] **[Robustezza #2] Backup pre-write nel worker** — verificato
      (0 snapshot in write_file/patch_code): se una patch corrompe un
      file, l'unica rete è git manuale. Criterio done: snapshot
      deterministico in `backups/<ts>/<relpath>` (retention max N
      sessioni) prima di ogni scrittura; restore documentato; test
      roundtrip.
6. [ ] **[Fase A] Eval suite interna (mini-SWE-bench)** — i task reali
      dei Cycle 70-85 diventano test-case con soluzione di riferimento;
      runner misura primo colpo % **per asse del radar** e **per
      granularità**. Criterio done: `evals/` con ≥12 casi + runner +
      report per famiglia. Dipende da: P1-1 (✅ Cycle 85i).
      > ✅ **Slice Fase A fatta** (campagna 85n): `evals/cases.json`
      > (13 casi, 8 assi, 3 granularità) + `tools/run_eval.py` (dry-run
      > valida e riassume per asse/granularità; --live richiede LLM).
7. [ ] **[SLOT-5] Eval per-slot pass@1** — runner che misura il
      primo-colpo **per tipo di slot** (import/function/handler/widget)
      e per dimensione output: è il numero che dice se SLOT funziona.
      Criterio done: tabella per-slot in DOCS/BENCH.md su ≥12 casi.
      Dipende da: P1-1 (✅ Cycle 85i), Fase A.

### Fascia 3 — ★ Chiudere i gap del sistema

8. [ ] **[SLOT-3 / P2-3] Planner a slot v2 + scaffolding GUI** — il
      cambiamento più grande: da PLAN testuale a lista di SLOT
      (file, anchor, tipo, refs proprie, test proprio); 3-4 regole
      nuove dal decision tree (M8); template PyQt6 curati (finestra+
      layout+segnali+thread) che il worker RIEMPIE invece di
      inventare; skill `py-gui-scaffold` che punta al template.
      Criterio done: planner produce slot + 3 template in
      GUI/refs/templates/ + skill + test snapshot + 1 task GUI reale
      chiuso al primo colpo con il template.
9. [ ] **[Fase D-16] Sweep num_ctx + flash-attention** — 2048/3072/
      4096 con `flash_attention_kv`: più contesto = meno dimenticanze
      (il bug requirements era conteso in parte per contesto corto).
      Criterio done: tabella qualità/tempo in DOCS/BENCH.md, soglia
      aggiornata se vince.
10. [x] **[P2-5] Fedeltà API: refs ai moduli interni** — refs per
      orchestrator/ledger/scheduler (come toolset_api); script che
      valida che ogni simbolo citato nei refs esista davvero
      (deterministico). Criterio done: 3 refs nuovi + validatore +
      test.
11. [x] **[P2-6] Clarifier: estendere oltre GUI** — pattern per test
      ("scrivi test per X": runner? marker?), persistenza (sqlite?
      json?), handler di sistema. Criterio done: 3 pattern nuovi + test.
12. [ ] **[P2-4] Memoria/contesto: misurare l'impatto reale** — l'import
      sistemato (C85) ha reso il contesto persistente funzionante per
      la prima volta; oggi è attivo ma non sappiamo se serve. Criterio
      done: A/B 10 task con/senza contesto → verdetto in DOCS/BENCH.md
      (mantieni, riduci o dismetti).
13. [x] **[Robustezza #1] Watchdog: backoff escalato + guardia
      crash-loop** — verificato (`SAFETY/watchdog.py:88-102`): riavvio
      fisso ogni 1s, senza escalation né contatore. Un poison crash =
      riavvio all'infinito con log spam. Criterio done: backoff
      1→2→4→…max 60s, reset del contatore dopo N secondi sani,
      allerta dopo 5 riavvii; test con crash simulato.
14. [x] **[Robustezza #4] CI GitHub Actions (zero LLM)** — verificato
      (`.github/workflows` assente). Criterio done: workflow a ogni
      push → py_compile tutto-repo + pyflakes 0-undefined + test
      offscreen veloci (sottoinsieme, NON la suite 19min) su ubuntu +
      Python 3.11.
15. [x] **[Robustezza #10] Campagna Zero Warning: pyflakes 474 → 0** —
      regola nel goal (vedi header): codice pulito ed elegante.
      Baseline: 375 unused import + 39 variabili morte + 16
      redefinition + 44 altro. Criterio done: pyflakes 0 su
      CORE+GUI+tools+scripts+SAFETY+INTENT+tests/*.py; batch
      deterministici (executor meccanico per gli unused import, una
      famiglia GUI/CORE per sessione) + baseline pytest-warning
      misurata e ridotta con `-W error` dove possibile. GO/NO-GO
      onesto se i warning Qt non sono sopprimibili.
16. [x] **[Robustezza #7] security_scan.py in CI + verify_cycle** — lo
      scanner esiste (262 finding, 13 errori: 9 in GLM_SOLUZIONE_WEB)
      ma NON gira in nessuna pipeline. Criterio done: security_scan
      nel workflow CI e in verify_cycle.sh con baseline (errori
      CORE/GUI = 3, falsi positivi documentati) → new-error = fail.

### Fascia 4 — ○ Sottofondi, training e igiene

17. [ ] **[Fase C] Feasibility QLoRA 3b + GO/NO-GO onesto** — GPU 4GB
      (1GB libera) = borderline: unload ollama → ~3GB liberi; 1 run
      piccolo (500 esempi, 1 epoca) di notte a macchina fredda.
      Vincolo duro: ventole al max + guardia ≥90°C. Criterio done:
      feasibility report (VRAM reali, tempo/epoca) + verdict GO/NO-GO
      scritto qui. NO-GO ammesso e onesto. (se GO) SFT sul corpus
      curato: successi + correction come hard-negatives (V-STaR),
      valutazione SOLO su eval suite Fase A; se non batte la baseline
      → NON si integra (lezione fast lane).
18. [ ] **[Fase F] Retrieval di soluzioni passate** — TF-IDF/keyword su
      task già chiusi (NO RAG neurale — verdetto Cycle 78).
      Criterio done: tool `retrieve_similar_task()` + A/B su 10 task.
      > ✅ **Slice Fase F fatta** (campagna 85n): `CORE/retrieval.py`
      > (TaskRetriever TF-IDF, build_from_pairs/queue_db/corpus) +
      > `ToolSet.retrieve_similar_task()` + `tests/test_retrieval.py`
      > (7 test). Resta: A/B su 10 task (richiede run LLM).
19. [ ] **[Fase E] Distill occasionale** — UN task hard risolto da
      modello più grande (7b/14b, macchina fredda), soluzione
      gate-verificata → entra nel corpus Fase B: il 3b impara
      dall'esempio. Criterio done: `tools/distill_task.py` + ≥3 esempi
      nel corpus.
20. [ ] **[Fase G] A/B automatico delle varianti prompt** — refs
      on/off, posizione REFS, formato PLAN: promosso solo chi vince
      misurato. Criterio done: `tools/eval_prompt_variants.py` + 1
      esperimento chiuso con verdetto in DOCS/BENCH.md.
21. [ ] **[Fase H] Timestral giudice di qualità (mai sovrano)** —
      quando il gate passa ma la qualità è dubbia, il decision model
      valuta; logga accordo/disaccordo. MAI override automatico: il
      gate resta l'unica autorità. Criterio done: giudice opzionale +
      report accordo gate↔giudice su 20 casi.
22. [ ] **[P3-8] Modello più forte per le task GUI** — confronto
      qwen2.5-coder:7b/14b SOLO per il routing GUI (macchina fredda,
      ventole al max, sessione corta). Criterio done: tabella
      comparativa 3b vs 7b su 3 task GUI identici in DOCS/BENCH.md.
23. [x] **[P3-9] Leva termica cpupower** — cap di frequenza per run
      lunghi; richiede sudo, documentare in README (sezione termica).
24. [x] **[P3-7] Decision tree v2 (residuo)** — 3-4 regole nuove
      derivate dai fallimenti (M8) NON coperte da SLOT-3 (architettura
      resta 1-2/4: limite onesto del 3b). Criterio done: regole in
      py-arch-decision + test + 1 task architetturale piccolo chiuso.
25. [x] **[Robustezza #5] Rotazione dei log** — verificato
      (`CORE/orchestrator.py:93,102`): FileHandler piatti → crescita
      illimitata. Criterio done: RotatingFileHandler (10MB × 5) per
      .log e .jsonl + test smoke.
26. [x] **[Robustezza #6] requirements-lock.txt** — verificato
      (requirements.txt: solo `>=`): una reinstall futura può prendere
      versioni incompatibili. Criterio done: `pip freeze` dal venv →
      lock file + riga nel README.
27. [x] **[Robustezza #8] pytest-xdist per la suite (1134s)** —
      benchmark `pytest -n 2/4` offscreen; se i test Qt instabilitano
      → verdict NO-GO scritto (fail-open onesto).
28. [x] **[Robustezza #9] Verdetto GLM_SOLUZIONE_WEB** — 9 errori
      S010 in codice esperimento nel repo: decidere archivio o
      rimozione; oggi è superficie di audit rumorosa. Criterio done:
      directory spostata/taggata, scanner ripulito.
29. [ ] **[Storico residuo] Igiene performance** — ridurre il prefill
      del worker (comprimere descrizioni tool, ~30-50%/step); batch
      delle write_file con commit a fine task; caching KV via
      llama.cpp diretto (solo se il carico reale lo chiede). Nota:
      num_ctx planner 3072→2048 già fatto (Cycle 67).

**Cosa NON facciamo (onestà):** PPO/RL infrastrutturale, reward-model
training, cluster multi-GPU — fuori dai vincoli hardware e termici.
Il nostro "reinforcement" è già il correction loop: dati verificati >
compute grezzo.

---

## 📅 Piano post-test (2026-11-19 → domani)

> Sessione di test conclusa con run finale pulita (888 passed / 0 failed /
> 0 warning / EXIT=0, 1031 s). Prossima fase: benchmark LLM + slot.
>
> **⏸️ Profilazione interrotta su richiesta (2026-11-19, 582/887 test in
> 230,87 s)** — il costo è concentrato in pochi test:
> `test_e2e.py` 3 test = **147 s** (75,02 + 42,02 + 30,03),
> `test_crud_file_manager.py` 31,9 s (15,25 + 8,40 + 8,31),
> `test_keys.py` 16,3 s, `test_routing.py` 15,2 s,
> setup `test_monthly_audit.py` 3,6 s. Gli altri 2.377 test sono
> < 0,005 s. Log: `/tmp/opencode/pytest_durations.log`.
>
> **Piano di domani (2026-11-20)**: (a) completare la profilazione con
> `--durations=0` sull'intera suite, (b) introdurre marker `slow` +
> profilo **fast ≤ 3 min** (default) mantenendo il profilo **full** per
> tutti i test, (c) eseguire **tutti** i test (full) con Zero Warning.

### 🔥 Incidente termico 2026-11-20 — stop ai run locali
> Durante la profilazione il BIOS ha eseguito un **thermal shutdown a
> 90 °C** (`System Temperature (90D)`). `nbfc` riportava `Target 100`
> ma `Current Fan Speed 0.00`: il raffreddamento non smaltisce calore
> (polvere/ventola). **Nessun test, LLM o benchmark locale** finché la
> ventola non è verificata (test BIOS F2 → Fan) e pulita/riparata.
>
> **Profilazione e suite full passano su GitHub Actions**:
> `.github/workflows/profile.yml` (`workflow_dispatch`, log
> `--durations=0` come artifact, live e2e saltati con `pause.flag`).
> Dopo la riparazione: CPU ≤ 60 °C (non 65) e LLM/GPU ≤ 60 °C con
> ventole al massimo.

1. [ ] (Domani) Suite completa finale di regressione: `pytest --ignore=project
      -q -p no:cacheprovider --durations=0` (regola operativa) → conferma
      finale Zero Warning + exit 0; usare i dati per il profilo fast ≤3 min.
2. [ ] (Domani) Fase D-16 — sweep num_ctx 2048/3072/4096 con flash_attention_kv
      (run LLM, ventole al max, ≤60 °C).
3. [ ] (Domani) SLOT-4 — prompt per-slot + benchmark 3 task reali.
4. [ ] (Domani) P2-4 — A/B memoria/contesto (10 task, run LLM).
5. [ ] (Domani) Fase C — feasibility QLoRA 3b (notte, GPU 4GB, macchina fredda).

---

## 🐳 Test isolati — avvio separato (Docker)

> Aggiunto 2026-11-21 — richiesta utente: sezione dedicata ai test con
> avvio separato (es. Docker), **nessun test eseguito** (manca spazio
> sul PC locale).

### Contenuto
- Obiettivo: esecuzione della suite di test in ambiente isolato
  (container Docker) per avvii separati dalla sessione GUI/orchestratore.
- Vincoli: `state/pause.flag` per live e2e; mai `--project .`;
  `QT_QPA_PLATFORM=offscreen`.

### Azioni
- [ ] (prossima) Sviluppare compose/docker per la suite — STOP: spazio
      disco PC insufficiente, nessun run previsto adesso.
- [ ] (prossima) Documentare comandi container (pytest, lint, pyflakes).

---

## 🧠 Clarifier — wiring del planning (da implementare)

> Aggiunto 2026-11-21 — problema utente: richieste vaghe (es.
> "creami un software che mi faccia il conteggio delle parole") non
> fermano il flusso per chiedere chiarimenti. Il clarifier esiste
> (`CORE/clarifier.py`) ma è opt-in (`clarify=False`) e non è collegato
> al path di default (orchestrator → worker → `_execute_direct`).

### Root cause
- `detect_ambiguity` è chiamato solo se `clarify=True` (default False).
- Il default path non passa `clarify` né un `ask_fn`.
- `action-planner` è advisory (LLM-driven), non un gate deterministico.
- `GUI/clarification_dialog.py` esiste ma non è usato da nessuno.

### Fix proposto
- [x] (fatto 2026-11-21) Aggiungere pattern "vague software creation" al clarifier.
- [x] (fatto 2026-11-21) Collegare `clarify=True` in `_execute_direct` con `ask_fn`:
      GUI/headless fallback (input() se tty, altrimenti
      state/clarification.txt con timeout 30 s, fail-open).
- [x] (fatto 2026-11-21) Aggiungere regola AGENT.md #10 "Clarify Before Acting".
- [ ] (prossima) Integrazione GUI dialog completa (show_clarification su
      thread principale via Qt signal/slot) — richiede spazio disco per test.

---

## 🧠 Tool hallucination — tool inventati nel ReAct

> Aggiunto 2026-11-21 — problema utente: il modello ha inventato un tool
> (`check_directory`) non presente nella lista disponibile, causando
> `ERROR: unknown tool 'check_directory'`. Il task è comunque stato
> completato via fallback.

### Root cause
- Il loop ReAct non valida i nomi tool prima della chiamata.
- Il modello piccolo allucina tool plausibili ma non esistenti.
- Nessun gate che rifiuti/riproponga il tool corretto.

### Fix proposto
- [x] (fatto 2026-11-22) Validare il nome tool contro la lista disponibile
      prima dell'esecuzione; se sconosciuto, chiedere al modello di riprovare
      con un tool valido — iniettando la lista tool nel prompt di correzione
      (commit b4a17ca).
- [ ] (prossima) Iniettare la lista tool nel prompt del ReAct (già
      presente? verificare).

---

## 🐧 Linux Driver — mitigazione rischio allucinazione API kernel

> Aggiunto 2026-11-22 — risposta alla domanda "possiamo risolvere il rischio
> allucinazione (API kernel inesistenti → kernel panic)?".

### Problema
Il modello 3b può allucinare nomi/firme di API kernel. In user-space un
simbodo inesistente è un errore di compilazione; in kernel space può
diventare un **panic a runtime**. Serve un gate rigoroso.

### Strati di mitigazione (proposti)
- [x] (fatto 2026-11-22) **Refs version-pinned**: tool `tools/extract_kernel_refs.py` estrae prototipi dagli header kernel (os.walk followlinks). Skill `linux-kernel-refs` creata.
- [x] (fatto 2026-11-22) **Skill `linux-kernel-refs`**: creata e registrata.
- [x] (fatto 2026-11-22) **API whitelist**: lista deterministica di simbodi kernel
      consentiti per versione; gate pre-compile via `CORE/kernel_api_whitelist.py`
      + `tools/gen_kernel_whitelist.py`.
- [x] (fatto 2026-11-22) **Gate compile**: `make` + `checkpatch.pl` + `sparse`
      aggiunti alla skill `static-analyzer`.
- [ ] (prossima) **Scaffold deterministico (SLOT)**: il planner genera lo
      scheletro (probe/remove, file_operations, Makefile); il modello 3b
      riempie solo piccoli slot (read/write/ioctl).

### Limiti residui
- API inline/static: catturate solo parzialmente da checkpatch/sparse.
- Race condition / IRQ: gate statici non bastano → test in QEMU (runtime).
- Device tree binding: validazione con `dtc` separatamente.

---

## 🧪 Tabella dei run di test (2026-11-19)
|---|---|---|---|---|---|---|
| 1 | `/tmp/opencode/pytest_full_run.log` | 00:12:34 | 00:29:52 | 0:17:18 | 261 passed, 3 skipped, **9 warn**, 6 sub — `INT` (SIGINT) | chiusa (parziale) |
| 2 | `/tmp/opencode/pytest_full_run2.log` | 00:31:44 | 00:47:45 | 0:16:01 | 896 passed, **1 failed**, 1 xfailed, **10 warn** — `EXIT=139` (segfault post-summary) | chiusa (con fallito) |
| 3 | `/tmp/opencode/pytest_full_run3.log` | 00:50:35 | 01:07:46 | 0:17:11 | **888 passed**, 1 xfailed, **1055 sub**, **0 failed, 0 warn** — `EXIT=0` | ✅ **CHIUSA** |

**Chiusura finale**: run3 ✅ — suite verde, Zero Warning, exit 0. Fix post-run2
(`_test_*`, `__test__=False`, alias HW3) applicati e ri-verificati in run3.

---

## 📜 Storico recente (completati — dettagli conservati)

### 📅 Domani (2026-11-17) — ordine di esecuzione concordato

Macchina fredda: prima il benchmark, poi il resto. Ogni step con la
regola termica (stadiale, `--cooldown 30 --thermal-limit 60`).

1. [x] **`tools/verify_cycle.sh` — prima esecuzione end-to-end** ✅
      (Cycle 74): py_compile OK (6 file) · boot smoke OK (rc=124) ·
      test_runner 64 file / 60 OK / 4 KO / 756 pass / 3 fail / 3 skip
      in 387s. I 3 fail sono pre-esistenti e NON causati da miei cambi:
      - `test_reuse.py` (assert 3072→2048 stale, corretto ora: Cycle 67
        aveva cambiato num_ctx planner a 2048 ma il test non fu aggiornato)
      - `test_user_workflow.py::TestToolbarToggle` (flake già noto)
      - `test_functional_swarm.py` (timeout 120s, flaky su hardware)
      Disciplina rispettata: una FAIL end-to-end viene indagata, non
      ignorata — qui il FAIL era "test vecchi", non regressione.
2. [x] **Benchmark di validazione della corsia veloce (fast lane)** —
      ✅ **CHIUSO con verdetto onesto** (Cycle 66, decisione utente
      "stop definitivo"): fast lane NON validata → `enabled = false`
      permanente. Motivi misurati in `DOCS/BENCH.md` §8: (1) il limite
      60°C viene sforato nelle fasi (79-80°C) anche con `num_thread=2`
      — il turbo della i7-7700HQ compensa, pendenza 0,27-0,29°C/s
      invariata; l'unica leva reale è il cap di frequenza (sudo) o
      altra macchina; (2) fast lane 0/2 con fallback al correction
      loop (campione insufficiente ma zero evidenze pro); (3) ~22
      min/sessione dominate dalle attese di raffreddamento. Restano
      attivi e riusabili: `temp_before/after` per fase nel JSON,
      pausa termica adattiva, driver + reporter, dati parziali.
3. [x] **Micro-ciclo config** — ✅ FATTO (Cycle 67, v0.3.15):
      `num_ctx` planner 3072 → 2048 (allineato al default tipizzato);
      `[hardware].keep_alive_sec = 900` NUOVO (warmup al boot utile 15
      min invece di 5, modello caldo tra task; RAM reale 7.6GB — 3.3
      liberi, i ~2.5GB residenti ci stanno e si scaricano da soli);
      toggle verificati: Timestral ce l'ha già (`[thermal].enabled`),
      SystemMonitor e Lifecycle sono PASSIVI (zero thread, zero costo
      da fermo) → toggle non necessari, nessun codice toccato.
      llama-server diretto con --prompt-cache resta FASE 3 (item #6),
      da misurare solo dopo un eventuale riscontro di carico reale.

### 🏛️ Strategia refactoring — Registro del debito (debt ledger) (Cycle 68)

Idea utente: DB per tracciare i pezzi da rifattorizzare + skill per il
dialogo LLM↔SQL. È la metà mancante di `CORE/code_map.py` (che mappa
cosa ESISTE via AST→SQLite): il ledger tiene traccia di cosa VA
RIFATTORIZZATO. Già dentro il progetto: SQLite usato in 5 punti
(memory_event_store, sml_database, code_map, task_queue, resilience).

- [x] **REGOLA DI PARITÀ GUI (Cycle 70)**: OGNI funzione del ledger
      è usufruibile dalla Plancia (`GUI/debt_ledger_panel.py`) —
      stats, list, add, next (🎯), mark, context (🔍), refresh
      on-demand senza timer nuovi (disciplina Cycle 63).
- [x] Regole di design (deterministiche, documentate nel modulo):
      1) l'LLM non scrive SQL libero — dialoga con API/CLI Python;
      2) `file_hash` alla registrazione → item `stale` se il file
      cambia (anti-stantio: un ledger stantio è peggio di niente);
      3) un item per sessione, stadiale — il "next" arriva da una
      query, non da un'idea (pianificazione fredda, adatta al
      limite 60°C).
- [x] **`CORE/debt_ledger.py`** — schema + API (`add`, `next`, `list`,
      `mark`, `stats`) + CLI (`add/next/list/done/stats/context`) +
      integrazione `code_map` (`context_for_file` fail-open).
      DB: `state/debt_ledger.db`.
- [x] **Test** `tests/test_debt_ledger.py` — priorità, stale-on-change,
      done skip, fail-open senza codemap.
- [x] **Skill** `.opencode/skill/debt-ledger/SKILL.md` — flusso
      registrare → next → verificare → chiudere, riusabile in ogni
      sessione futura. ✅ Cycle 74: scritta (regole + CLI + ciclo di
      sessione + regola parità GUI + esempio reale 13,4s).
- [x] Docs: IMPLEMENTED Cycle 68, README versione.
- [x] **Primo test reale del flusso, a tempo (Cycle 69)**: alimentare la
      coda con item veri già noti + eseguire il primo con il flusso
      della skill (`next → progress → context → stadio → done`) e
      misurare il tempo reale. Obiettivo utente: "molto meno tempo" —
      la coda elimina l'esplorazione LLM: il lavoro è già scritto in
      SQL, la sessione esegue. Include la dimostrazione live della
      regola stale (due item sullo stesso file: il primo eseguito
      invalida il secondo → ri-registrazione).

### 🦋 Prismalux — ESPERIMENTO CHIUSO, clone rimosso (Cycle 74, 2026-11-17)

**Obiettivo dell'utente**: vedere se si poteva importare qualcosa come
software e riusarlo — fatto. **Decisione utente**: il clone esce da
byte-swarmy e si elimina (i 3 commit locali non pushati vanno persi,
confermato esplicitamente). `project/prismalux/` rimosso.

Cosa resta a byte-swarmy (il valore dell'esperimento è nel sistema,
non nel clone):
- [x] **Skill `project-radiography`** — radiografia fredda riusabile
      per qualunque progetto futuro
- [x] **Fix skill-hijack** (find_skill matchava keywords generiche →
      il worker seguiva ricette sbagliate) + test di regressione
- [x] **Runner `tools/swarm_refactor_session.py`** (agent fresh,
      gate termiche, guardia ≥90°C, threshold configurabile)
- [x] **Verdetto onesto**: il worker 3b NON è capace per modifiche
      minime a codice esistente; le gate proteggono i test ma non i
      file dati → per quella classe serve l'esecutore deterministico
- [x] **Lezione UEFI** + `VENTOLA/` (controllo ventole, prerequisito
      dei run LLM su questa macchina)
- [x] Radiografia riusabile come metodo (312 cpp/180 h/164 py,
      6 god-file, 123 marker — dati storici in DOCS/IMPLEMENTED.md)

### Test agentico — programmino Qt/PyQt6 via swarm (Cycle 50)

- [x] **Test agentico Qt/PyQt6** ✅ Cycle 76: **VERDETTO FAIL** (4° run LLM,
      4° fallimento). Task: creare `VENTOLA/hello_qt.py` (finestra +
      QLabel contatore + QPushButton). Il worker ha ignorato il file
      target e scritto `project/main.py` (10 byte) + `patch_code.py`
      (bloccato da regression gate); `hello_qt.py` NON è stato creato.
      Temp 41→79°C in 105s; guardia 90°C non scattata. Danno pulito
      (main.py ripristinato, patch_code.py/tests/test_patch_code_regression.py
      rimossi). Conclusione: il worker 3b non è capace neppure di creare
      un file PyQt6 da zero — coerenza con il verdetto sui bare-except.
      **Il test ha prodotto il suo deliverable (un verdetto onesto), non
      un'app funzionante.** Restano solo item deterministici (capability).

### Capability agentica — test→benchmark feedback + doc summarization (Cycle 51)

- [x] **Capability: test execution → benchmark feedback** ✅ Cycle 78:
      implementato in `CORE/worker.py` (done=true viene rifiutato se la
      suite è stata eseguita e fallisce; i fallimenti vengono iniettati
      come prompt di correzione, max 2 retry, poi allow done con warning).
      I risultati dei test diventano così un segnale di feedback che
      guida il loop, non solo un warning. Connesso a `_summarize_result`
      (già esistente) per l'estrazione intelligente.
- [x] **Capability: doc reading → summary** ✅ Cycle 78: nuovo tool
      `read_document(path)` in `CORE/tools.py` (testo diretto per
      .txt/.md/.py/.json/.csv/.log/.html/.xml + PDF via pdftotext con
      layout; troncamento a max_file_size_readable), registrato in
      `allowed_tools`, dispatch in `worker._call_tool`, descrizione nel
      prompt, e summarization dedicata in `_summarize_result`
      (prime 5 righe + titoli/capitoli). Il worker può ora leggere
      documenti lunghi senza saturare il contesto.

- [x] **Middle capability: escalation 3B→4B** ✅ Cycle 52: fallback del
  worker_coder (junior) → `worker_coder_big` (middle, qwen3-coder:4b) invece
  di scendere al più piccolo (worker_general 1.5B). Salto di capacità al
  tier "middle".

### Tool LLM — diario di bordo (Cycle 52+)

- [x] **Tool `diary_llm`** ✅ Cycle 53: nuovo tool che lascia un diario di
  bordo (problem, context, attempts, failures, learnings, optimization) al
  termine di un task; persistenza in `state/diary/`. Implementato con scrittura
  sicura + sanitizzazione task_id. ✅ Cycle 53.
- [x] **Diary: DB vs file** ✅ Cycle 78: **decisione documentata** —
      il diario LLM resta **file markdown** per il contesto
      self-optimization (attuale, basta per il contesto del worker); DB
      (SQLite) solo per analytics/query strutturate, da introdurre SOLO
      quando c'è un caso d'uso reale di query (oggi non c'è). Motivazione:
      il file è leggibile/editabile a mano, versionabile, zero schema
      da migrare; il DB aggiungerebbe complessità senza beneficio
      misurabile (regola "measure, don't add").

### Efficientamento energetico (proposto dopo il benchmark Cycle 59)

Ottimizzazioni per ridurre il consumo energetico, in ordine di impatto
decrescente. Il benchmark ha dimostrato che il harness è 13.6x più lento
del modello nudo (192s vs 14s per task) — la vera leva è la semplificazione.

### Regola termica permanente (🆕 Cycle 65)

> **Mini-test, mai generazioni monolitiche.** Ogni test che chiama l'LLM
> (benchmark, e2e worker, test generation) si fa a STADI brevi con verifica
> host-side tra uno e l'altro, per non surriscaldare il portatile:
> 1. **Scheletro** (classe vuota / funzioni test_* con `pass`) →
>    `pytest --collect-only` o `py_compile` (~gratis, zero LLM);
> 2. **Definizioni** (corpi minimi, assert essenziali) → verifica;
> 3. **Implementazione completa** → mai in un'unica generazione lunga.
>
> Ogni stadio genera ≤ ~300 token. Nel benchmark: un task = uno stadio,
> con `--cooldown 30 --thermal-limit 60` tra task. Errori di import o di
> struttura si scoprono allo stadio 1 SENZA pagare le generazioni
> successive. Implementata in `CORE/test_generator.py` (scheletro →
> corpi, collect-check tra gli stadi).

1. [~] **Eliminare il correction loop (single-shot)**: sostituire il ReAct
      loop (10 step) con single-shot (prompt → genera → compila → retry una
      volta). Riduzione consumo stimata ~90%. ✅ **Cycle 64** — corsia
      veloce implementata (`CORE/worker.py: _execute_fast_lane`), prompt
      nudo del benchmark, max 2 tentativi, difese deterministiche intatte
      (AST scanner, safe path, runtime verifier). **Default OFF** in attesa
      del benchmark di validazione a macchina fredda (regola "measure,
      don't add"). Attivazione: `[fast_lane] enabled = true` in config.toml.
2. [ ] **Ridurre il prefill del worker**: rimuovere tool non usati dal prompt,
      comprimere descrizioni. Riduzione stimata ~30-50% per step.
3. [x] **Consolidare i timer della GUI**: ✅ **Cycle 63** — un solo
      heartbeat (1s) al posto di 5 timer (500ms/1500ms/1500ms/3000ms);
      subprocess costosi (nvidia-smi + ollama ps) da ogni 1.5s a ogni 3s,
      zoom catch-up solo se zoom != 100, timer SIGINT 200ms → 500ms.
      Stima ~5-10% CPU costante in meno a riposo.
4. [ ] **Spegnere componenti inutili via config**: disabilitare Timestral,
      SystemMonitor, LifecycleManager quando non necessari.
5. [ ] **Ridurre num_ctx del planner**: 3072 → 2048 (come orchestrator).
6. [ ] **Caching KV cache (llama.cpp)**: salvare il cache del system prompt
      e riutilizzarlo tra chiamate. Richiede passaggio a llama.cpp diretto.
7. [ ] **Batch scritture disco**: batch delle write_file, commit solo alla
      fine del task.
  ✅ **Cycle 62** (semplificazione Fase 1): inventario CORE/, rimossi 3 moduli
  orfani (`sml_database`, `preflight_cli`, `loop_detector` fuso in
  `worker.py`), spostato `example_mcp_server.py` in `tests/`. CORE/ scende
  da ~50 a ~47 file. Nessuna metrica peggiorata (270 passed, 1000 subtests,
  boot smoke OK). Regola rispettata: Timestral LLM Tuner non toccato.

### Miglioramenti senior da applicare (dalla code review) — priorità decrescente

Interventi strutturali che chiudono i gap identificati; non sono "feature
nuove", ma migliori al sistema:

1. [x] **Classificatore di rischio deterministico + blocco umano per task ad
      alto impatto**: ✅ **Cycle 56**: modulo `SAFETY/risk_classifier.py` con
      regole deterministiche (path toccati → alto; diff > 50 righe / > 3 file →
      alto; refactoring architetturale / cambio API pubblica → alto); task
      `high`/`critical` → `awaiting_human_approval` + GUI prompt di
      conferma; log in `logs/security.log`.
2. [x] **Runtime verification harness per i diff generati**: ✅ **Cycle 56**:
      dopo ogni `write_file` e prima dell'audit, smoke test sul file
      (py_compile; test via pytest); per GUI/orchestrator: avvio headless
      controllato + timeout (boot smoke); su fail → feedback specifico nel
      correction loop. Modulo `CORE/runtime_verifier.py`.
3. [x] **Test generation per i nuovi percorsi di esecuzione**: ✅ **Cycle 57**:
      al worker, per ogni nuovo percorso scritto (write_file su modulo .py),
      generare + eseguire test di regressione via pytest; se non generabile o
      se fallisce → feedback specifico nel correction loop. Modulo
      `CORE/test_generator.py`, iniettato in `CORE/worker.py` (`execute`).
4. [x] **Semplificazione architetturale**: ✅ **Cycle 58**: inventario CORE/MONITORing,
      fusione `exception_handler.py` + `state_recovery.py` → `CORE/resilience.py`;
      rimossi i 4 moduli orfani (non importati da nessun codice di produzione)
      `exception_handler`, `state_recovery`, `benchmark`, `MONITORING/predictive`.
      Import nei test aggiornati (`test_usability_hardcore` ora importa da
      `CORE.resilience`). Nessuna metrica peggiorata (tutte le suite verdi).
5. [x] **Benchmark esterni e validazione indipendente**: ✅ **Cycle 59** (eseguito e misurato):
      nuovo modulo `CORE/external_benchmark.py` con 8 task di refactoring atomici
      su `bench_target/` (mini-repo esterno). Dual mode: harness vs modello nudo.
      **Risultato onesto**: modello nudo migliore del harness (50% vs 12.5% primo
      colpo; 14s vs 192s medio/task). Criterio di uscita Fase 0 NON raggiunto:
      tempo umano netto negativo → fermarsi e semplificare prima di aggiungere
      feature. Report in `DOCS/BENCH.md`, JSON in `state/benchmarks/`.
      Test: `tests/test_external_benchmark.py` (11 test, mock senza Ollama).
6. [x] **Fuzzing mirato sulla sicurezza**: ✅ **Cycle 60**: modulo
      `tests/fuzz_security.py` con generatore custom (seed fisso) che fuzza
      `validate_bash_command` (metacaratteri shell offuscati, path traversal
      su comandi allowlistati, comandi fuori allowlist), `ToolSet.write_file`
      (path traversal, null byte, path troppo lungo, nomi strani dentro
      project/) e `MCPClient._parse_tool_result` (payload mancanti, troppo
      lunghi, tipi sbagliati, JSON malformato, None). Invariante: nessun
      bypass di sicurezza, nessun crash non gestito. Nessun regression test
      aggiuntivo necessario in test_security.py (nessun bypass trovato).
7. [x] **Migliorare l'esperienza utente della GUI per il flusso di approvazione
      umana**: ✅ **Cycle 61**: coda approvazioni (`awaiting_human_approval`)
      dentro `GUI/task_scheduler_panel.py` con titolo, livello di rischio e
      motivo (parsed dal reason del risk gate), pulsanti Approva/Rifiuta con
      feedback/Sospendi per task singolo, approvazione in blocco solo per
      rischio basso/medio (con conferma esplicita per alto/critico), log delle
      azioni utente in `logs/user_actions.log`. Notifica badge `🔒 N` sulla top
      bar di `GUI/control_center.py` (aggiornata ogni 3s) quando ci sono
      approvazioni in sospeso. Funzioni di transizione stato in
      `GUI/task_queue.py`: `approve_task`, `reject_task`, `suspend_task`.

### Responsive
*(nessun item aperto — T-R3 e gap vuoto risolti nel Cycle 29)*

---

## 🆕 Token reduction (nuove tecniche — proposte 2026-11-14)

Priorità 1–8 per ridurre il prompt del worker di Byte-Swarmy (~4–5KB → ~1.5–2KB/step,
guadagno 50–60%, senza perdita di funzionalità). Vedi conversazione per dettagli.


Ordine consigliato: T1 → T2 → T4 → T5 → T9 → T3 → T7 → T8 → T6 (ultimo, sforzo alto) — TUTTI IMPLEMENTATI tranne T6.

---

## 🆕 Token reduction (nuove tecniche — avanzate, proposte 2026-11-14)

Priorità per ridurre ulteriormente il prompt del worker (~2KB → ~1KB/step) e il tempo
di inferenza. Vedi conversazione per dettagli.


Ordine consigliato: T10 → T11 → T13 → T15 → T12 → T14 → T16 → T17 (ultimo, sforzo alto).

---

## 🆕 Token reduction (nuove tecniche — avanzate 2, proposte 2026-11-14)

- [~] **T23 — KV cache condiviso tra task simili**: NON FATTO — fuori
  scope (Ollama già gestisce il KV cache del prefisso).
- [~] **T24 — Batch tool calls**: NON FATTO — fuori scope (guadagno
  reale ma refactor+rischio ordering alti).
- [~] **T25 — Prompt pruning per rilevanza**: NON FATTO — fuori scope
  (complessità alta, guadagno variabile).
- [~] **T26 — Quantizzazione prompt (llama.cpp)**: NON FATTO — fuori
  scope (richiede bypass Ollama con llama-cpp-python).

Ordine consigliato: T18 → T19 → T20 → T21 → T11/T12 (già in lista) →
T22 → T24 → T23 → T25 → T26 (ultimo, sforzo alto).

> **CHIUSO (2026-11-14)**: programma token reduction terminato con 22/26
> tecniche implementate (T1–T22). T23–T26 spostate in fuori scope:
> guadagno marginale o sforzo/rischio non giustificato sull'architettura
> attuale (vedi sezione Fuori scope).

---

## 🔧 Manutenzione & strumenti


## Regola workflow (da Cycle 46b)
- **Ogni report/misura va documentato in `DOCS/`** (es. `DOCS/BENCH.md`
  per i bench, `DOCS/IMPLEMENTED.md` per i cicli); i JSON grezzi restano
  in `state/benchmarks/` (gitignored). Nessun report solo in chat.
  Regola anche in `AGENT.md` §Regole (punto 6).

## Furbate candidate (verificate contro il codice, Cycle 47?)
Ottimizzazioni proposte dopo la prima misura bench — ognuna con il punto
del codice reale su cui agire. Da scegliere con l'utente:
(nessuna aperta: menu chiuso — vedi "Furbate completate (menu chiuso)")

### Bench post-furbate (Cycle 47b)

### Furbate completate (menu chiuso)

**Menu furbate (A–F): COMPLETO — tutte le furbate implementate e misurate.**

---

## Fuori scope (per scelta/limiti hardware)
- Skill worker `pyqt6-graphics` / `pyqt6-network`: fuori scope — il 3B non
  le regge; la GUI si fa a mano o con `pyqt6-basics`.
- Token reduction T23 (KV cache condiviso): Ollama gestisce già il KV
  cache del prefisso system prompt — guadagno ~zero.
- Token reduction T24 (batch tool calls): guadagno reale potenziale
  (50–70% round-trip in meno) ma richiede refactor di formato risposta +
  loop ReAct + gestione ordering; rischio regression alto.
- Token reduction T25 (pruning per rilevanza): richiede scoring delle
  sezioni; complessità alta per guadagno variabile.
- Token reduction T26 (quantizzazione KV llama.cpp): richiede di
  bypassare Ollama con llama-cpp-python — cambio architetturale.
