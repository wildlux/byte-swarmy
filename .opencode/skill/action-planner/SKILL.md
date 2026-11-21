---
name: action-planner
description: Pianificatore di azioni per richieste non chiare: quando l'utente chiede qualcosa di ambiguo o poco implementabile, chiede a schermo (chat/GUI) i dettagli necessari prima di pianificare ed eseguire. Usa quando la richiesta non è chiara, multi-interpretabile, o confligge con l'obiettivo corrente.
---

# Action Planner — pianificatore di azioni per richieste non chiare

Flusso di fallback del planner quando l'input utente non è implementabile o è
ambiguo: **chiedere → chiarire → pianificare → eseguire**.

## 1. Trigger

- L'utente chiede qualcosa di vago ("fai una cosa", "vorrei qualcosa di nuovo").
- La richiesta ha più interpretazioni plausibili.
- La richiesta confligge con l'obiettivo attivo (goal Middle Senior, roadmap
  SLOT, radar).
- L'utente esprime un dubbio o un confine ("mi sa che...") senza decisione.

## 2. Workflow

1. **Classificare l'ambiguità**: livello (alto/medio/basso) e dimensione
   (obiettivo, deliverable, vincoli, contesto, criteri di successo).
2. **Emettere domande mirate** (una dimensione per domanda, una sola fonte di
   verità: l'utente).
3. **Canale di risposta**: chat (`question` tool) o GUI (pannello/Pannello
   Plancia) a seconda della superficie attiva — "a schermo".
4. **Ricevere risposta** → aggiornare piano (`todo.md`) → trasformare in
   task (SLOT) → eseguire.
5. **Fallback**: se l'utente non risponde in modo utile → proporre piano
   default con criteri misurabili, marcare la voce come `pianificata`.

## 3. Relazione con il sistema esistente

- `CORE/clarifier.py` (clarify loop) continua a gestire le domande di task.
- Questa skill gestisce il **pianificatore di azioni**: da qui parte l'azione
  stessa (qui nasce il piano; lì i dubbi procedurali).
- Vincoli: una voce per sessione, planner deterministico, nessuna generazione
  monolitica.

## 4. Quality gates

- Le domande devono essere risponte prima di qualsiasi azione.
- Nessuna azione su codice/progetto senza piano corrente.
- Se l'utente chiede "creare direttamente l'applicazione", il planner converte
  la richiesta in user story con deliverable e criteri d'accept.
