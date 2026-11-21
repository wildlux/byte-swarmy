---
name: current-time
description: Fornisce la data e l'ora correnti locali e in UTC. Usa questa skill ogni volta che l'utente chiede che ore sono, la data di oggi o informazioni temporali.
---

Questa skill ti permette di ottenere l'ora corrente eseguendo lo script `/home/wildlux/Desktop/byte-swarmy/.opencode/skill/current-time/time.sh`.

## Quando usarla
- Quando l'utente chiede "che ore sono?"
- Quando serve una data o un timestamp per un'operazione.
- Quando devi registrare l'ora di un evento.

## Come usarla
Usa il tool `shell` per eseguire il seguente comando:

```
bash /home/wildlux/Desktop/byte-swarmy/.opencode/skill/current-time/time.sh
```

Lo script restituisce un oggetto JSON con due campi:
- `local`: data e ora nel fuso orario locale.
- `utc`: data e ora in UTC.

Usa il campo `local` per rispondere all'utente, a meno che non venga richiesto esplicitamente l'UTC.
