# Piano d'azione — migliorare il sistema che già si migliora (2026-11-22)

> **Interpretazione autonoma** (regola "non chiedere, esegui"): per "sistema già
> migliorato di suo" si intende il **loop di auto-miglioramento** di
> Byte-Swarmy — feedback corpus, correction loop, skill proposer, retrieval,
> eval e gate. Il piano rende quel loop **verificabile e misurabile**, non
> aggiunge un secondo meccanismo di apprendimento.
>
> **Stato aggiornato 2026-11-22: Onda 1 (A1–A4) in Cycle 87, B1 in Cycle 88,
> B2 in Cycle 89.** B3–C2 e D1 restano pianificati; C3 è 🔒 bloccato termicamente. Il piano
> agenti/subagenti è una voce separata in `todo.md` (chiusa in Cycle 86).
> Nessun run LLM, nessuna rete, nessun benchmark: dopo lo shutdown termico del
> 2026-11-20 la ventola non è ancora verificata (≤60 °C, ventole al max).
> Dettagli e gate: [`DOCS/IMPLEMENTED.md`](IMPLEMENTED.md) § Cycle 87.

## 1. Evidenze — cosa non funziona ancora nel loop

| # | Gap misurato | Prova nel codice | Effetto |
|---|---|---|---|
| 1 | `done` accettato con nomi indefiniti residui | `CORE/worker.py:679-681` | il gate non distingue "verificato" da "fallito" |
| 2 | `done` accettato con test falliti o mai eseguiti | `CORE/worker.py:730-733` | "non testato" vale come "verificato" |
| 3 | Corpus scritto solo al ritorno `done` | `CORE/worker.py:738-762` | i fallimenti definitivi non alimentano il feedback |
| 4 | Curatore filtra solo `done`, esclude `corrected` | `tools/curate_corpus.py:9-12` | gli esempi più preziosi (correction) restano fuori |
| 5 | `reason` mai popolato nella triple | `CORE/worker.py:758` | non si sa perché un task è stato corretto |
| 6 | `retrieve_similar_task` esiste ma non è chiamabile | `CORE/tools.py:351` vs `CORE/worker.py:195-214` | il retrieval non rientra nel loop |
| 7 | `best_of_n` codificato ma spento (`=1`) | `CORE/best_of.py`, `CONFIG/config.toml:237` | Fase D-15 resta aperta senza misura |
| 8 | Skill proposer auto-approva dopo 3 successi | `CORE/skill_proposer.py:318-344` | una bozza può entrare senza gate verde |
| 9 | Override auto-skill/auto-tool solo in file gitignored | `CORE/auto_skill.py:30`, `CORE/auto_tool.py:22` | nessuna validazione di schema |
| 10 | Documentazione contraddittoria | `AGENT.md:208-210` (MAX_STEPS 6) vs `CORE/worker.py:218` (10); baseline security 7/15/13 in `tools/verify_cycle.sh:9,65` e `todo.md:260-264` | le regole scritte non sono quelle eseguite |

> La tabella è lo **snapshot iniziale** del piano. Evidenze 1–8 chiuse nei
> Cycle 87–89 (A1–A4, B1, B2); 9–10 restano gli input di B3 e C1.

## 2. Principi del piano

| Principio | Applicazione |
|---|---|
| Deterministic-first | Ogni nuovo comportamento nasce come gate verificabile prima di essere usato dal modello |
| Fail-closed sulla verifica | `failed` e `not_tested` non valgono `done` senza override esplicito e tracciato |
| Report-only sull'apprendimento | Il sistema propone correzioni e bozze; non si auto-modifica il codice |
| Un item per sessione | Nessuna generazione monolitica; ogni azione ha test e gate propri |
| Termica | Ogni azione che richiede LLM resta in attesa della verifica ventola |

## 3. Onda 1 — Verità della verifica (offline, eseguibile subito)

