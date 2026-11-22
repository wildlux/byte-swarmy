---
name: codice-morto
description: Trova e gestisce codice morto (funzioni, metodi, classi, import non referenziati) con report deterministico e verifica prima della rimozione. Usa quando l'utente parla di codice morto, dead code, codice inutilizzato, funzioni/import non usati, pulizia del codebase.
---

# Codice morto — trova, verifica, rimuovi con gate

Regola d'oro: **il report NON è una sentenza**. Nessuna cancellazione senza
verifica e gate deterministici.

## 1. Scopo
- Rilevare definizioni pubbliche e import che non risultano referenziati.
- Fornire un report stabile e verificabile, senza mai modificare i file.
- Guidare una rimozione sicura, a piccoli passi, con rollback git.

## 2. Workflow

1. **Report** (sola lettura):
   ```bash
   .venv/bin/python -c "from CORE.dead_code import scan, format_report; print(format_report(scan('.')))"
   ```
   Oppure, nel worker/Chat, il tool `find_dead_code(path='.')`.
2. **Verifica ogni candidato** prima di toccare nulla:
   - `find_references(nome)` e `get_call_graph(nome)`;
   - cerca anche stringhe dinamiche (`getattr`, `importlib`, nomi nei file `.ui`,
     route HTTP, segnali Qt, entry point registrati in `pyproject`/config);
   - controlla che non sia un'API pubblica usata da progetti esterni.
3. **Classifica** il risultato in tabella:

   | Candidato | File:riga | Verifica | Azione |
   |---|---|---|---|
   | `nome` | `path:42` | 0 riferimenti / solo definizione | rimuovi oppure conserva (motivo) |

4. **Rimozione** solo se confermata: `patch_code(path, old, new)` un blocco
   alla volta. Non usare `delete_file` per interi moduli senza aver verificato
   gli importatori.
5. **Gate dopo ogni rimozione**: `compileall`, `tools/lint_style.py`,
   `tools/security_scan.py`, test mirati del modulo toccato. Zero errori e
   zero warning nuovi, altrimenti `git checkout -- <file>` e riesamina.

## 3. Falsi positivi noti
- Hook di framework e metodi Qt (eventi, `paintEvent`, `eventFilter`).
- Entry point (`main`, `run`, `test_*`), getter/setter pubblici.
- Funzioni con decoratori (route, slot, property): possono essere richiamate
  dall'esterno.
- Riferimenti solo in stringhe/JSON/config o via reflection.
- `__init__.py` è escluso dagli import sospetti perché è un re-export.

Il detector in `CORE/dead_code.py` esclude già queste categorie; il giudizio
finale resta umano.

## 4. Output atteso
- Report con `file:riga`, tipo (funzione/classe/import) e conteggio candidati.
- Nessuna modifica applicata dal tool: `find_dead_code` è **report-only**.
- Dopo l'intervento: tabella con rimosso/conservato e gate superati.
- Se il lavoro viene registrato, aggiorna `DOCS/MIGLIORAMENTI.md` e `todo.md`.
