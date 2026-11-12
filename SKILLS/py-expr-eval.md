---
id: py-expr-eval
title: Python expression evaluator (dict variables) (single file)
keywords: espressione, expression, eval, valuta, parser, variabili, dizionario, calcolo, formula, x * y
---
# Recipe: expression evaluator (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
# Variabili del task
variabili = {"x": 5, "y": 3}

# Espressione del task
espressione = "x * y + 2"

# Valutazione sicura con eval (solo le variabili del dizionario)
risultato = eval(espressione, {"__builtins__": {}}, variabili)
print(f"RISULTATO={risultato}")


if __name__ == "__main__":
    pass
```

RULES:
- - Usa eval() con __builtins__ disabilitati e il dizionario delle
  variabili come globals/locals — MAI eval() senza restrizioni.
- Sostituisci il dizionario e l'espressione con quelli del task.
- Stampa RISULTATO= con il valore calcolato.
- Supporta +, -, *, / e le variabili del dizionario.