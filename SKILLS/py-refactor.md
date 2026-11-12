---
id: py-refactor
title: Python refactoring (rename, extract, typehints, async, modularize) (single file)
keywords: refactoring, rinomina, rename, estrai, extract, type hints, annotazioni, async, await, asincrono, modularize, moduli, separa, split, riuso, multi-file
---
# Recipe: refactoring (single file)

STEPS (follow in order):
1. Leggi il task e scegli UNA operazione dalla tabella DECISION TREE.
2. Create project/main.py using the TEMPLATE dell'operazione scelta.
3. 4. done=true with a one-line result.

## DECISION TREE

| Se il task menziona... | Operazione | Template |
|---|---|---|
| rinomina, rename, simbodo | RENAME | A |
| estrai, extract, metodo | EXTRACT | B |
| type hints, annotazioni, tipi | TYPEHINTS | C |
| async, await, asincrono | ASYNC | D |
| modularize, separa, split, moduli | MODULARIZE | E |

## TEMPLATE A — RENAME
```python
def {{ NEW NAME }}({{ PARAMS }}):
    """{{ WHAT IT COMPUTES }}"""
    return {{ COMPUTATION }}

def main():
    result = {{ NEW NAME }}({{ ARGS }})
    print(f"{{ MARKER }}={result}")

if __name__ == "__main__":
    main()
```

## TEMPLATE B — EXTRACT
```python
def {{ EXTRACTED NAME }}({{ PARAMS }}):
    """{{ WHAT IT COMPUTES }}"""
    {{ BODY }}
    return {{ RESULT }}

def main():
    result = {{ EXTRACTED NAME }}({{ ARGS }})
    print(f"{{ MARKER }}={result}")

if __name__ == "__main__":
    main()
```

## TEMPLATE C — TYPEHINTS
```python
from typing import List, Optional

def {{ NAME }}({{ PARAM }}: {{ TYPE }}) -> {{ RETURN }}:
    """{{ WHAT }}"""
    {{ BODY }}
    return {{ RESULT }}

def main():
    result = {{ NAME }}({{ ARGS }})
    print(f"{{ MARKER }}={result}")

if __name__ == "__main__":
    main()
```

## TEMPLATE D — ASYNC
```python
import asyncio

async def {{ NAME }}({{ PARAMS }}):
    """{{ WHAT }} (asincrona)."""
    await asyncio.sleep(0)
    return {{ RESULT }}

async def main():
    result = await {{ NAME }}({{ ARGS }})
    print(f"{{ MARKER }}={result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## TEMPLATE E — MODULARIZE
```python
# Responsabilità 1
def {{ FUNC1 }}({{ PARAMS1 }}):
    """{{ WHAT1 }}"""
    return {{ RESULT1 }}

# Responsabilità 2
def {{ FUNC2 }}({{ PARAMS2 }}):
    """{{ WHAT2 }}"""
    return {{ RESULT2 }}

def main():
    r1 = {{ FUNC1 }}({{ ARGS1 }})
    r2 = {{ FUNC2 }}({{ ARGS2 }})
    print(f"{{ MARKER1 }}={r1}")
    print(f"{{ MARKER2 }}={r2}")

if __name__ == "__main__":
    main()
```

RULES:
- Scegli il PRIMO template che matcha. Usa SOLO quello.
- - Do NOT change the output of the program.