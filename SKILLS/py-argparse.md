---
id: py-argparse
title: Python CLI with argparse (single file)
keywords: argparse, argomenti, command line, flag, opzioni, parametro da riga di comando
---
# Recipe: CLI with argparse (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import argparse


def main():
    parser = argparse.ArgumentParser(description="{{ PURPOSE }}")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Aggiungi un numero")
    add_parser.add_argument("numero", type=int, help="Numero da aggiungere")

    sum_parser = subparsers.add_parser("sum", help="Somma la lista")

    # Simulazione: add 5, add 3, add 2, poi sum
    numbers = []
    for num in [5, 3, 2]:
        numbers = numbers + [num]

    total = sum(numbers)
    print(f"TOTALE={total}")


if __name__ == "__main__":
    main()
```

RULES:
- - - Use argparse — NEVER parse sys.argv manually, NEVER use input().
- Positional args and `--flags` as the task requests; always help=.
- Convert types with type=int/type=float (argparse strings by default).
- If the task gives example values, hard-code them in main() and compute the result. Do NOT require command-line input at runtime.
- Print the EXACT marker the task requests (e.g. TOTALE=10).