| ID | Azione | Criterio di done | Tipo |
|---|---|---|---|
| A1 | Introdurre `verification_status` esplicito (`verified` / `failed` / `not_tested`) in `CORE/worker.py`: il `done` con `failed` o `not_tested` richiede override esplicito nel task e finisce nel report | `tests/test_worker_verification.py`: 5 casi offline (verified, import fail, test fail, mai testato, override); zero LLM | Offline |
| A2 | Scrivere triple nel corpus anche per `corrected` e `failed_definitively`, con `reason` popolato dal prompt correttivo (max 4000 char) | `tests/test_feedback_corpus.py` esteso: le triple contengono `verdict`, `reason`, `attempts`; dedup invariato | Offline |
| A3 | Aggiornare `tools/curate_corpus.py`: `done` + `corrected` come hard negatives stratificati, `--only-done` per il comportamento storico | test CLI offline con JSONL finti: conteggio per verdict, nessuna duplicazione | Offline |
| A4 | Collegare `retrieve_similar_task` al dispatch del worker (`TOOL_CODE_MAP`, prompt, descrizione, keyword auto-tool) senza chiamata automatica | test: nome presente in mapping/prompt/allowlist; callable con fake retriever | Offline |

## 4. Onda 2 — Fedeltà del feedback (offline)

| ID | Azione | Criterio di done | Tipo |
|---|---|---|---|
| B1 | Rendere `best_of_n` configurabile e testare il gate-giudice con N candidati finti (nessuna generazione reale) | test con 3 candidati, scelta deterministica, rifiuto di tutti; flag letto da config | Offline |
| B2 | `CORE/skill_proposer.py`: auto-approvazione solo con gate verde sul candidato; altrimenti bozza + report, mai sovrascrittura silenziosa | test: gate rosso → bozza, gate verde → approvazione, backup `.backup.md` presente | Offline |
| B3 | Validatore deterministico degli override auto-skill/auto-tool (chiavi note, max 4 keyword, nessun duplicato) | test con override valido e 4 invalidi; errore chiaro, fail-open sul file mancante | Offline |

## 5. Onda 3 — Coerenza e misura

| ID | Azione | Criterio di done | Tipo |
|---|---|---|---|
| C1 | Allineare le regole scritte al codice: `AGENT.md` MAX_STEPS 6→10, baseline security_scan unica, rimuovere paragrafo duplicato in `GUI/IMPLEMENTED.md:54`, dichiarare `state → data/state` | `git diff --check` + ricerca:.zero contraddizioni note | Offline |
| C2 | Nuovo `tools/self_improvement_report.py`: conta triple per verdict, tasso correction, gate rossi, proposte skill, copertura retrieval; legge solo `state/`, scrive report in `DOCS/` | esecuzione offline con dati finti: tabella Markdown prodotta, zero LLM, exit 0 | Offline |
| C3 | A/B memoria/contesto, eval per-slot, sweep `num_ctx`, distillazione, giudice Timestral | **BLOCCATO TERMICAMENTE**: solo dopo verifica ventola, CPU/LLM ≤60 °C, ventole al max | LLM |

## 6. Gate di accettazione del piano

| Gate | Comando | Soglia |
|---|---|---|
| Compilazione | `.venv/bin/python -m compileall -q <file toccati>` | exit 0 |
| Stile | `.venv/bin/python tools/lint_style.py <file toccati>` | 0 errori, 0 warning nuovi |
| Sicurezza | `.venv/bin/python tools/security_scan.py .` | nessun nuovo finding |
| Test mirati | `.venv/bin/python -m pytest tests/test_worker_verification.py tests/test_feedback_corpus.py -q` | tutti verdi, zero LLM |
| Pulizia | `git diff --check` | exit 0 |

## 7. Fuori scope (scelta esplicita)

| Esclusione | Motivo |
|---|---|
| Nuovo meccanismo di RL / reward model | Il "reinforcement" esistente è il correction loop con dati verificati; aggiungere RL senza misura è fuori dai vincoli hardware |
| Auto-modifica del codice da parte del sistema | Le proposte restano report/bozze; l'applicazione passa dai gate e da una sessione dedicata |
| Esecuzione live di best-of-N, A/B, distillazione | Richiede LLM; vincolo termico non ancora rimosso |
| Nuovi ruoli modello o credenziali cloud | Separate nel piano agenti/subagenti; qui non si toccano né config modelli né token |

## 8. Regola di chiusura

Ogni azione A1–C2, una volta eseguita, va registrata in `DOCS/IMPLEMENTED.md`
con Cycle number e spuntata in `todo.md`. Il piano resta aperto finché C3 non
è sbloccato dalla verifica della ventola; la chiusura termica è un prerequisite
fisico, non una decisione software.
