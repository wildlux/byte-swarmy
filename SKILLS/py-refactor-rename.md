---
id: py-refactor-rename
title: Python rename symbol across files (multi-file refactoring)
keywords: rinomina, rename, rinominare, classe, tutto il progetto, referenzia, referenziato, dipendenze, multi-file, multi file
---
# Recipe: rename symbol across files (multi-file)

STEPS (follow in order):
1. Identifica il simbolo da rinominare (classe/funzione) e la sua
   DEFINIZIONE: cerca `class {{OLD NAME}}` o `def {{OLD NAME}}` nel
   file dove è definito.
2. Trova TUTTI i file che lo referenziano: definizione, import,
   uscite `{{OLD NAME}}(...)` e `import {{OLD NAME}}` nei moduli
   citati nel task (es. utils.py, app.py) e nei loro test
   (es. test_app.py). NON toccare altre parti.
3. Rinomina con lo stesso nome in OGNI file referenziato, definizione
   compresa: la classe/funzione mantiene IDENTICA firma e comportamento.
   Aggiorna anche le stringhe-di-errori e i commenti che citano
   esplicitamente il vecchio nome.
4. NON modificare la logica: solo il nome. Nessuna riformattazione
   del resto del codice, nessun spostamento di funzioni tra file.
5. done=true con una riga: simbolo rinominato in N file (elenco).

REGOLE:
- Rinomina TUTTE le referenze trovate, non solo la definizione:
  un simbolo rinominato solo nella definizione rompe gli import.
- Non rinominare simboli omofoni in moduli NON coinvolti dal task.
- Non aggiungere file nuovi se il task non lo chiede.
