#!/usr/bin/env bash
#
# sync.sh — Commit + Push su GitHub in un colpo solo
#
# Uso:
#   ./sync.sh                       Commit automatico con timestamp, poi push
#   ./sync.sh "messaggio"           Commit con messaggio personalizzato, poi push
#   ./sync.sh --pull                Solo pull dal remote (sync da altri PC)
#   ./sync.sh --status              Mostra stato git
#   ./sync.sh --log                 Mostra ultimi commit
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

case "${1:-commit}" in
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

    commit|"")
        # Mostra cosa è cambiato
        echo "📋 File modificati:"
        git status --short

        # Se non c'è nulla da committare
        if [ -z "$(git status --short)" ]; then
            echo "✓ Nessuna modifica da sincronizzare"
            exit 0
        fi

        echo

        # Messaggio del commit
        if [ -n "$1" ] && [ "$1" != "commit" ]; then
            MSG="$1"
        else
            MSG="Auto-sync $(date '+%Y-%m-%d %H:%M:%S')"
        fi

        echo "📝 Commit con messaggio: \"$MSG\""
        git add .
        git commit -m "$MSG"

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

    *)
        echo "Uso: $0 [commit|\"messaggio\"|--pull|--status|--log]"
        echo
        echo "  commit (default)   Commit automatico + push"
        echo "  \"messaggio\"        Commit con messaggio personalizzato + push"
        echo "  --pull             Scarica modifiche da GitHub"
        echo "  --status           Mostra stato git"
        echo "  --log              Mostra ultimi 20 commit"
        ;;
esac
