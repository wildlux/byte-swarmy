---
id: py-regex
title: Python regex text extraction (single file)
keywords: regex, regular expression, espressioni regolari, pattern, match, findall, estrai, cerca pattern
---
# Recipe: regex extraction (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import re


def main():
    testo = "{{ TEXT }}"
    pattern = r"{{ PATTERN — ALWAYS a raw string }}"
    found = re.findall(pattern, testo)

    for item in found:
        print(item)
    print(f"{{ MARKER }}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Replace EVERY {{...}} placeholder with real code. Example: `{{ MARKER }}`
  becomes `TROVATI={len(found)}` so the line reads print(f"TROVATI={len(found)}")
  — use the EXACT name and value the task requests.
- Patterns are ALWAYS raw strings: `r"\d+"`, never "\d+".
- `re.findall` = all matches; `re.search` = first match (use
  `.group()`); `re.match` anchors at the START of the string.
- Case-insensitive only if the task asks: pass `re.IGNORECASE`.
- Groups: findall returns tuples when the pattern has groups.
- print() the exact markers the task requests.
