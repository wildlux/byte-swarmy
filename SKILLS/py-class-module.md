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

TEMPLATE (keep every line that has no {{...}} exactly as-is):
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
    except {{ ERROR CLASS }} as e:
        print(e)
    {{ ONLY IF THE TASK ASKS THE LENGTH: print(f"LEN= {len(coll)}") — remove this line otherwise }}
    try:
        {{ DRAIN IT, e.g. while True: print(coll.pop()) }}
    except {{ ERROR CLASS }} as e:
        print(e)


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
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
