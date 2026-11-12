---
id: py-refactor-modularize
title: Python modularize (split monolith into modules) (single file)
keywords: modularize, moduli, separa, split, import, riuso, responsabilità, monolite
---
# Recipe: modularize (single file simulation)

STEPS (follow in order):
1. Identify the responsibilities in the monolithic code.
2. Create project/main.py using the TEMPLATE below.
3. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
4. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
# Modulo 1: {{ RESPONSIBILITY 1 }}
def {{ FUNC 1 }}({{ PARAMS 1 }}):
    """{{ WHAT IT COMPUTES 1 }}"""
    return {{ RESULT 1 }}


# Modulo 2: {{ RESPONSIBILITY 2 }}
def {{ FUNC 2 }}({{ PARAMS 2 }}):
    """{{ WHAT IT COMPUTES 2 }}"""
    return {{ RESULT 2 }}


def main():
    r1 = {{ FUNC 1 }}({{ ARGS 1 }})
    r2 = {{ FUNC 2 }}({{ ARGS 2 }})
    print(f"{{ MARKER 1 }}={r1}")
    print(f"{{ MARKER 2 }}={r2}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Identify at least 2 distinct responsibilities in the original code.
- Each function must have a single responsibility (SRP).
- Do NOT change the output of the program.
- Use clear function names that describe the responsibility.