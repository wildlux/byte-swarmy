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

- [ ] **CU5. Spezzare `GUI/control_center.py`** — 6.498 righe: separare
  `FileSystemModel`, `CheckableTreeView`, `FileTreeDrawer` in `GUI/file_manager.py`.
- [ ] **CU6. Spezzare `GUI/main_window.py`** — 4.484 righe: separare aree
  della plancia in widget dedicati.
- [ ] **CU7. Dimensioni fisse GUI** — 87 occorrenze `setFixedSize/Width/Height`:
  valutare sostituzione con `setMinimumSize` + stretch dove opportuno.

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
- Documentazione: aggiornati README.md, AGENT.md, todo.md.
