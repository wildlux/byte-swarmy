---
id: py-arch-decision
title: Python architectural decision (pattern choice) (single file)
keywords: architettura, architecture, pattern, design, scelta, trade-off, struttura, progettazione, sistema
---
# Recipe: architectural decision (single file)

STEPS (follow in order):
1. Leggi il task e scegli UN pattern dalla tabella DECISION TREE.
2. Stampa # PATTERN_SCELTO=<nome> e # TRADEOFF=<motivazione> come prime 2 righe del file.
3. Create project/main.py using il TEMPLATE generico + il pattern scelto.
4. 5. done=true with a one-line result.

## DECISION TREE (scegli il PRIMO che matcha)

| # | Se il task menziona... | Pattern |
|---|---|---|
| 1 | file grande, streaming, riga per riga, memoria limitata | GENERATOR |
| 2 | risorsa da aprire/chiudere, with, cleanup | CONTEXT_MANAGER |
| 3 | wrappare, misurare, ritentare, loggare, cache | DECORATOR |
| 4 | thread, concorrenza, producer-consumer, lock | THREADING |
| 5 | stato condiviso, CRUD, persistenza, dati | CLASS |
| 6 | CLI, argomenti, flag, sottocomandi | ARGPARSE |
| fallback | nessuno dei precedenti | CLASS |

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
# PATTERN_SCELTO={{ PATTERN DALLA TABELLA }}
# TRADEOFF={{ MOTIVAZIONE IN 1 RIGA }}


def main():
    {{ IMPLEMENTAZIONE DEL PATTERN SCELTO }}
    print(f"{{ MARKER }}={{ VALUE }}")


if __name__ == "__main__":
    main()
```

RULES:
- - PRIMA di scrivere codice, la prima riga del file DEVE essere: # PATTERN_SCELTO=<nome>
- La seconda riga DEVE essere: # TRADEOFF=<motivazione in 1 riga>
- PATTERN_SCELTO è un commento nel CODICE, non un print. Il print() stampa solo i marker del task.
- - Se il task non rientra in nessuna categoria → usa CLASS (fallback).