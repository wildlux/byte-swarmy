---
id: py-class-module
title: Python class module with dunder methods (single file)
keywords: classe, class, __len__, __contains__, __iter__, __str__, dunder, protocollo, collezione, collection, stack, pila, coda, metodi, methods, eccezioni, exceptions
---
# Recipe: Python class module (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
class {{ CLASS NAME }}:
    def __init__(self):
        self.items = []

    def {{ METHOD }}(self, {{ PARAMS }}):
        self.items.append({{ PARAMS }})

    def __len__(self):
        return len(self.items)

    def __contains__(self, item):
        return item in self.items

    def __iter__(self):
        return iter(self.items)


def main():
    coll = {{ CLASS NAME }}()
    try:
        {{ FILL IT, e.g. coll.add("a") }}
    except Exception as e:
        print(e)
    # HINT: if the task requires markers (e.g. LEN=3, HAS=True), ADD
    # real print() lines producing EXACTLY them, e.g.:
    # print(f"LEN={len(coll)}")   |   print(f"HAS={'b' in coll}")
    it = iter(coll)
    while True:
        try:
            print(next(it))
        except StopIteration:
            break


if __name__ == "__main__":
    main()
```

RULES:
- Replace EVERY {{...}} placeholder with real code. A placeholder left in the file is a SYNTAX ERROR. NEVER delete an `except` line.
- DRAIN: create the iterator ONCE (`it = iter(coll)`) OUTSIDE the loop, then `next(it)` inside. `next(iter(x))` in a while loop = INFINITE LOOP. Safest drain: `for item in coll: print(item)`.
- MARKERS: read the task and print EVERY marker it requests, EXACTLY as written (LEN=3, HAS=True...). The `# HINT` comments show HOW: turn them into real print() lines. A required marker left out = task FAILS.
- If the task names CUSTOM exceptions, define them as `class NomeError(Exception)` and use THEM in the except lines.
- Keep the two `try/except` blocks intact.
- If the PROJECT MAP already contains the requested class/function, IMPORT it from its file. Redefine only if the map has nothing.
- ALL code stays INSIDE main() — never at module level.