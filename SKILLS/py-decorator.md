---
id: py-decorator
title: Python timing decorator (single file)
keywords: decoratore, decoratori, decorator, misura_tempo, timing, tempo di esecuzione, misurare, timer, chrono, wrapper
---
# Recipe: timing decorator (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import time
from functools import wraps


def misura_tempo(func):
    """Stampa i millisecondi di esecuzione di func."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"Tempo di esecuzione: {elapsed_ms:.2f} ms")
        return result
    return wrapper


@misura_tempo
def {{ FUNCTION NAME }}({{ PARAMETERS }}):
    """{{ WHAT IT COMPUTES }}"""
    return {{ COMPUTATION }}


def main():
    result = {{ FUNCTION NAME }}({{ ARGUMENTS }})
    print(f"SOMMA={result}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- The decorator MUST be defined and applied with @ to the target
  function. Never measure with inline time.time() calls.
- Use the EXACT quantity from the task: "somma i numeri da 1 a 100000"
  means `sum(range(1, 100001))` = 5000050000. Never shrink the range.
- Adjust the final print marker to the one the task requests.