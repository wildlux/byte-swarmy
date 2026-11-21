---
name: skill-searcher
description: Motore di ricerca delle skill operative (.opencode/skill/*): indicizza nome+descrizione+corpo delle skill e risponde a query (task/argomento) con la lista rilevante. Usa quando le skill aumentano o prima di assegnare un task a un Worker, per scegliere la skill giusta.
---

# Skill Searcher — motore di ricerca delle skill

Flusso: **query → indice → ranking → risultato**.

## 1. Scopo
- Come le skill crescono, il planner deve sapere **quali skill cercare** per un task.
- Indicizzazione deterministica di `name` + `description` (+ corpo) di ogni
  `SKILL.md` in `.opencode/skill/`.

## 2. Indice
- Fonti: `.opencode/skill/*/SKILL.md` (frontmatter `name`, `description`; body).
- Tokenizzazione: parole chiave minuscole, stopword base.
- Ranking: corrispondenza lessicografica/tipologica (task → skill).

## 3. Query e selezione
1. Ricevere task/argomento dal planner.
2. Eseguire ricerca → restituire skill candidate (top-k).
3. Verificare rilevanza; se nessuna → nessuna skill (task diretto).

## 4. Quality gates
- Indice riletto a ogni ricerca (le skill cambiano).
- Nessuna skill scelta senza corrispondenza rilevante.

## 5. Comandi chiave
```bash
ls /home/wildlux/Desktop/byte-swarmy/.opencode/skill/*/SKILL.md
grep -l "descrizione" /home/wildlux/Desktop/byte-swarmy/.opencode/skill/*/SKILL.md
```

## 6. Display — elenco completo per la Plancia di comando

- Il searcher espone l'**elenco completo** delle skill (mode `all`) per la UI
  (Plancia di comando / Control Center): `name`, `description`, path.
- L'utente chiede (chat o GUI): "mostrami tutte le skill" → il searcher
  restituisce la lista; la Plancia deve renderizzarla nel pannello dedicato.
- Il pannello della Plancia legge le SKILL.md dal filesystem (zero LLM) e
  mostra nome + descrizione; il searcher resta l'indicizzatore per task→skill.
- Nessuna skill scelta senza corrispondenza rilevante.
