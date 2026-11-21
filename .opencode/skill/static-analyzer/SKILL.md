---
name: static-analyzer
description: Skill per eseguire e orchestrare le analisi statiche di codice (lint style, pyflakes/nomi, security scan, validazione referenze, compile) prima di modificare o eseguire il codice. Usa quando serve un gate statico pre-modifica o prima di una campagna di refactoring.
---

# Static Analyzer — gate di analisi statica

Flusso: **gate statico → modifica → verifica**.

## 1. Scopo
- Eseguire e orchestrare le verifiche statiche del progetto prima di modificare codice.
- Garantire pulizia (0 errori / 0 warning) e sicurezza prima delle modifiche.

## 2. Workflow
1. `tools/lint_style.py` (stile, leggibilità, theme guard).
2. `pyflakes`/nomi indefiniti (gate Zero Warning).
3. `tools/security_scan.py` (baseline errori).
4. `tools/validate_refs.py` (validazione referenze interne).
5. `compileall` (sintassi).
6. Test mirati (subset) prima della suite completa.

## 3. Quality gates
- 0 errori / 0 warning prima di ogni modifica rilevante.
- Nessuna modifica al codice senza gate statico superato (o sua registrazione).

## 4. Comandi chiave
```bash
.venv/bin/python tools/lint_style.py
.venv/bin/python -m pyflakes CORE/ GUI/ tools/ scripts/ SAFETY/ INTENT/ tests/
.venv/bin/python tools/security_scan.py
.venv/bin/python tools/validate_refs.py
.venv/bin/python -m compileall -q CORE GUI tools scripts SAFETY INTENT tests
```
