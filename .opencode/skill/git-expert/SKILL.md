---
name: git-expert
description: Skill per l'uso di Git (status, diff, log, branch, commit, push, merge, stash) con operazioni sicure e una alla volta. Usa quando l'utente chiede operazioni git o workflow di versionamento.
---

# Git Expert — skill per l'uso di Git

Flusso: **scoperta → operazione → verifica**.

## 1. Scopo

- Consultare lo stato del repository in modo deterministico (status, diff, log).
- Eseguire commit/branch/push/merge con sicurezza (niente force push senza conferma).

## 2. Workflow

1. `git status` / `git diff` / `git log --oneline` per contesto.
2. Eseguire UNA sola operazione Git alla volta.
3. Verificare con `git status` e `git diff` dopo l'operazione.

## 3. Quality gates

- Commit atomici con message descrittivi.
- Push solo su branch pushata; nessun force push senza conferma esplicita.

## 4. Comandi chiave

```bash
git status --short
git diff --stat
git log --oneline -5
git add -A && git commit -m "msg"
git push origin main
```
