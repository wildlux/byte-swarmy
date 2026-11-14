---
id: py-compaction-summary
title: Python compattazione/riassunto testo (single file)
keywords: compattazione, compact, riassunto, summary, sintesi, condensare, comprimere, testo lungo, log, file grande, ridurre, riassumi, sintetizza, comprimi, riduci, condensa, output lungo, testo grande
---
# Recipe: compattazione/riassunto testo (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import re
import sys
from collections import Counter


def compact_text(text: str, max_lines: int = 10) -> str:
    """Compatta il testo: rimuove righe vuote, deduplica, tiene le piu informative."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Deduplica mantenendo l'ordine
    seen = set()
    unique = []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            unique.append(ln)
    # Se troppo lungo, tieni le prime e le ultime + le righe con keyword
    if len(unique) <= max_lines:
        return "\n".join(unique)
    keywords = ["error", "warn", "fail", "def ", "class ", "import", "TODO", "FIXME"]
    important = [ln for ln in unique if any(k in ln for k in keywords)]
    head = unique[:max_lines // 2]
    tail = unique[-(max_lines // 2):]
    result = head + important[:max_lines - len(head) - len(tail)] + tail
    # Deduplica finale
    seen2 = set()
    out = []
    for ln in result:
        if ln not in seen2:
            seen2.add(ln)
            out.append(ln)
    return "\n".join(out[:max_lines])


def word_freq(text: str, top: int = 5) -> list:
    """Frequenza parole (esclude stop words comuni)."""
    stop = {"the", "a", "an", "is", "are", "was", "were", "to", "of",
            "in", "on", "at", "for", "with", "and", "or", "but", "il",
            "la", "le", "lo", "i", "gli", "di", "da", "in", "a", "per",
            "con", "su", "e", "o", "ma", "che", "non", "un", "una"}
    words = re.findall(r"\w+", text.lower())
    c = Counter(w for w in words if w not in stop and len(w) > 2)
    return c.most_common(top)


def main():
    # Leggi testo da stdin o da file
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    print("=== COMPACTED ===")
    print(compact_text(text))
    print("=== TOP WORDS ===")
    for w, n in word_freq(text):
        print(f"  {w}: {n}")


if __name__ == "__main__":
    main()
```

RULES:
- Usa compact_text() per ridurre testo lungo prima di inserirlo nel prompt.
- word_freq() aiuta a identificare i temi dominanti.
- Stampa il marker RISULTATO=... con il numero di righe compattate.
- Non modificare il testo originale: solo produrre una sintesi.