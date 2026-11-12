---
id: py-http-api
title: Python HTTP API fetch (single file)
keywords: api, http, request, richiesta, rest, get, post, url, urllib, scarica dati
---
# Recipe: HTTP API fetch (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import json
import urllib.error
import urllib.request


def fetch_json(url):
    """Scarica e decodifica JSON dall'URL."""
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    try:
        data = fetch_json("{{ URL }}")
        print(f"{{ MARKER }}")
    except urllib.error.HTTPError as e:
        print(f"ERRORE_HTTP={e.code}")
    except urllib.error.URLError as e:
        print(f"ERRORE_RETE={e.reason}")


if __name__ == "__main__":
    main()
```

RULES:
- - Replace EVERY {{...}} placeholder with real code. Example: `{{ MARKER }}`
  becomes `STATO={resp.status}` so the line reads print(f"STATO={resp.status}")
  — use the EXACT name and value the task requests.
- Default `urllib.request` (requests ONLY if already in the venv).
- ALWAYS set timeout= (network must never hang forever).
- Handle HTTPError and URLError in try/except: print a marker, never
  crash with a traceback.
- JSON decode with json.loads(resp.read().decode("utf-8")).
