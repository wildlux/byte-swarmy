# 🔍 Prompt Lint (D1)

_Misura offline del prompt effettivo. Zero LLM, zero rete. A/B live resta 🔒 bloccato termicamente._

**Famiglia**: `compact` — **source**: `Worker._build_system(family=compact)` — **status**: `OK`

| Metrica | Valore |
|---|---|
| Caratteri | 1302 |
| Parole | 187 |
| Righe | 35 |
| Frasi | 52 |
| Parole/frase (media, max) | 3.6, 11 |
| Regole numerate | 7 |
| Tool esposti | 13 |
| Token non-inglesi | 5 (2.7%) |
| Una azione per turno | sì |
| Marker offensivi | 0 |

| Check | Esito | Dettaglio |
|---|---|---|
| `instructions` | ✅ | 7 regole numerate (min 5) |
| `exposed_tools` | ✅ | 13 tool esposti (max 16) |
| `avg_sentence` | ✅ | media 3.6 parole/frase (max 20) |
| `max_sentence` | ✅ | frase piu lunga 11 parole (max 35) |
| `non_english` | ✅ | quota non-inglese 2.7% (max 5%) |
| `one_action_per_turn` | ✅ | una azione/turno + formato JSON esplicito |
| `tone` | ✅ | nessun marcatore offensivo |

## Conclusione sull'ipotesi

- **Struttura**: regole numerate, tool limitati e formato JSON esplicito sono misurabili e presenti (✅ sopra).
- **Tono**: i marcatori offensivi sono 0: il tono non è un fattore di struttura e non va introdotto.
- **Lingua**: le istruzioni sono in inglese; il residuo non-inglese sono commenti nei tool (`# righe`, `# se dubbi`).
