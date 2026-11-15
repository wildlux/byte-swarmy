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
