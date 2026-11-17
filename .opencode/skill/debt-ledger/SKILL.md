---
name: debt-ledger
description: Registro del debito tecnico di byte-swarmy (SQLite). Usa quando trovi un pezzo da rifattorizzare/ottimizzare, quando devi scegliere su cosa lavorare, o quando l'utente parla di refactoring, debito tecnico, ottimizzazioni da tracciare.
---

# Debt ledger — il flusso completo

Il ledger decide il lavoro: **`next` torna la coda, mai "un'idea"**.
Deterministico-first: l'LLM non scrive SQL libero, dialoga con le
API/CLI del modulo (`CORE/debt_ledger.py`). Verifiche anti-stantio con
`file_hash` (se il file è cambiato dopo la registrazione, l'item
diventa `stale` e non torna da `next`).

## Regole permanenti (leali e non negoziabili)

1. **REGISTRA solo con premessa misurata** — numeri dalla radiografia
   (skill `project-radiography`), mai "mi sembra". Il vincolo di
   verifica (build? test? grep?) va scritto nel rationale.
2. **UN item per sessione** — stadiale: mini-test, mai generazioni
   monolitiche.
3. **`next` decide** — apri la sessione con `next`; il titolo dell'item
   è il lavoro. Se l'item è stale → prima capire perché (file
   cambiato: rileggere, registrare nuovo o aggiornare).
4. **Per-progetto**: ogni progetto target ha il SUO ledger
   (`--root project/<nome>`); quello di default è di byte-swarmy.
5. **REGOLA DI PARITÀ GUI (Cycle 70)**: ogni funzione del ledger deve
   avere un controllo nella Plancia (`GUI/debt_ledger_panel.py`) —
   niente API che esistono solo da terminale. Se aggiungi una funzione,
   aggiungi anche il bottone.
6. **Chiudi onesto**: `done` solo dopo verifica deterministica
   (py_compile + grep + diff + `git status` del clone). Se il worker
   LLM fallisce → verdetto scritto, fallback deterministico
   documentato, item chiuso comunque (la coda non si seppellisce).

## CLI (tutti i comandi)

```bash
D=".venv/bin/python -m CORE.debt_ledger"

# registrare (premessa misurata nel rationale!)
$D add [--root project/<nome>] --kind refactor|optimization|test|docs \
    --file <percorso> --title "Cosa" --rationale "Perché, con dati" \
    [--priority 1|2|3] [--effort xs|s|m|l]

# il lavoro decide da solo
$D next [--root ...]          # prende l'item valido a priorità più alta
$D list [--root ...] [--status open|done|in_progress|stale]
$D mark <id> in_progress|done|open [--root ...]
$D done <id> [--root ...]     # scorciatoia per mark done
$D get <id> [--root ...]      # dettaglio completo
$D context <file> [--root ...] # simboli del file dal code_map (fail-open)
$D stats [--root ...]         # done · in_progress · open · stale
```

`--kind` ammessi: `refactor`, `optimization`, `test`, `docs`.
`--effort`: `xs`, `s`, `m`, `l` (stima onesta, non aspirazionale).

## Il ciclo di sessione (stadiale)

```
1. $D next                 → l'item torna dalla query (id, title, file)
2. Stadio di lavoro:
   a. LLM? → tools/swarm_refactor_session.py (agent fresh, guardie
      termiche, disciplina in descrizione) — SOLO con ventole attive
   b. Meccanico? → esecutore deterministico (sed/grep/refactor API),
      documentato come fallback nel ledger/docs
3. Verifica deterministica:
   - py_compile dei file toccati
   - grep del pattern (deve valere 0 residui se l'item lo promette)
   - git diff (sano: solo le righe promesse)
   - git status del clone (nessun file hallucinato)
4. $D done <id>            → item chiuso
5. Docs: DOCS/IMPLEMENTED.md + todo.md + README versione
6. Commit + push byte-swarmy
```

## Esempio reale (Cycle 69, misurato)

Ciclo completo — `next` → esecuzione fredda → verifica → `done` —
**13,4 secondi**: la disciplina costa meno di una pausa termica.

## GUI (regola di parità)

Pannello 🏛️ **Registro del debito** in Plancia: `stats` (etichetta),
`list` (tabella), `add` (dialog), `next` (🎯 Prossimo: prende, marca
in corso, seleziona), `mark` (▶ In corso / ✅ Fatto), `context`
(🔍 simboli code_map), refresh solo a bottone (zero timer nuovi).
