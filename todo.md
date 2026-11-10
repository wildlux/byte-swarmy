# 📋 BYTE-SWARMY — TODO (Riuso codice e manutenibilità)

Regola operativa: **prima si scrive il task qui, poi si esegue**. Ogni modifica
al codice deve avere una riga con stato `[ ]` / `[x]`. I task devono essere
piccoli, atomici e verificabili.

---

## 🔄 Riuso codice e manutenibilità (sessione corrente)

### 🟢 Facile (inizio ora)

- [x] **RU1. BaseWorker per thread QThread** — `CORE/gui_worker.py` con segnali
  comuni (`progress`, `finished_ok`, `failed`) e `cancel()`. Rifattorizzato
  `WeightsDownloadWorker` e `WeightspaceProveWorker` in `GUI/settings_panel.py`
  per ereditare da `BaseWorker`.

### 🟡 Medio

- [x] **RU2. StateRepository per JSON di stato** — `CORE/state_repository.py` con
  `load_json`/`save_json`/`exists`/`remove`. Integrato in `settings_store.py`,
  `hf_weights.py` e `benchmark.py`.
- [x] **RU3. `parse_llm_json` unificato** — tutti i 4 blocchi di estrazione JSON in
  `orchestrator.py` usano ora `_REGEX.search("json_object", raw)` o
  `json_block(raw)` da `regex_controller.py`.

### 🔴 Da valutare

- [x] **RU4. Config tipizzata con dataclass** — `CORE/config_model.py` con
  dataclass per tutte le sezioni di `CONFIG/config.toml` +
  `load_typed_config()`. Gli usi esistenti di `config["..."]` continuano a
  funzionare; il nuovo codice può usare la versione tipizzata.
- [x] **RU5. Tool registry (leggero)** — `CORE/tools.py` con `TOOL_REGISTRY`,
  `@register_tool(name)`, `get_tool(name)`, `list_tools()`. I metodi
  esistenti di `ToolSet` continuano a funzionare; il registry permette di
  aggiungere tool esterni/plugin senza toccare `ToolSet`.

- [x] **RU6. Controllo path centrale** — `CORE/path_utils.py` con
  `is_relative_safe`, `has_traversal`, `sanitize_filename`, `join_safe`,
  `normalize_separators`, `path_depth`, `split_safe`, `is_within_project`;
  ri-esporta `safe_project_path` e `is_sensitive_path` da `SAFETY.security`
  senza rompere import esistenti.

### ✅ Test scritti (questa sessione)

- [x] **tests/test_reuse.py** — 22 test offline che coprono:
  `regex_controller`, `state_repository`, `config_model`, `path_utils`,
  `tools` (tool registry), `gui_worker` (logica astratta).

---

## 🏷️ Costanti centralizzate (nuova sessione)

### 🟢 Facile (inizio ora)

- [x] **CU1. `CORE/constants.py` — fonte unica per costanti ricorrenti** —
  aggiunti `OLLAMA_HOST`, `DEFAULT_NUM_CTX`, `BTN_TRANSPARENT_STYLE`,
  `BTN_TRANSPARENT_DANGER_STYLE`.
- [x] **CU2. Sostituisci `http://localhost:11434`** — 19 occorrenze in
  `CORE/*`, `GUI/*`, `INTENT/*`, `tests/*` → usa `OLLAMA_HOST`.
- [x] **CU3. Sostituisci `num_ctx=4096`** — occorrenze in
  `orchestrator.py`, `model_selector.py`, `llm_tuner.py`,
  `control_center.py`, `config_model.py` → usa `DEFAULT_NUM_CTX`.
- [x] **CU4. Stile pulsante trasparente centralizzato** — definite
  `BTN_TRANSPARENT_STYLE`, `BTN_TRANSPARENT_DANGER_STYLE`,
  `BTN_TRANSPARENT_MEDIUM_STYLE`, `BTN_TRANSPARENT_SMALL_STYLE` in
  `CORE/constants.py`; sostituite le 6 occorrenze principali in
  `GUI/control_center.py` (quelle con più ripetizioni). Le rimanenti
  in altri file GUI sono singole e possono essere rifatte al bisogno.

### 🟡 Medio (da valutare dopo CU1-CU4)

