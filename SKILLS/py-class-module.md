---
id: py-class-module
title: Python class module with dunder methods (single file)
keywords: classe, class, __len__, __contains__, __iter__, __str__, dunder, protocollo, collezione, collection, stack, pila, coda, metodi, methods, eccezioni, exceptions
---
# Recipe: Python class module (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is — the ONLY
exception: `# HINT` lines, to turn into real print() lines when the
task requires the markers shown):
```python
class {{ CLASS NAME }}:
    def __init__(self):
        self.items = []

    def {{ METHOD NAME, e.g. add }}(self, {{ PARAMS }}):
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
    # DRAIN sicuro: UN iteratore solo, poi next(it) finché StopIteration.
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
- ONE file only: project/main.py. Standard library only.
- Replace EVERY {{...}} placeholder with real code. A placeholder left
  in the file is a SYNTAX ERROR. NEVER delete an `except` line: if you
  open a `try:` you MUST keep its `except` block.
- DRAIN pattern: create the iterator ONCE (`it = iter(coll)`) OUTSIDE
  the loop, then `next(it)` inside it. `next(iter(x))` INSIDE a while
  loop creates a FRESH iterator every turn → never raises
  StopIteration → INFINITE LOOP. The safest drain is plain
  `for item in coll: print(item)`.
- MARKERS: read the task and print EVERY marker it requests, EXACTLY
  as written (LEN=3, HAS=True, each element per line...). The `# HINT`
  comments in the template show HOW: turn them into real print()
  lines when the task requires those values. A required marker left
  out = the task FAILS the runtime check.
- If the task names CUSTOM exceptions (e.g. StackOverflowError),
  define them as `class NomeError(Exception)` and use THEM in the
  except lines instead of Exception.
- Keep the two `try/except` blocks of the template intact.
- If the PROJECT MAP already contains the requested class/function,
  IMPORT it from its file (e.g. `from utils import Statistiche`) and
  USE it — do NOT redefine it. Redefine only if the map has nothing.
- ALL code stays INSIDE main() — never at module level.
- If you print len(coll) or call len(self), the class MUST implement
  __len__. If the task doesn't ask the length, drop that print.
- Quoted items are STRING literals: `add("a")` appends the string "a",
  NEVER a variable named a. Write every item quoted.
- The methods shown in the template are the usual dunders: implement
  ALL and ONLY the methods the task names, including peek/pop if asked.
- Custom exceptions subclass Exception; handle them in main with
  try/except and print the exact marker the task requests.
- If the task asks a different storage (capacity, dict), adapt __init__
  but keep every requested method.
