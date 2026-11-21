---
name: skill-lister
description: Elenca tutte le skill operative disponibili (.opencode/skill/*) e suggerisce quella pertinente. Usata come trigger quando l'utente scrive 'chiocciola'.
---

# Skill Lister — elenco e suggerimento skill

Flusso: **trigger → lista → suggerimento**.

## 1. Scopo

- Quando l'utente scrive "chiocciola", mostrare tutte le skill disponibili.

## 2. Workflow

1. Leggere `.opencode/skill/*/SKILL.md`.
2. Elencare name + description.
3. Suggerire la skill più pertinente alla richiesta successiva.

## 3. Quality gates

- Lista completa: nessuna skill nascosta.

## 4. Comandi chiave

```bash
ls /home/wildlux/Desktop/byte-swarmy/.opencode/skill/*/SKILL.md
```
