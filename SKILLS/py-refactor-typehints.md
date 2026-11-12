---
id: py-refactor-typehints
title: Python add type hints (single file)
keywords: type hints, annotazioni, tipi, typing, mypy, int, str, list, dict, ->, parametri tipizzati
---
# Recipe: add type hints (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
from typing import List, Optional


def {{ FUNCTION NAME }}({{ PARAM }}: {{ TYPE }}) -> {{ RETURN TYPE }}:
    """{{ WHAT IT COMPUTES }}"""
    {{ BODY }}
    return {{ RESULT }}


def main():
    result = {{ FUNCTION NAME }}({{ ARGUMENTS }})
    print(f"{{ MARKER }}={result}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Add type hints to ALL function parameters and return types.
- Use built-in types (int, str, float, bool, list, dict) when possible.
- Use typing.List, typing.Dict, typing.Optional for complex types.
- Do NOT change the logic or output of the program.
- If a function returns None, annotate -> None.