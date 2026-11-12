---
id: py-arch-decision
title: Python architectural decision (pattern choice) (single file)
keywords: architettura, architecture, pattern, design, scelta, trade-off, struttura, progettazione, sistema
---
# Recipe: architectural decision (single file)

STEPS (follow in order):
1. Leggi il task e scegli UN pattern dalla tabella DECISION TREE.
2. Stampa PATTERN_SCELTO=<nome> e TRADEOFF=<motivazione in 1 riga>.
3. Create project/main.py using the TEMPLATE below.
4. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
5. done=true with a one-line result.

## DECISION TREE (scegli il PRIMO che matcha)

| # | Se il task menziona... | Pattern | Perché |
|---|---|---|---|
| 1 | file grande, streaming, riga per riga, memoria limitata | GENERATOR | O(1) memoria |
| 2 | risorsa da aprire/chiudere, with, cleanup | CONTEXT_MANAGER | Cleanup automatico |
| 3 | wrappare, misurare, ritentare, loggare, cache | DECORATOR | Riusabile |
| 4 | thread, concorrenza, producer-consumer, lock | THREADING | Thread-safe |
| 5 | stato condiviso, CRUD, persistenza, dati | CLASS | Stato esplicito |
| 6 | CLI, argomenti, flag, sottocomandi | ARGPARSE | Standard |
| fallback | nessuno dei precedenti | CLASS | Più generico |

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
- ONE file only: project/main.py. Standard library only.
- PRIMA di scrivere codice, la prima riga del file DEVE essere:
  # PATTERN_SCELTO=<nome>  (es. GENERATOR, CONTEXT_MANAGER, DECORATOR,
  THREADING, CLASS, ARGPARSE)
- La seconda riga DEVE essere:
  # TRADEOFF=<motivazione in 1 riga>
- Poi il codice del pattern scelto.
- Il marker PATTERN_SCELTO deve essere il primo output su stdout? NO:
  PATTERN_SCELTO è un commento nel CODICE, non un print. Il print()
  stampa solo i marker del task (es. COUNT=5, SOMMA=15).
- Replace EVERY {{...}} placeholder with real code.
- Se il task non rientra in nessuna categoria → usa CLASS (fallback).