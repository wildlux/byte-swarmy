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
def {{ FUNCTION NAME, taken from the task }}({{ PARAMETERS, taken from the task }}):
    """{{ WHAT IT COMPUTES, one line }}."""
    return {{ COMPUTATION, taken from the task }}


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
- If the PROJECT MAP already contains a function that does the job,
  IMPORT and USE it instead of rewriting it.
- print() the final result so the user sees it.
- NO argparse, NO classes, NO menus, NO threads, NO extra files.
- Use the EXACT numbers, names and quantities from the task. Never
  shrink the problem: "somma i numeri da 1 a 100000" means
  sum(range(1, 100001)), not a small example.
- Quoted items (even single letters like 'a') are string literals.
- Clean text as instructed: palindromes → strip ALL punctuation AND
  spaces, lowercase. Word counts → strip punctuation, lowercase, then
  split on spaces (NEVER join the words into one string).

DONE WHEN:
- project/main.py exists and lint_code passes.
- Running it would print the requested result.
