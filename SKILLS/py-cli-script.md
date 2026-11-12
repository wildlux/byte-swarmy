---
id: py-cli-script
title: Python CLI script (single file)
keywords: script, cli, console, terminale, input, output, main, funzione
---
# Recipe: CLI script (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
def {{ FUNCTION NAME }}({{ PARAMETERS }}):
    """{{ WHAT IT COMPUTES }}."""
    return {{ COMPUTATION }}


def main():
    # {{ HOW THE INPUT ARRIVES: hard-coded, input(), or argv }}
    {{ READ OR DEFINE INPUTS }}
    result = {{ FUNCTION NAME }}({{ ARGUMENTS }})
    print({{ HUMAN-READABLE OUTPUT, e.g. f"Risultato: {result}" }})


if __name__ == "__main__":
    main()
```

RULES:
- - - Quoted items (even single letters like 'a') are STRING literals, never variable names.
- Use the EXACT numbers, names and ranges from the task.
- print() exactly the markers the task requests (e.g. SOMMA=...).