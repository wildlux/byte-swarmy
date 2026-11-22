# 📈 Miglioramenti implementati — Cycle 70 → 96 (v0.3.18 → v0.3.34)

![Grafico miglioramenti](grafici/miglioramenti.svg)

> Rigenera il grafico con: `.venv/bin/python tools/gen_grafici.py`
> (deterministico, zero LLM — stesso input → stesso SVG byte-per-byte)

---

## 🎯 Il Goal: sistema a livello Middle Senior

Il modello (qwen2.5-coder:3b) **non diventerà un senior** — il verdetto
del Cycle 72 è sperimentale e chiaro (4 run / 4 fallimenti su creazioni
PyQt6). Il goal dichiarato è che il **SISTEMA** (modello + gate +
executor deterministico + refs + clarifier + test) operi **almeno a
livello middle senior, o quanto più vicino possibile**.

Scala (grafico D, criteri misurabili):

| Livello | Criterio | Stato |
|---|---|---|
| **Junior** — 1/4 | 3b nudo senza sistema: 0/4 task GUI, modifiche minime fallite, requirements sovrascritto | baseline (C72) |
| **Junior+** — 2/4 | Sistema v0.3.34: 38 meccanismi attivi, gate per-slot + assembler + import-check, Zero Warning (0 pyflakes), corpus feedback, best-of-N configurabile, auto-skill/auto-tool validati, self-improvement misurabile | **◀ siamo qui** |
| **Middle** — 3/4 | ≥50% dei task chiusi al primo tentativo (senza correction), task GUI ≥50% | target intermedio |
| **Middle Senior** — 4/4 | **≥70% al primo tentativo; task GUI ≥75%; 0 simboli API inesistenti nei file scritti (gate import-check); 0 violazioni gate; 0 warning (pyflakes + pytest — regola Zero Warning) ✅ raggiunto (474 → 0)** | ★ GOAL |

Come si misura: la stessa suite (`verify_cycle.sh` + test di parità +
benchmark di sessione). Ogni meccanismo della sezione B è un gradino
verso il goal; il progresso è un numero, non un'impressione.

### Radar per asse (grafico E) — dove siamo deboli

| Asse | Oggi | Goal | Gap → azione (todo.md) |
|---|:-:|:-:|---|
| Task GUI (creazione) | 1/4 | 3/4 | scaffolding deterministico (template) — SLOT-3 |
| Modifiche minime | 3/4 | 4/4 | best-of-N attivo (fast lane), executor + disciplina |
| Refactoring mecc. | 4/4 | 4/4 | E1: `tools/refactor_guard.py` — AST + API pubblica + behavioral diff, 8/8 refactoring atomici verdi |
| Gate / verifica | 4/4 | 4/4 | punto di forza: gate per-slot + import-check |
| Fedeltà API | 3/4 | 4/4 | gate import-check (0 allucinazioni misurabili) + refs interni |
| Chiarimenti ambigui | 3/4 | 4/4 | clarifier esteso (3 pattern nuovi) |
| Architettura | 2/4 | 3/4 | SLOT: gate + assembler pronti, planner v2 (SLOT-3) |
| Memoria / contesto | 3/4 | 4/4 | A2–A3 triple con `reason` + `corrected`, A4 retrieval chiamabile, C2 report (copertura 100%): loop misurabile; impatto live resta 🔒 termico (C3) |

---

## A. Audit robustezza Cycle 85 — i 15 difetti corretti, per categoria