- [x] **CU5. Spezzare `GUI/control_center.py`** — separare `FileSystemModel`, `CheckableTreeView`, `FileTreeDrawer` in `GUI/file_manager.py`. ✅ Fatto: `FileSystemModel` e `CheckableTreeView` spostati in `GUI/file_manager.py` (riga 3794-4049 rimosse da control_center.py). `FileTreeDrawer` resta per ora (intrecciato con ControlCenter).
- [x] **CU6. Spezzare `GUI/main_window.py`** — separare aree della plancia in widget dedicati. ✅ Fatto: creato `GUI/panels.py` con `wrap_in_panel_page`, `build_actors_page`, `build_cicd_page`, `build_clean_code_page`, `build_config_page`, `build_scheduler_page`, `build_plancia_cards`, `build_tools_cards`. `control_center.py` li importa e usa. Le card della plancia (cards_grid, tools_grid) sono ora costruite da `panels.py`.
- [x] **CU7. Dimensioni fisse GUI** — 87 occorrenze `setFixedSize/Width/Height`: valutare sostituzione con `setMinimumSize` + stretch dove opportuno. ✅ Fatto parzialmente: sostituite ~14 occorrenze (titoli, barre toolbar/command-bar, input file_name, larghezze colonne CPU/GPU, larghezza ricerca categorie). Rimangono fissi i pulsanti quadrati (28x28, 24x24, ecc.) e i separatori per coerenza visiva.

---

### ✅ Completato (questa sessione)

- `CORE/regex_controller.py` — controllore centralizzato regex (pattern precompilati + helper statici).
- `CORE/hf_weights.py`, `CORE/weight_space_harness.py`, `CORE/tools.py`, `CORE/orchestrator.py` — integrati con `regex_controller`.
- `GUI/settings_panel.py` — sezione "Pesi da Hugging Face" (sviluppo beta) con worker thread dedicati.
- `GUI/control_center.py` — **pulsante toggle ☑ "Seleziona/deseleziona tutti"** nell'header "Lavori e compiti" (a destra, accanto a 🔄 ➕ 🗑️ 🧹), agisce sulle checkbox dei task.
- `GUI/control_center.py` — **Plancia di controllo compatta**: triangolo "arrotola" (▾/▸) allineato in alto a destra; rimosso spazio vuoto sotto l'header → più spazio per i menù rettangoli (card) sottostanti. (`CollapsibleSection`: header minHeight 40px, margini header 6px, margini content-top 6px, toggle_btn `AlignTop`.)
- `GUI/control_center.py` — **Zoom reale**: `_apply_zoom` riscala i font-size hard-coded (px e pt) negli stylesheet inline per-widget e nel QSS della finestra a partire da base 100% (fattore assoluto level/100, zero drift); catch-up periodico (1,5s) scala i widget creati dopo lo zoom; barra zoom `[-][%][+][↻]` con etichetta live; scorciatoie Ctrl++ / Ctrl+− / Ctrl+0 (`_ZoomEventFilter` + `keyPressEvent`); zoom persistito in `CONFIG/settings.json` (`settings_store.get_zoom_level`/`set_zoom_level`).
- `GUI/control_center.py` — **QSplitter verticale** tra file tree e lista task (metà/metà di default, ridimensionabile, dimensioni persistenti in `state/splitter_vertical_state.json`).
- `GUI/control_center.py` — **Usabilità plancia**: badge testo bianco su colore solido (contrasto), badge dimensione fissa, titoli troncati con elipsis + tooltip, tooltip valori CPU/GPU (2.1G, 65%, 800M), filtro categorie "Tutte le categorie" accanto alla ricerca, barra avanzamento "Pronto" a riposo, larghezza minima pannello sinistro adeguata allo zoom, scrollbar visibile sull'area card.
- `GUI/gui_backend.py` + `GUI/control_center.py` — **Bug CPU/GPU valori identici**: `kv`/`mem`/`bus` erano segnaposto hardcoded (2.1G, 65%, 800M) uguali per entrambi. Ora leggono valori reali: RAM % da `/proc/meminfo`, GPU mem % e frequenza da `nvidia-smi`, KV cache stimata da `context_used` + architettura modello (`INTENT.metrics.estimate_kv_cache_mb`). Mostrano `-` quando il dato non è disponibile.
- `GUI/control_center.py` — **Rimossi ultimi valori hardcoded**: inizializzazioni `self._cpu_temp`, `self._gpu_temp`, `self._tok_s`, `self._kv`, `self._mem`, `self._freq` e le label iniziali di `_device_row` ora usano valori neutri (`0`, `0.0`, `-`) invece di segnaposto fittizi (45°C, 12t/s, 2.1G, 65%, 800M). I valori reali vengono popolati al primo tick di `_tick_metrics`.
- Documentazione: aggiornati README.md, AGENT.md, todo.md.

