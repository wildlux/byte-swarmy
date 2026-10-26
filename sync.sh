#!/usr/bin/env bash
#
# sync.sh — Commit + Push su GitHub in un colpo solo
#
# Uso:
#   ./sync.sh                       Commit automatico con timestamp, poi push
#   ./sync.sh "messaggio"           Commit con messaggio personalizzato, poi push
#   ./sync.sh commit                Equivalente a ./sync.sh (auto-sync timestamp)
#   ./sync.sh --pull                Solo pull dal remote (sync da altri PC)
#   ./sync.sh --status              Mostra stato git
#   ./sync.sh --log                 Mostra ultimi commit
#   ./sync.sh -h|--help             Mostra questo aiuto
#

set -e

cd "$(dirname "${BASH_SOURCE[0]}")"

# Verifica che sia un repo git
if [ ! -d ".git" ]; then
    echo "❌ Non è un repository git. Esegui prima:"
    echo "  git init"
    echo "  git remote add origin https://github.com/wildlux/byte-swarmy.git"
    exit 1
fi

# Funzione di aiuto
show_help() {
    cat <<EOF
Uso: $0 [commit|"messaggio"|--pull|--status|--log|-h]

  commit (default)   Commit automatico con timestamp + push
  "messaggio"        Commit con messaggio personalizzato + push
  --pull             Scarica modifiche da GitHub (rebase)
  --status           Mostra stato git
  --log              Mostra ultimi 20 commit
  -h, --help         Mostra questo aiuto
EOF
}

case "${1:-commit}" in
    -h|--help)
        show_help
        ;;

    --pull)
        echo "📥 Pull dal remote..."
        git pull --rebase origin main 2>/dev/null || git pull origin main
        echo "✓ Pull completato"
        ;;

    --status)
        git status
        ;;

    --log)
        git log --oneline -20
        ;;

    *)
        # Default: commit + push
        # Accetta qualsiasi argomento come messaggio (incluso "commit" o stringa vuota)

        echo "📋 File modificati:"
        git status --short

        # Determina il messaggio del commit
        if [ -z "$1" ] || [ "$1" = "commit" ]; then
            MSG="Auto-sync $(date '+%Y-%m-%d %H:%M:%S')"
        else
            MSG="$1"
        fi

        # Committa SOLO se ci sono modifiche pendenti
        if [ -n "$(git status --short)" ]; then
            echo "📝 Commit con messaggio: \"$MSG\""
            git add .
            git commit -m "$MSG"
        else
            echo "✓ Nessuna modifica da committare"
        fi

        # PUSH SEMPRE — anche se non c'è un nuovo commit,
        # potrebbero esserci commit locali non ancora su GitHub
        echo
        echo "🚀 Push su GitHub..."
        BRANCH=$(git branch --show-current)
        git push -u origin "$BRANCH"

        echo
        echo "✓ Sincronizzazione completata!"
        echo
        echo "📋 Ultimi 3 commit:"
        git log --oneline -3
        ;;
esac
