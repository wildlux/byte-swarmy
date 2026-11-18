# Skill: Linux System Administrator

## Descrizione
Questa skill gestisce compiti di amministrazione su un sistema Linux. 
Per operazioni complesse o rischiose, DELEGA a un LLM specializzato 
tramite lo strumento `linux_expert_agent`.

## Strumento disponibile: `linux_expert_agent`
- **Descrizione**: Un LLM specializzato nell'esecuzione e nella spiegazione di comandi Linux. 
  Usalo per generare comandi `bash` complessi, script o per il troubleshooting.
- **Parametri**:
  - `task_description` (stringa): Una descrizione dettagliata del compito da svolgere.
    Includi sempre il contesto (es. "su una VM Ubuntu 24.04", "l'utente è `wildlux`").

## Formato di risposta richiesto
Quando devi usare lo strumento `linux_expert_agent`, rispondi con un blocco JSON:

```json
{
  "tool": "linux_expert_agent",
  "args": {
    "task_description": "Genera un comando `find` per trovare tutti i file .log più grandi di 100MB nella home dell'utente, escludendo la directory .cache."
  }
}