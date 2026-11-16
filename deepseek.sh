#!/usr/bin/env bash
# setup-current-time-skill.sh
# Prepara la skill 'current-time' per OpenCode e testa il ciclo completo.

set -euo pipefail

SKILL_NAME="current-time"
SKILL_DIR="$HOME/.config/opencode/skills/$SKILL_NAME"
TIME_SCRIPT="$SKILL_DIR/time.sh"
MODEL="${1:-ollama/qwen2.5-coder:7b}"

echo "==> 1. Verifica prerequisiti"
for cmd in ollama opencode jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERRORE: '$cmd' non trovato nel PATH." >&2
    exit 1
  fi
done
echo "    OK: ollama, opencode, jq presenti."

echo
echo "==> 2. Creazione directory e script time.sh"
mkdir -p "$SKILL_DIR"

cat > "$TIME_SCRIPT" <<'TIME_EOF'
#!/usr/bin/env bash
set -euo pipefail
LOCAL_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')
UTC_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
printf '{"local":"%s","utc":"%s"}\n' "$LOCAL_TIME" "$UTC_TIME"
TIME_EOF

chmod +x "$TIME_SCRIPT"
echo "    Creato: $TIME_SCRIPT"

echo
echo "==> 3. Creazione SKILL.md (con percorso assoluto nel comando)"
cat > "$SKILL_DIR/SKILL.md" <<SKILL_EOF
---
name: $SKILL_NAME
description: Fornisce la data e l'ora correnti locali e in UTC. Usa questa skill ogni volta che l'utente chiede che ore sono, la data di oggi o informazioni temporali.
---

Questa skill ti permette di ottenere l'ora corrente eseguendo lo script \`$TIME_SCRIPT\`.

## Quando usarla
- Quando l'utente chiede "che ore sono?"
- Quando serve una data o un timestamp per un'operazione.
- Quando devi registrare l'ora di un evento.

## Come usarla
Usa il tool \`shell\` per eseguire il seguente comando:

\`\`\`
bash $TIME_SCRIPT
\`\`\`

Lo script restituisce un oggetto JSON con due campi:
- \`local\`: data e ora nel fuso orario locale.
- \`utc\`: data e ora in UTC.

Usa il campo \`local\` per rispondere all'utente, a meno che non venga richiesto esplicitamente l'UTC.
SKILL_EOF

echo "    Creato: $SKILL_DIR/SKILL.md"
echo "    Contenuto:"
sed 's/^/      /' "$SKILL_DIR/SKILL.md"

echo
echo "==> 4. Verifica esecuzione diretta dello script"
OUTPUT=$("$TIME_SCRIPT")
echo "    Output: $OUTPUT"
if ! echo "$OUTPUT" | jq -e '.local and .utc' >/dev/null 2>&1; then
  echo "ERRORE: lo script non produce un JSON valido." >&2
  exit 1
fi
echo "    OK: JSON valido."

echo
echo "==> 5. Verifica modelli disponibili in OpenCode"
if ! opencode models | grep -q "$MODEL"; then
  echo "ATTENZIONE: il modello '$MODEL' non è elencato da 'opencode models'."
  echo "Modelli Ollama disponibili:"
  opencode models | grep '^ollama/' || true
  echo
  echo "Suggerimento: aggiungi il modello al blocco 'models' in ~/.config/opencode/opencode.json,"
  echo "oppure passa un modello diverso come primo argomento:"
  echo "    $0 ollama/qwen2.5-coder:3b"
  exit 1
fi
echo "    OK: $MODEL disponibile."

echo
echo "==> 6. Test end-to-end con OpenCode"
echo "    Comando: opencode run \"Che ore sono? Usa la skill current-time.\" -m $MODEL"
echo
opencode run "Che ore sono? Usa la skill current-time e il tool shell per eseguire lo script." -m "$MODEL"

echo
echo "==> Fatto."
echo "    Se la risposta contiene l'ora corrente (CET), il ciclo funziona."
echo "    Se il modello ha allucinato, prova con un modello più grande:"
echo "        $0 ollama/qwen3:4b"
echo "        $0 ollama/qwen2.5-coder:7b"