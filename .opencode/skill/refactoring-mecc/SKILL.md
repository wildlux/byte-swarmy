---
name: refactoring-mecc
description: Skill per refactoring meccanico sicuro (rename di simboli) con anteprima, snapshot e gate deterministici. Usa quando l'utente chiede di rinominare funzioni/variabili/classi, fare refactoring meccanico o annullare un rename.
---

# Refactoring meccanico — anteprima → gate → apply → rollback

Regola: **mai scrivere senza anteprima e snapshot**. Il tool è il meccanismo,
questa skill è la policy: non duplicare la firma del tool, richiamarla.

## 1. Workflow

1. **Anteprima** (default, nessuna scrittura): `rename_symbol(old, new)` →
   diff unificato + conteggio occorrenze. Controlla che le occorrenze in
   stringhe/commenti siano segnalate e **non** toccate.
2. **Verifica**: `find_references(old)` per scoprire usi via reflection,
   stringhe, config o API esterna; `get_call_graph(old)` se serve il contesto.
3. **Apply** solo dopo verifica: `rename_symbol(old, new, apply=True)` →
   scrittura transazionale e snapshot in `state/refactor_snapshots/<id>/`.
4. **Gate**: `compileall`, `tools/lint_style.py`, `tools/security_scan.py`,
   test mirati. Zero errori e zero warning nuovi.
5. **Rollback** se un gate è rosso: `restore_snapshot('<id>')`, poi
   riesegui i gate. Non committare finché tutto non è verde.

## 2. Cosa non fare

- Non sostituire con regex globale: il tool usa token NAME e lascia intatte
  stringhe e commenti.
- Non rinominare API pubbliche usate fuori dal repo senza verifica esplicita.
- Non applicare a interi moduli senza aver controllato gli importatori.

## 3. Falsi positivi noti

- `getattr`, `importlib`, nomi in JSON/config/UI e segnali Qt collegati per
  stringa.
- Omonimi in classi diverse: il rename è per nome, non per scope — verifica
  con `find_references` prima dell'apply.

## 4. Output atteso

| File | Occorrenze codice | Occorrenze testo | Azione |
|---|---|---|---|
| `path.py` | N | K (non toccate) | rinominato / conservato |

Poi: ID snapshot, gate eseguiti e commit atomico separato.
