---
id: py-inheritance
title: Python inheritance (single file)
keywords: ereditarietà, eredita, ereditare, sottoclasse, subclass, classe base, base class, super, override, polymorfismo
---
# Recipe: inheritance (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
class {{ BASE NAME }}:
    def {{ METHOD }}(self):
        return {{ BASE COMPUTATION }}


class {{ CHILD NAME }}({{ BASE NAME }}):
    def {{ METHOD }}(self):
        result = super().{{ METHOD }}()
        {{ EXTEND / MODIFY result }}
        return result


def main():
    child = {{ CHILD NAME }}()
    print(f"{{ MARKER }}")


if __name__ == "__main__":
    main()
```

RULES:
- - Replace EVERY {{...}} placeholder with real code. Example: `{{ MARKER }}`
  becomes `RISULTATO={child.metodo()}` so the line reads
  print(f"RISULTATO={child.metodo()}") — use the EXACT name and value
  the task requests.
- The child class MUST inherit: `class Child(Base)`.
- To extend a method, call `super().method()` FIRST, then add.
- Override = SAME method name, SAME parameters.
- In main instantiate the CHILD class, never the base.
- print() the exact markers the task requests.