## 🔴 Priorità 1 — Rilevamento ripetizioni e anti-loop (critica)

- [x] **CORE/loop_detector.py** — nuovo modulo: rileva ripetizioni nell'output LLM (n-grammi ripetuti, rapporto di compressione testo molto alto) e restituisce motivo del loop / None.
- [x] **CORE/ollama_client.py** — `call_streaming` accetta `options_override` (nuovo seed, temperatura, penalità per chiamata singola); `_clamp_options` applica clamp di sicurezza: `repeat_penalty ≥ 1.05`, `temperatura > 0`, `repeat_last_n` in [64,256], `num_predict` finito.
- [x] **CORE/orchestrator.py** — `execute` rileva loop con `detect_loop`; se trovato, applica fallback (nuovo seed, temperatura +0.1, penalità +0.05); se il loop persiste, interrompe con errore esplicito.
- [x] **CORE/orchestrator.py** o **CORE/correction.py** — (fallback già integrato in execute) verificare copertura anche nel percorso correction/post-execution: il task rifiutato dall'audit viene rimesso in pending e rieseguito tramite `worker.execute()` → `call_streaming()` → `detect_loop()`, quindi il rilevamento loop si applica anche ai tentativi di correzione.

## 🟡 Priorità 2 — Robustezza e rollback

- [x] **CORE/last_good_config.py** — nuovo modulo: salva in `state/last_good_config.json` l'ultima configurazione LLM (temperature, top_p, repeat_penalty, ...) che ha portato un task al completamento con successo. Fornisce `save/load/clear` per model_key.
- [x] **CORE/ollama_modelfile.py** — nuovo modulo: legge i PARAMETER effettivi dal Modelfile di Ollama (`ollama show --modelfile <nome>`) e li usa come punto di partenza fisso (priorità su config.toml). Fallback a {} se Ollama non disponibile o senza PARAMETER espliciti.
- [x] **CORE/ollama_client.py** — `_get_tuned_options` usa i valori del Modelfile come base (Modelfile > config.toml > default); `call` e `call_streaming` salvano le opzioni usate in `self.last_options_used[model_key]`.
- [x] **CORE/orchestrator.py** — dopo `mark_done` salva la config usata come "last good"; quando un task raggiunge `failed_definitivamente`, fa rollback all'ultima configurazione buona sovrascrivendo `models_cfg[model_key]`.

## 🟢 Priorità 3 — Modello pesante su GPU (qwen2.5-coder:3b)

- [x] **CONFIG/config.toml** — `worker_coder` passa da `qwen2.5-coder:1.5b` a `qwen2.5-coder:3b` (disponibile su Ollama, ~1.9 GB). Parametri adeguati per il 3B: temperature=0.2, top_p=0.8, top_k=20, repeat_penalty=1.1, repeat_last_n=256, num_ctx=4096, num_predict=512, seed=42.
- [x] **CORE/constants.py** — `ACTOR_WEIGHT_DEFAULT_MODELS["llm"]["medium"]` passa da `qwen2.5:3b` a `qwen2.5-coder:3b` (coerenza con worker_coder).
- [x] **byte-swarm.sh** — Aggiunte variabili d'ambiente `OLLAMA_MAX_LOADED_MODELS=1` e `OLLAMA_KEEP_ALIVE=300` per far convivere il modello leggero (RAM) e il pesante (GPU) senza saturare la memoria.
- [x] **byte-swarm.sh** — Check pre-avvio: avvisa se `qwen2.5-coder:3b` non è installato (non blocca, usa fallback 1.5b).

## 🟡 Priorità 4 — Schema consigliato e configurazione attori

- [x] **Schema consigliato** — Documentato in README.md: Router (qwen2.5:0.5b, RAM) → Coder 3B Q4_K_M (GPU) → Verifica (test/compilatore), con fallback a Coder 1.5B (RAM) se il 3B fallisce.
- [x] **Configurazione attori** — Aggiornato `ACTOR_WEIGHT_DEFAULT_MODELS` in `CORE/constants.py` e documentazione per riflettere il nuovo modello pesante su GPU.
- [x] **Fallback modello** — In `CORE/orchestrator.py`: quando `worker_coder` (3B) fallisce definitivamente, il task viene rimesso in `pending` e rieseguito con `worker_general` (1.5B) come secondo tentativo. Metodo `_execute_task_with_worker` estrapolato per evitare duplicazione di codice.
