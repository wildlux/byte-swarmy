# Test Funzionali BYTE-SWARMY

File: `test_functional_swarm.py` — 584 righe, 7 test, pronto all'uso.

## Come usare

### Setup (una tantum)
```bash
cd ~/Desktop/byte-swarmy

# Copia il file in tests/
cp /path/to/download/test_functional_swarm.py tests/test_functional_swarm.py
chmod +x tests/test_functional_swarm.py
```

### Esecuzione
```bash
# 1. Avvia orchestrator se non attivo
./bswarm start --orch

# 2. Pulisci task vecchi
./bswarm queue cleanup

# 3. Esegui tutti i 7 test (~20 min)
python3 tests/test_functional_swarm.py

# oppure esegui solo un test
python3 tests/test_functional_swarm.py --test 4   # solo Fibonacci

# lista test disponibili
python3 tests/test_functional_swarm.py --list
```

## Cosa testano i 7 test

| # | Nome | Cosa verifica |
|---|---|---|
| 1 | `add(a,b)` | Funzione semplice: positivi, negativi, grandi |
| 2 | `multiply` + `divide` | Multiple funzioni + gestione errore (ValueError su /0) |
| 3 | Classe `Counter` | OOP, stato isolato tra istanze |
| 4 | `fib(n)` | Algoritmo: 8 casi + edge negativo |
| 5 | Script con file I/O | Side effect: script eseguito, file creato, contenuto verificato |
| 6 | `filter_even` | Lista: edge cases (vuota, zero, negativi pari) |
| 7 | `reverse_string` | Stringhe: edge cases (vuota, 1 char, palindrome) |

Ogni test verifica:
- ✅ File creato in `project/` (accetta `main.py` come fallback)
- ✅ Codice sintatticamente valido (AST parsing)
- ✅ Funzioni/classi richieste presenti
- ✅ Esecuzione senza errori
- ✅ Comportamento corretto su casi edge

## Risultati attesi con `qwen2.5-coder:1.5b`

- **6/7 (86%)** tipicamente
- Test 5 (file I/O) è il più difficile per il modello piccolo
- Codice prodotto è di buona qualità (gestione errori, casi base, algoritmi)

## Integrazione GUI (opzionale)

Per lanciare i test dalla GUI di byte-swarmy, aggiungi un pulsante in `GUI/main_window.py`:

```python
# In GUI/main_window.py, aggiungi un pulsante "Run Functional Tests"
# che lancia:
import subprocess
result = subprocess.run(
    ["python3", "tests/test_functional_swarm.py"],
    capture_output=True, text=True, cwd=ROOT
)
# Mostra result.stdout in un dialog
```

## Output di esempio

```
======================================================================
  🐝 TEST FUNZIONALI BYTE-SWARMY — QUALITÀ DEL CODICE PRODOTTO
======================================================================

[00:14:42] --- Funzione semplice (add) ---
[00:14:42]   → status: done
[00:14:42]   ✓ add(2,3)=5, add(-1,1)=0, add(100,200)=300

...

======================================================================
  RIASSUNTO
======================================================================
  ✓ PASS  Funzione semplice (add)
  ✓ PASS  Multiple funzioni + error handling
  ✓ PASS  Classe con stato (Counter)
  ✓ PASS  Algoritmo (Fibonacci)
  ✗ FAIL  Script con file I/O
  ✓ PASS  List manipulation (filter_even)
  ✓ PASS  String manipulation (reverse)

  6/7 test passati (86%)
  ⚠ Swarm funziona ma con qualche limite
======================================================================
```
