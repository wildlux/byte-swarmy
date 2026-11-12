---
id: py-context-manager
title: Python context manager (__enter__/__exit__) (single file)
keywords: context manager, with, __enter__, __exit__, risorsa, gestione risorse, apertura e chiusura
---
# Recipe: context manager (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
class {{ CM NAME }}:
    def __enter__(self):
        {{ ACQUIRE THE RESOURCE, e.g. self.f = open(...) }}
        return self

    def __exit__(self, exc_type, exc, tb):
        {{ RELEASE THE RESOURCE, e.g. self.f.close() }}
        return False  # NON inghiottire le eccezioni


def main():
    with {{ CM NAME }}() as cm:
        {{ USE THE RESOURCE }}
        print({{ MARKER }})


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- `__exit__` signature EXACTLY: `def __exit__(self, exc_type, exc, tb)`.
- `__exit__` returns False (propagate errors) unless the task says to
  suppress.
- Acquire in `__enter__`, release in `__exit__` — never leak the
  resource outside the `with` block.
- The `with` statement is the ONLY way the resource is used in main.
