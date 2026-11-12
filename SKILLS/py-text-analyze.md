---
id: py-text-analyze
title: Python text analysis (word frequency + palindrome) (single file)
keywords: frequenza, frequency, conta parole, word count, parole ripetute, palindromo, palindrome, analisi testo, split
---
# Recipe: text analysis — word frequency + palindrome (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import re


def is_palindromo(frase):
    """Palindromo: SOLO lettere, spazi e punteggiatura spariti."""
    cleaned = "".join(c for c in frase.lower() if c.isalpha())
    return cleaned == cleaned[::-1]


def conta_parole(frase):
    """Frequenza: PRIMA estrazione parole, POI conteggio."""
    words = re.findall(r"[a-zàèéìòù]+", frase.lower())
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def main():
    frase = "{{ TEXT }}"
    print(f"PALINDROMO={is_palindromo(frase)}")
    counts = conta_parole(frase)
    # se il task chiede la parola più frequente, stampa:
    # print(f"PIU_FREQUENTE={max(counts, key=counts.get)}")


if __name__ == "__main__":
    main()
```

RULES:
- - - Word extraction happens FIRST with regex `[a-zàèéìòù]+`: punctuation and spaces disappear BY CONSTRUCTION — never count on the whole phrase string.
- Palindrome: keep ONLY letters (isalpha), lowercase, then compare with the reverse.
- Most frequent word = max(counts, key=counts.get) — a REAL word from the split, never the whole phrase. If the task asks a specific marker, print it EXACTLY (uncomment and adapt the commented line, using the marker NAME the task requests).