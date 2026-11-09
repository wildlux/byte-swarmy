# Diario di bordo SML — BYTE-SWARMY

Questa cartella contiene i log di ogni tentativo di test sui modelli SML.
Ogni file è un JSON con nome: `test_<data>_<ora>_<modello>_<livello>.json`

Campi:
- modello: nome del modello Ollama
- quantizzazione: es. Q4_K_M
- dimensione_gb: grandezza approssimativa
- prompt_versione: versione del system prompt usata (es. "v2", "v3")
- livello: 1, 2 o 3
- prompt_inviato: il prompt completo mandato al modello
- output_grezzo: risposta completa del modello
- output_parsato: dizionario parsato (se riuscito)
- esito: "promosso" | "bocciato" | "errore"
- punteggio: 0.0-1.0
- errore: messaggio di errore se bocciato
- timestamp: data e ora
- note_miglioramento: osservazioni su cosa cambiare nel prossimo tentativo

Uso:
- Ogni test aggiunge un nuovo file qui
- Per analizzare: leggere i file con esito "bocciato" per capire pattern ricorrenti
- Per migliorare il prompt: confrontare "promosso" vs "bocciato" sullo stesso modello

Esempio di struttura:
{
  "modello": "qwen2.5:1.5b",
  "quantizzazione": "Q4_K_M",
  "dimensione_gb": 0.99,
  "prompt_versione": "v3",
  "livello": 1,
  "prompt_inviato": "...",
  "output_grezzo": "...",
  "output_parsato": {...},
  "esito": "promosso",
  "punteggio": 1.0,
  "errore": null,
  "timestamp": "2026-11-09T17:30:00",
  "note_miglioramento": "Il modello segue bene il formato testo strutturato v3"
}
