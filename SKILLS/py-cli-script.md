---
id: py-cli-script
title: Simple Python console script (single file)
keywords: script, cli, console, command line, python, program, software, sommare, somma, sum, add, subtract, multiply, divide, calculate, calcolo, numeri, numbers, convert, convertitore, fibonacci, factorial, pari, dispari, even, odd, prime
---
# Recipe: single-file Python console script

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. Call lint_code("main.py") to verify it compiles.
4. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
def {{ FUNCTION NAME, e.g. somma }}({{ PARAMETERS, e.g. a, b }}):
    """{{ WHAT IT COMPUTES, one line }}."""
    return {{ COMPUTATION, e.g. a + b }}


def main():
    # {{ HOW THE INPUT ARRIVES: hard-coded, input(), or argv }}
    {{ READ OR DEFINE INPUTS }}
    result = {{ FUNCTION NAME }}({{ ARGUMENTS }})
    print({{ HUMAN-READABLE OUTPUT, e.g. f"Risultato: {result}" }})


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- print() the final result so the user sees it.
- NO argparse, NO classes, NO menus, NO threads, NO extra files.

DONE WHEN:
- project/main.py exists and lint_code passes.
- Running it would print the requested result.
