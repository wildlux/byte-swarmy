---
name: project-radiography
description: Radiografia fredda di un progetto (zero LLM) prima di una campagna di refactoring — censimento file per tipo, salute di compilazione, god-file, marker di debito, build system, code_map. Usa quando si aggiunge un nuovo progetto target, si vuole capire "com'è fatto" un codebase, o prima di popolare il debt ledger.
---

# Radiografia progetto (fredda, zero LLM)

Analisi STATICA e deterministica di un codebase prima di toccarlo:
il risultato alimenta il debt ledger (item con premise reale) e il
code_map (context per l'LLM). Tutto qui sotto è lavoro freddo —
compatibile con il limite 60°C — ed è ripetibile a ogni campagna.

Esempio reale (prismalux, 2026-11-16): 312 cpp · 180 h · 164 py ·
0 errori di compilazione · 6 god-file >100KB · 123 marker debito.

## 1. Censimento per tipo

```bash
cd <progetto>
find . -type f -not -path "*/.git/*" | sed 's/.*\.//' | sort | \
    uniq -c | sort -rn | head -10
```

## 2. Distribuzione per directory della lingua principale

```bash
# dove vivono davvero i file della lingua dominante
find . -name "*.py" -not -path "*/.git/*" | sed 's|^\./||; s|/[^/]*$||' | \
    sort | uniq -c | sort -rn | head -12
```

## 3. Salute di compilazione (la prima verifica, gratis)

```bash
# Python: tutto l'albero, zero LLM
.venv/bin/python -m compileall -q . 2>&1 | grep -cE "Error|error"
```
Per C++/Qt: NON lanciare il build completo a freddo (carico pesante —
312 file = 49→78°C in 107s misurati). Notare SOLO il build system
(CMake/qmake) e il numero di unità: la strategia di verifica
(ccache, -j limitato, build stadiale) va decisa PRIMA di registrare
item C++ nel ledger.

## 4. God-file (i monoliti da splittare)

```bash
find . -name "*.cpp" -not -path "*/.git/*" -exec ls -la {} \; | \
    awk '{print $5, $9}' | sort -rn | head -6
# soglia d'allerta empirica: >100KB un singolo file sorgente
```

## 5. Marker di debito (dove il codice ha paura di se stesso)

```bash
grep -rn "TODO\|FIXME\|XXX\|HACK" --include="*.py" --include="*.cpp" \
    --exclude-dir=.git -l . | sed 's|^\./||; s|/[^/]*$||' | \
    sort | uniq -c | sort -rn | head -8
```

## 6. Code_map per il contesto del ledger

```bash
# dalla root di byte-swarmy (stdlib ast + SQLite, fail-open)
.venv/bin/python -c "from CORE import code_map; \
    print(code_map.rebuild('project/<nome>'))"
```

## 7. Registra gli item veri nel debt ledger (per-progetto)

```bash
.venv/bin/python -m CORE.debt_ledger add --root project/<nome> \
    --kind refactor --file <file/dir colpito> \
    --title "Cosa" --rationale "Dato misurato dalla radiografia" \
    --priority 1|2|3 --effort xs|s|m|l
```

REGLA: un item entra nel ledger SOLO con una premessa misurata
(numberi della radiografia), mai "mi sembra". Il vincolo di verifica
(build? test?) va scritto nel rationale — se la verifica richiede
carico pesante, l'item resta in coda finché la strategia di build
non esiste.

## 8. Ordine di esecuzione della campagna

1. Item xs/s a verifica fredda (py_compile, grep, rinomie) → subito
2. Item m/l C++ → SOLO dopo strategia di build termicamente sicura
3. Un item per sessione, stadiale (`next` decide, mai l'idea)
