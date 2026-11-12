---
id: py-decorator-retry
title: Python retry decorator (single file)
keywords: decoratore, decoratori, decorator, retry, ritenta, ritentare, tentativo, tentativi, riuscire, fallisce
---
# Recipe: retry decorator (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
from functools import wraps


def retry(max_tentativi=3):
    """Ritenta func fino a max_tentativi volte se solleva eccezione."""
    def decoratore(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for tentativo in range(1, max_tentativi + 1):
                try:
                    print(f"TENTATIVO={tentativo}")
                    return func(*args, **kwargs)
                except Exception:
                    if tentativo == max_tentativi:
                        raise
        return wrapper
    return decoratore


_chiamate = {"n": 0}


@retry(max_tentativi=3)
def {{ FUNCTION NAME }}({{ PARAMETERS }}):
    """{{ WHAT IT COMPUTES }}"""
    _chiamate["n"] += 1
    if _chiamate["n"] < 3:
        raise ValueError("fail")
    return {{ COMPUTATION }}


def main():
    result = {{ FUNCTION NAME }}({{ ARGUMENTS }})
    print(f"RISULTATO={result}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Il decorator retry MUST essere definito e applicato con @ alla funzione.
- Stampare TENTATIVO=n ad OGNI tentativo (incluso l'ultimo riuscito).
- La funzione target deve fallire le prime 2 volte e riuscire la 3a.
- Usare un contatore esterno (_chiamate) per simulare il fallimento.
- Use the EXACT quantity from the task per il risultato finale.
- Adjust the final print marker to the one the task requests.