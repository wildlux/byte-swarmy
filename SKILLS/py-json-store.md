---
id: py-json-store
title: Python JSON store (single file)
keywords: json, persistenza, salvataggio, lettura, file, store, database, dati
---
# Recipe: JSON store (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import json
import os

STORE_FILE = "store.json"


def load_store():
    if os.path.exists(STORE_FILE):
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_store(data):
    with open(STORE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def main():
    store = load_store()
    {{ OPERAZIONE: add, search, update, delete }}
    save_store(store)
    print(f"{{ MARKER }}={{ VALUE }}")


if __name__ == "__main__":
    main()
```

RULES:
- - - Use json.load/json.dump for serialization.
- Handle FileNotFoundError gracefully (return empty dict).
- Print the EXACT marker the task requests.