---
id: py-generators
title: Python generators with yield (single file)
keywords: generatore, generator, yield, iteratore pigro, lazy, stream, sequenza, produrre valori
---
# Recipe: generators with yield (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
def {{ GENERATOR NAME }}({{ PARAMS }}):
    """{{ WHAT IT YIELDS, one value at a time }}"""
    {{ INITIAL STATE }}
    while {{ CONDITION }}:
        yield {{ VALUE }}
        {{ UPDATE STATE }}


def main():
    for value in {{ GENERATOR NAME }}({{ ARGS }}):
        print(value)


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- `yield` is NOT `return`: the function is LAZY, its body runs only
  when iterated. Never `return` inside the loop.
- NEVER build the whole list in memory unless the task explicitly asks
  for it (generators exist to stream).
- Consume with a `for` loop; use `next()` only if the task says so.
- If a total is requested, accumulate during iteration and print the
  exact marker the task requests.
