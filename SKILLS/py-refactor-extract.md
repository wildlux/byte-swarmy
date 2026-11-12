---
id: py-refactor-extract
title: Python extract method (single file)
keywords: extract, estrai, metodo, funzione, refactoring, blocco, separa, riuso, modulo
---
# Recipe: extract method (single file)

STEPS (follow in order):
1. Identify the block of code to extract.
2. Create project/main.py using the TEMPLATE below.
3. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
4. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
def {{ EXTRACTED FUNCTION NAME }}({{ PARAMS }}):
    """{{ WHAT IT COMPUTES }}"""
    {{ BODY OF THE BLOCK }}
    return {{ RESULT }}


def main():
    # Original code with the block replaced by a call
    result = {{ EXTRACTED FUNCTION NAME }}({{ ARGUMENTS }})
    print(f"{{ MARKER }}={result}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- The extracted function MUST have the same behavior as the original block.
- All variables used in the block must be passed as parameters.
- The original code in main() must call the extracted function.
- Do NOT change the output of the program.