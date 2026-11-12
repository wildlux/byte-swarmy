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
import time


class Timer:
    """Context manager che misura i ms di un blocco with."""
    def __enter__(self):
        self.start = time.perf_counter()  # ACQUIRE: salva come self.*
        return self

    def __exit__(self, exc_type, exc, tb):
        self.end = time.perf_counter()    # RELEASE
        self.elapsed_ms = (self.end - self.start) * 1000
        return False  # NON inghiottire le eccezioni


def main():
    with Timer() as cm:
        result = sum(range(1, 100001))
        print(f"SOMMA={result}")
    # cm.elapsed_ms è disponibile SOLO dopo il with (fuori dal blocco)
    print(f"TEMPO={cm.elapsed_ms:.2f}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- `__exit__` signature EXACTLY: `def __exit__(self, exc_type, exc, tb)`.
- `__exit__` returns False (propagate errors) unless the task says to
  suppress.
- SEMPRE salvare i valori come self.attributo (self.start, self.end,
  self.elapsed_ms) — mai variabili locali, perché main() li legge
  fuori dal with tramite `cm.attributo`.
- Acquire in `__enter__`, release in `__exit__` — never leak the
  resource outside the `with` block.
- Il blocco `with` è l'UNICO modo in cui la risorsa è usata in main.
- Adatta i nomi (Timer, start, end, elapsed_ms) al task, ma mantieni
  il pattern self.* in entrambi i metodi.