| Categoria | N. | Dettaglio |
|---|---:|---|
| **Funzionalità silent-dead** | 6 | persistent_memory mai importata (contesto nel prompt sempre vuoto), `run_test_suite` dead-on-arrival, path host nel sandbox (bandit/mypy/lint), combo modelli (`_ollama_installed` inesistente), `__main__` di center_area, `def embed` orfano |
| **NameError mascherati** | 4 | `proj_name` (tooltip barra), `subprocess` (fallback sensors), `log` nel fallback tomli, doppio import + riga morta (`temps`) |
| **Anti-allucinazione (ref/docs)** | 2 | cross-contamination ref Qt (pyside+QApplication → pyqt6.md), semantica errata `toolset_api.md` |
| **Infra test / collection** | 2 | `tests/archiviati` (file troncato tracciato rompeva l'exit code), TestToolbarToggle auto-start nei test |
| **Parità GUI (back_btn)** | 1 | DebtLedgerPanel e FanPanel senza via di ritorno alla Plancia |

Commit: `4a1cb1a` (12 difetti) · `0bb4998` (parità GUI) · `72e1b71` (toolbar).

---

## B. I 38 meccanismi di robustezza e anti-allucinazione attivi

| # | Meccanismo | Introdotto |
|--:|---|---|
| 1 | Regola di parità GUI (ogni funzione del ledger → controllo in Plancia) | v0.3.18 (C70) |
| 2 | Runner v2 + fix keyword skill (anti-hijack) | v0.3.20 (C72) |
| 3 | `verify_cycle.sh` — verifica end-to-end completa | v0.3.22 (C75) |
| 4 | Hard cap wall-clock `--max-run-sec` + ventole prerequisito | v0.3.24 (C77) |
| 5 | `PROTECTED_FILES` (requirements, config, .gitignore, ...) | v0.3.25 (C79) |
| 6 | Guardia anti-shrink sospetto (≥500 byte → <20% bloccato) | v0.3.25 (C79) |
| 7 | Suite gate toolset (14 test `test_toolset_gates.py`) | v0.3.25 (C79) |
| 8 | `GUI/refs/` cheat sheet + tool `list_refs()` | v0.3.26 (C81) |
| 9 | Iniezione condizionale refs nel prompt (soglia ≥2 keyword) | v0.3.26 (C82) |
| 10 | Ref WM espliciti (tkinter, pyside6) + matching word-boundary | v0.3.27 (C83) |
| 11 | Clarifier: GUI senza toolkit → domanda (ask-if-vague) | v0.3.28 (C84) |
| 12 | Mutua esclusione famiglie Qt nei ref | v0.3.30 (C85) |
| 13 | `conftest.py` root: collection ermetica (archiviati ignorati) | v0.3.30 (C85) |
| 14 | `_sandbox_argv`: traduzione path host→sandbox (bandit/mypy/test) | v0.3.30 (C85) |
| 15 | `run_test_suite` reale: test del progetto nel sandbox + fallback pytest | v0.3.30 (C85) |
| 16 | Test toolbar ermetici (mai subprocess dai test) | v0.3.30 (C85c) |
| 17 | Metrica "primo colpo %" (queue.db.first_try + report tool) | v0.3.31 (C85i) |
| 18 | Gate per-slot (pyflakes/AST sul frammento prima dell'assembly) | v0.3.31 (C85j) |
| 19 | Assembler deterministico (marker `# @@slot` / `# @@imports`) | v0.3.31 (C85j) |
| 20 | Gate import-check (0 allucinazioni API, retry ≤2) | v0.3.31 (C85j) |
| 21 | Corpus di feedback (Triple JSONL + hook worker + curate CLI) | v0.3.31 (C85k) |
| 22 | Best-of-N con gate come giudice (fast lane) | v0.3.32 (C85l) |
| 23 | Watchdog backoff escalato + guardia crash-loop | v0.3.32 (C85l) |
| 24 | Refs interni (orchestrator/ledger/scheduler) + validate_refs.py | v0.3.32 (C85l) |
| 25 | Clarifier esteso (test runner, handler sistema, formato config) | v0.3.32 (C85l) |
| 26 | Zero Warning: pyflakes 474 → 0 su CORE/GUI/tools/scripts/SAFETY/tests | v0.3.32 (C85m) |

---

## C. Crescita della suite di test (run completa)

| Metrica | Cycle 75 (v0.3.22) | Cycle 85 (v0.3.30) |
|---|---:|---:|
| Test passati | 756 | **789** |
| Subtests passati | non tracciati | **1050** |
| Fallimenti | 3 (pre-esistenti) | **0** |
| Durata run | 387 s | 1134 s |

La durata è cresciuta **perché i gate ora eseguono veri comandi sandbox**
invece di morire istantaneamente su NameError: più lento, ma finalmente
reale. Nessun flake residuo: `test_functional_swarm` passa da solo
(7 passed, 21 min — lento ma verde), `TestToolbarToggle` corretto.

---

## D. Versione per versione

| Versione | Cycle | Cosa è stato implementato |
|---|---|---|
| v0.3.18 | 70 | Ledger integrato nella GUI, regola di parità |
| v0.3.19 | 71 | Skill `project-radiography`, coda ledger per-progetto |
| v0.3.20 | 72 | Root-cause skill-hijack provata + fix keywords, runner v2 |
| v0.3.21 | 73 | Lezione UEFI, sweep MCP (57 conversioni bare except) |
| v0.3.22 | 75 | `verify_cycle.sh` end-to-end, skill `debt-ledger` |
| v0.3.24 | 77 | Ventole in Plancia, `--max-run-sec`, gate termica coretemp |
| v0.3.25 | 79 | `PROTECTED_FILES`, shrink guard, test gate |
| v0.3.26 | 81 | `GUI/refs/` + `list_refs()` |
| v0.3.26+ | 82 | Iniezione condizionale cheat sheet nel prompt |
| v0.3.27 | 83 | Ref WM espliciti (tkinter, pyside6) |
| v0.3.28 | 84 | Clarifier ask-if-vague per GUI |
| v0.3.30 | 85 | Audit robustezza: 15 difetti corretti, test ermetici |
| v0.3.33 | 86 | Chat = banco di test (tools/skill on-off), client cloud Groq/Gemini/OpenRouter, sorting Archivio, dettaglio task a 2 colonne, scan segreti |
| v0.3.34 | 86 | Auto-skill + **auto-tool** per parole chiave; fix 403 Groq (User-Agent Cloudflare); test cloud live (11 modelli, 0,78 s) |
| v0.3.34 | 86 | Dotfile `.editorconfig`, `.gitattributes`, `.env.example` (variabili cloud documentate, `.env` gitignored) |
| v0.3.34 | 86 | Riordino `TOOLS/REVERSE_ENGINEERING/` (refuso corretto, 14 riferimenti), regola cartelle in `AGENT.md` #11 + README, 0 file senza docstring in `CORE/GUI/tools` |
| v0.3.34 | 86 | Fix dialog **Dettagli task** (`QWidget` non importato): la finestra si apre di nuovo; errori e task mancanti ora avvisano invece di fallire in silenzio; 4 test di regressione offscreen |
| v0.3.34 | 86 | Fix eliminazione etichette (tombstone default) e ordinamento Archivio (header `sectionsClickable`): 5 test offscreen, logica delete unificata |
| v0.3.34 | 86 | Skill `codice-morto` + tool `find_dead_code` (AST deterministico, report-only): registrato in firme/allowlist/dispatch/auto-tool, 7 test dedicati |
| v0.3.34 | 86 | Qualità: W011 (segnali header non cliccabili), fixture `qapp` condivisa, firme/versioni API verificate, `api_lookup(strict)`, rename in anteprima con snapshot/rollback, skill `refactoring-mecc` |

---

## E. Novità Cycle 86 — banco di prova modelli e organizzazione GUI (Nov 2026)

### Banco di prova modelli (Chat)

| Componente | File | Cosa fa |
|---|---|---|
| Pannello Chat | `GUI/chat_panel.py` | sezione collassabile in Plancia; source combo, models combo, tool/skill pickers, chiave API |
| Contesto selezionabile | `CORE/chat_context.py` | elenca tool (`TOOL_SIGNATURES`) e skill (`.opencode/skill/*/SKILL.md`), salva la selezione in `state/chat_tools_skills.json`, costruisce il blocco di system prompt (max 12k char) |
| Auto-skill | `CORE/auto_skill.py` | 23 skill con keyword IT/EN, matching su parole intere, max 4 skill per prompt; anteprima live mentre si scrive; keyword extra da `state/auto_skill_keywords.json` |
| Auto-tool | `CORE/auto_tool.py` | 30 tool di `TOOL_SIGNATURES` con keyword IT/EN, stesso motore di matching, max 4 tool per prompt; anteprima separata 🛠️; keyword extra da `state/auto_tool_keywords.json` |
| Client cloud | `CORE/cloud_client.py` | provider OpenAI-compatibili (Groq, Gemini, OpenRouter), `list_models`, `pick_default_model`, `chat`, chiavi in `state/cloud_api.json` (0600); User-Agent esplicito per aggirare il blocco Cloudflare 1010 |
| CLI di test | `tools/test_cloud_api.py` | `--save-key`, `--list`, `--prompt`, misura latenza e stampa la risposta |

Le skill restano **solo** in `.opencode/skill/`; le chiavi API non entrano mai
in git (`state/` → `data/`, entrambe gitignored) e il dialog usa
`EchoMode.Password`.

### Organizzazione GUI

| Miglioramento | Effetto |
|---|---|
| Toggle "Seleziona/deseleziona tutti" | glifo e stato coerenti (☐ vuoto / ☑ pieno) |
| Archivio — click su **Name** | ordine alfabetico A→Z, secondo click Z→A — click collegato e header reso `sectionsClickable` (prima il segnale non veniva emesso) |
| Archivio — click su **📄** | raggruppa per estensione; secondo click inverte cartelle/file; freccetta di ordinamento sull'header |
| Guardia W011 | il lint segnala `sectionClicked.connect` senza `setSectionsClickable(True)`: il bug non può più tornare silently |
| Dettaglio task | due colonne: metadati/log a sinistra, **Risultato** e **Progetti** a destra |
| Codice prodotto | click sul file → codice effettivo nel viewer (con ▶ Esegui) |
| Etichette | pallini colore nel menu contestuale, settings, completer `#`, colori rapidi |
| Rinomina etichetta | pulsante ✏️ accanto a 🎨 Cambia colore e 🗑️ Elimina; `GUI/label_actions.py` aggiorna registro e task in un unico posto |
| Dotfile di configurazione | `.editorconfig` (stile = `tools/lint_style.py`), `.gitattributes` (LF + binari + `linguist-generated`), `.env.example` (variabili cloud debug/sandbox; `.env` gitignored) |
| Regola delle cartelle | contenitori di primo livello in MAIUSCOLO, una cartella per categoria, nessun refuso o duplicato — `AGENT.md` guardrail #11 e README |
| Riordino tool RE | `REVERSE_ENGEREENING_TOOLS/` → `TOOLS/REVERSE_ENGINEERING/`; 14 riferimenti aggiornati, `$ROOT` nella copia di setup corretto |
| Docstring di modulo | 0 file senza docstring in `CORE/GUI/tools` (completati i 3 `__init__.py` vuoti) |
| Dettagli task | dialog ripristinato (`QWidget` importato); errori/task assenti mostrano un avviso; `tests/test_task_details_dialog.py` (4 test offscreen) |
| Elimina etichetta | conferma "Sì" ora elimina davvero: tombstone `state/labels_deleted.json` impedisce la ricreazione dei default; logica unificata in `delete_label_everywhere()` usata da 4 pannelli |
| Test regressione | `tests/test_labels_delete_sort.py`: 5 test offscreen (tombstone, ri-creazione, task, conferma dialog, click header) |

### Sicurezza dei segreti

| Controllo | Dettaglio |
|---|---|
| `tools/security_scan.py` S030 | rileva token/credenziali nell'URL dei remote git (`.git/config`) |
| `tools/security_scan.py` S031 | rileva token reali (GitHub/Groq/Gemini/OpenRouter/AWS/Slack) nei file **tracciati** e nel diff staged |
| mascheramento | il finding mostra solo i primi 4 caratteri (`ghp_…(40 char)`), mai il token intero |
| remote git | URL pulito `https://github.com/wildlux/byte-swarmy.git`; credenziali nel credential helper dell'utente (`~/.git-credentials`, 0600, fuori dal repo) |

### Novità 2026-11-22 — inventario regex e subagent

| Meccanismo | Dettaglio | Gate |
|---|---|---|
| Inventario regex | `tests/test_regex_inventory.py` scansiona con AST il registro (`DEFAULT_PATTERNS` + `LANG_HINTS`) e le chiamate `re.*` letterali in `CORE/`, `GUI/`, `tools/`: 24 pattern, 130 usages, 148 file, 0 invalidi/duplicati. Report: `DOCS/REGEX_INVENTORY.md` | 4 test verdi, `pytest -q -s` stampa tutto |
| Subagent 1-livello | `CORE/subagent.py` + tool `spawn_subagent`/`get_subagent_report`/`list_subagents`: figli con `AgentMemory` e ruoli modello esistenti, profondità ≤1, max 4, zero LLM in `spawn()`, gate ≤60 °C/`pause.flag`, cap wall-clock. Policy: `DOCS/SUBAGENTS.md` | 8 test offline verdi, zero rete/LLM |
| Verità della verifica (A1) | `verification_status` esplicito: `not_tested` non vale `verified`; richiede `run_test_suite` o override tracciato; marker nel report, non nel result | 7 test (-integrazione), contratto `execute()` invariato |
| Corpus verificabile (A2–A3) | `reason` popolato e troncato a 4000 char, `failed_definitively` nel corpus, curatore con `done` + `corrected` stratificati e `--only-done` | 11 test offline, dedup invariato |
| Retrieval nel loop (A4) | `retrieve_similar_task` in mapping/prompt/allowlist/dispatch/auto-tool, chiamabile ma non automatico | 4 test con retriever finto |
| Best-of-N configurabile (B1) | `OrchestratorConfig.best_of_n` tipizzato e clampato 1..8; `judge_candidates` puro: primo candidato che passa il gate, `all_rejected` esplicito. Loop live resta a 1 | 8 test + 55 regressioni, zero LLM |
| Skill proposer con gate (B2) | Auto-approvazione dopo 3 successi SOLO se gate deterministico verde; gate rosso = bozza intatta + report in `failures.json` + CLI `--gate`; backup `.backup.md` e metadati su ogni approvazione | 14 test + 22 regressioni, zero LLM |
| Override guard (B3) | `CORE/override_guard.py`: chiavi note, max 4 keyword, dedup accent-insensitive, null/duplicati/JSON rotti scartati con codice+report; collegato a entrambi i loader | 10 test + 4 subtest + 26 regressioni |
| Coerenza docs (C1) | MAX_STEPS=10 e baseline security=7 unica in `AGENT.md`/`SPECIFICATIONS`/`verify_cycle.sh`; `GUI/IMPLEMENTED.md` ridotto a stub; symlink `state→data/state` dichiarato | 4 test di coerenza, zero codice runtime toccato |
| Report self-improvement (C2) | `tools/self_improvement_report.py`: corpus/verdetti/first-try, gate skill, override invalidi, copertura retrieval; snapshot rigenerabile in `DOCS/SELF_IMPROVEMENT_REPORT.md` | 6 test + 6 subtest, zero LLM |
| Prompt lint (D1) | `tools/prompt_lint.py`: misura struttura del prompt reale (regole, tool, frasi, lingua, 1 azione/turno, tono); snapshot `DOCS/PROMPT_LINT_REPORT.md`. Ipotesi: struttura sì, tono no | 6 test, zero LLM; A/B live resta 🔒 termico |
| Refactor guard (E1) | `tools/refactor_guard.py`: AST + API pubblica invariata + behavioral diff (snapshot stdin→stdout); WARN se snapshot non conclusivo, FAIL su comportamento/sintassi/API | 8/8 casi atomici + 4 negativi, zero LLM; report `DOCS/REFACTOR_GUARD_REPORT.md` |

---

*Documento aggiornato al Cycle 95 il 2026-11-22: il grafico legge ciclo e
conteggio meccanismi dai documenti, quindi basta premere 🔄 Rigenera nella
Plancia (oppure `.venv/bin/python tools/gen_grafici.py`). I valori del radar
restano giudizi espliciti in `tools/gen_grafici.py`.*

---

## ✅ Stato finale verificato — Cycle 85n (2026-11-19)

- **Suite pytest completa**: `888 passed, 1 xfailed, 1055 subtests passed, 0
  failed, 0 warning, EXIT=0` (1031 s) — run finale **pulita** (nessun segfault,
  nessun fallito, nessun warning).
- **pyflakes**: 0 warning su CORE/GUI/tools/scripts/SAFETY/INTENT/tests
  (baseline 474 → 0).
- **Regola Zero Warning**: raggiunta (errori + warning = 0).
- **Grafico miglioramenti**: rigenerato deterministico (`tools/gen_grafici.py`).

Prossimi gradini verso Middle Senior (todo.md): Fase D-16, SLOT-3/4/5, P2-4,
Fase C/E/G/H, P3-8 — tutti richiedono run LLM (ventole al max, ≤60 °C) o GPU
notturna.
