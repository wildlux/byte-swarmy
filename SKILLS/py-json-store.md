---
id: py-json-store
title: JSON persistence CRUD (single file)
keywords: rubrica, agenda, contatti, contacts, json, persistenza, salvataggio, salva, rileggi, rileggere, cerca, search, find, aggiungi, memorizza, store, file
---
# Recipe: JSON persistence (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import json

DATA_FILE = "{{ FILENAME, e.g. rubrica.json }}"


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_data(items):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def main():
    items = load_data()
    {{ APPEND EVERY RECORD, e.g. items.append({"nome": "Mario Rossi", "numero": "12345"}) }}
    save_data(items)
    items = load_data()  # re-read to prove persistence
    query = "{{ SEARCH TERM }}"
    for record in items:
        if query in record["{{ FIELD, e.g. nome }}"]:
            print(f"TROVATO={record['{{ VALUE FIELD }}']}")


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Save to the EXACT filename in the task (current working directory).
- Search is a SUBSTRING match: `query in record[field]` — "Mario"
  matches "Mario Rossi". Exact equality only if the task says exact.
- print() the exact marker the task requests (e.g. TROVATO=12345).
