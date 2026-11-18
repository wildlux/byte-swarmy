# Modulo: CORE.debt_ledger
# Debt ledger — cheat sheet (byte-swarmy)

## CLI (tutti i comandi)
```bash
D=".venv/bin/python -m CORE.debt_ledger"
$D add [--root project/<nome>] --kind refactor|optimization|test|docs \
    --file <path> --title "Cosa" --rationale "Perché, con dati" \
    [--priority 1|2|3] [--effort xs|s|m|l]
$D next [--root ...]          # item valido a priorità più alta
$D list [--root ...] [--status open|done|in_progress|stale]
$D mark <id> in_progress|done|open [--root ...]
$D done <id> [--root ...]
$D get <id> [--root ...]
$D context <file> [--root ...]  # simbodi dal code_map
$D stats [--root ...]           # done · in_progress · open · stale
```

## Regole permanenti
1. **Registra solo con premessa misurata** (numeri dalla radiografia)
2. **UN item per sessione** — stadiale
3. **`next` decide** — mai "un'idea"
4. **Per-progetto**: `--root project/<nome>`; default = byte-swarmy
5. **Parità GUI**: ogni funzione ha un controllo nella Plancia
6. **Chiudi onesto**: `done` solo dopo verifica deterministica

## Kind / Effort
- kind: `refactor`, `optimization`, `test`, `docs`
- effort: `xs`, `s`, `m`, `l`
- priority: `1` (alta), `2` (media), `3` (bassa)

## Stale logic
- Ogni item ha un `file_hash` (SHA256 del file al momento della registrazione).
- Se il file cambia dopo la registrazione, l'item diventa `stale` e non torna da `next`.
- Serve per evitare di lavorare su premesse obsolete.

## GUI (Plancia)
- 🏛️ Registro del debito: stats (etichetta), list (tabella), add (dialog),
  next (🎯 Prossimo), mark (▶/✅), context (🔍), refresh on-demand.
- Zero timer nuovi (disciplina Cycle 63).
