---
id: py-argparse
title: Python CLI with argparse (single file)
keywords: argparse, argomenti, command line, flag, opzioni, parametro da riga di comando
---
# Recipe: CLI with argparse (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import argparse


def main():
    parser = argparse.ArgumentParser(description="{{ PURPOSE }}")
    parser.add_argument("{{ POSITIONAL NAME }}", type={{ TYPE }},
                        help="{{ WHAT IT IS }}")
    parser.add_argument("--{{ FLAG NAME }}", type={{ TYPE }},
                        default={{ DEFAULT }}, help="{{ WHAT IT DOES }}")
    args = parser.parse_args()

    result = {{ COMPUTATION using args.* }}
    print(f"{{ MARKER }}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Replace EVERY {{...}} placeholder with real code. Example: `{{ MARKER }}`
  becomes `RISULTATO={result}` so the line reads print(f"RISULTATO={result}")
  — use the EXACT name and value the task requests.
- Use argparse — NEVER parse sys.argv manually, NEVER use input().
- Positional args and `--flags` as the task requests; always help=.
- Convert types with type=int/type=float (argparse strings by default).
- If the task ALSO gives example values to compute, hard-code a
  fallback ONLY if args are absent — check with
  `if args.POSIZIONALE is None` pattern or default values.
