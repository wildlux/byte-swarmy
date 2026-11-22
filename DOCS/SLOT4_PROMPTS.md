# SLOT-4 — prompt per slot

Task: finestra con titolo
Template: `finestra.py.tpl` — slot: 2

> Struttura deterministica dei prompt. **Nessun modello è stato chiamato**: il benchmark con 3 task reali resta 🔒 termico.

## Prompt 1 — `statement`

```text
# SLOT 1/2 — statement

Task: finestra con titolo
Template: `finestra.py.tpl`

## REF DI QUESTO SLOT SOLO
- `TITLE`

## ISTRUZIONE
impostare il titolo della finestra

## ANCHOR (non modificarlo)
`# SLOT: titolo della finestra`

## REGOLE OUTPUT
- Rispondi SOLO con il codice di questo slot (statement).
- Massimo 40 righe, nessuna spiegazione.
- Usa SOLO le REF sopra e i nomi impliciti del tipo di slot.
- Non riscrivere gli altri slot né aggiungere API non dichiarate.
- Le ref degli altri slot non sono incluse in questo prompt.
```

## Prompt 2 — `statement`

```text
# SLOT 2/2 — statement

Task: finestra con titolo
Template: `finestra.py.tpl`

## REF DI QUESTO SLOT SOLO
- `WIDTH`

## ISTRUZIONE
impostare larghezza e altezza iniziali

## ANCHOR (non modificarlo)
`# SLOT: dimensioni iniziali (larghezza, altezza)`

## REGOLE OUTPUT
- Rispondi SOLO con il codice di questo slot (statement).
- Massimo 40 righe, nessuna spiegazione.
- Usa SOLO le REF sopra e i nomi impliciti del tipo di slot.
- Non riscrivere gli altri slot né aggiungere API non dichiarate.
- Le ref degli altri slot non sono incluse in questo prompt.
```

