# Architettura a SLOT — far diventare "ottimo" qwen2.5-coder:3b

> 2026-11-18 · proposta-architettura v1 · deterministica-first
> Premessa misurata: generazione whole-file del 3b = **0/4** (verdetto
> Cycle 72, 4 run / 4 fallimenti su PyQt6). Il problema non è "quanto
> sa" il modello: è **quanto è grande il singolo output che gli chiediamo**.

---

## L'inversione

Un cervello 3B non può tenere in memoria di lavoro un file PyQt6
intero (layout, segnali, thread, imports). Ma un cervello 3B **può
riempire correttamente una funzione di 20-60 righe** se gli viene dato:

1. lo scheletro già scritto (template deterministico),
2. le refs SOLO di quel punto (zero rumore),
3. un output piccolo e vincolato,
4. decodifica quasi-greedy (temperature 0.1, già default nel progetto).

Quindi: **non chiedere al 3b di essere l'ingegnere. Chiedigli di
essere il muscolo che riempie buchi piccoli, verificati uno alla volta.**

```
TASK dichiarativo
   │
   ▼
[1] PLANNER DETERMINISTICO ──── decision tree v2 + code_map
   │     produce SLOT (non testo libero):
   │     ogni slot = {file, anchor, tipo, refs proprie, test propio}
   ▼
[2] FILLER = qwen2.5-coder:3b
   │     UNO slot per volta · output 20-60 righe · refs solo dello slot
   │     slot "hard" → BEST-OF-N=3 (Fase D applicata al livello slot)
   ▼
[3] GATE PER-SLOT ───────────── pyflakes + AST su SOLO lo slot
   │     fallito → correction loop SOLO su quello slot (≤3)
   ▼
[4] ASSEMBLER DETERMINISTICO ── python puro, zero LLM
   │     inserisce gli slot, gestisce import, formattazione
   ▼
[5] GATE FINALE (già esiste) ── test + marker + behavioral diff
   ▼
[6] CORPUS PER-SLOT (Fase B) ── ogni (refs, slot, verdetto) = 1 esempio
   ▼
[7] QLoRA STaR (Fase C) ────── fine-tune sui slot PASSATI,
                                 slot falliti = hard-negative (V-STaR)
   ▼
[8] RETRIEVAL (Fase F) ─────── "questo slot assomiglia a X già chiuso"
```

## Perché questo lo rende "ottimo" (e il whole-file no)

| | Whole-file (oggi) | Slot (proposto) |
|---|---|---|
| Output per chiamata | 100-400 righe | 20-60 righe |
| Contesto occupato da rumore | alto | ~zero (refs solo dello slot) |
| Errore tipico | file intero da buttare | 1 slot da correggere |
| Correction loop | non ci arriva il 3b | dentro la sua capacità |
| Signal per il fine-tuning | confuso (file intero) | pulito e denso per esempio |
| pass@1 misurato (C72) | 0/4 | **da misurare (Fase A)** |

## Cosa cambia (i componenti)

1. **Planner** — da PLAN testuale a lista di SLOT (decision tree v2 +
   scaffolding P2-3 si fondono qui). È il cambiamento più grande.
2. **Worker** — prompt per-slot: stesso ollama_client, stesso sandbox,
   stesso sandbox, stesso gate terminale. Cambia il PROMPT, non il motore.
3. **Gate per-slot** (nuovo, ~80 righe) — pyflakes/AST sul frammento
   prima dell'assembly; il gate finale resta l'autorità.
4. **Assembler** (nuovo, ~150 righe) — deterministico, gestisce import
   e placement; è il pezzo che NON esiste oggi.
5. **Eval per-slot** (Fase A) — pass@1 misurato PER TIPO di slot
   (import/function/handler/widget): qui si vede l'asse di miglioramento.

## Cosa NON cambia (le regole del sistema)

- Sandbox bwrap (11/11 PASS), SAFETY, limite 60°C, ventole-al-max.
- Il gate deterministico resta l'unica autorità (nessun LLM sovrano).
- Regola **Zero Warning** (0 errori E 0 warning) anche per i componenti nuovi.
- Un item per sessione; mai generazioni monolitiche.

## Ordine di attacco (costo/beneficio crescente)

1. **Assembler + gate per-slot su 1 solo tipo** (slot "function" in
   file esistente): prototype in 1 sessione, misurato su 3 task reali.
2. **Best-of-N=3 sui slot hard** — già in Fase D, applicato qui.
3. **num_ctx sweep** (P1/D16) — serve al planner, non al filler.
4. **QLoRA STaR sul corpus di slot** — solo dopo ≥100 slot verificati;
   GO/NO-GO onesto su GTX 1050 4GB (1GB libera), notte a macchina fredda.

## Limiti onesti (dove NON arriva)

- L'asse **Architettura** del radar resta 2/4: un 3B non disegna
  architetture nuove — le DISCEDE il planner deterministico.
- "Ottimo" = **Middle Senior**: ≥70% dei task scoped chiusi al primo
  tentativo, 0 warning. Oltre: serve la distillazione (Fase E) o
  hardware diverso — nessuna architettura fa diventare un 3B un
  progettista da 480B.
