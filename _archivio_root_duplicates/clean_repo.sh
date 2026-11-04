#!/usr/bin/env bash
# Pulizia repo: rimuove dal tracking file che NON dovrebbero stare su GitHub.
#
# Esegui DALLA ROOT del repo:
#     bash scripts/clean_repo.sh
#
# Oppure in dry-run (mostra cosa farebbe senza modificare niente):
#     bash scripts/clean_repo.sh --dry-run
#
# Cosa fa:
#   1. Verifica che CONFIG/settings.json, actors.json, scheduled_tasks.json,
#      git_settings.json, security_baseline.json NON siano tracked
#   2. Rimuove dal tracking eventuali PNG/JPEG creati in root (debug)
#   3. Verifica che .gitignore aggiornato li escluda
#   4. Fa un commit "chore: clean repo (untrack runtime files)"
#
# Sicuro: NON cancella i file dal filesystem, solo dal tracking git.

set -e

DRY_RUN=0
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=1
    echo "=== DRY-RUN: nessuna modifica verrà applicata ==="
fi

cd "$(git rev-parse --show-toplevel)"

echo "=== 1. Verifica CONFIG/*.json ==="
for f in CONFIG/settings.json CONFIG/actors.json CONFIG/scheduled_tasks.json \
         CONFIG/git_settings.json CONFIG/security_baseline.json; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        echo "  ⚠️  $f è TRACKED — rimuovo dal tracking"
        if [ $DRY_RUN -eq 0 ]; then
            git rm --cached "$f"
        fi
    else
        echo "  ✓  $f non tracked (ok)"
    fi
done

echo ""
echo "=== 2. Verifica PNG/JPEG in root (debug screenshots) ==="
for f in *.png *.jpeg *.jpg; do
    [ -e "$f" ] || continue
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        echo "  ⚠️  $f è TRACKED — rimuovo dal tracking (resta su disco)"
        if [ $DRY_RUN -eq 0 ]; then
            git rm --cached "$f"
        fi
    else
        echo "  ✓  $f presente ma non tracked (ok)"
    fi
done

echo ""
echo "=== 3. Verifica file .bak/.orig/.swp ==="
for f in *.bak *.orig *.swp *~; do
    [ -e "$f" ] || continue
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        echo "  ⚠️  $f è TRACKED — rimuovo"
        if [ $DRY_RUN -eq 0 ]; then
            git rm --cached "$f"
        fi
    fi
done

echo ""
echo "=== 4. Verifica .gitignore aggiornato ==="
if grep -q "CONFIG/settings.json" .gitignore 2>/dev/null; then
    echo "  ✓  .gitignore contiene CONFIG/settings.json"
else
    echo "  ✗  .gitignore NON contiene CONFIG/settings.json — aggiornalo!"
fi
if grep -q "/\*.png" .gitignore 2>/dev/null; then
    echo "  ✓  .gitignore contiene /*.png (solo root)"
else
    echo "  ✗  .gitignore NON contiene /*.png — aggiornalo!"
fi

echo ""
if [ $DRY_RUN -eq 1 ]; then
    echo "=== DRY-RUN completato. Riesegui senza --dry-run per applicare. ==="
else
    if [ -n "$(git status --porcelain)" ]; then
        echo "=== 5. Commit delle modifiche ==="
        git add .gitignore
        git commit -m "chore: clean repo (untrack runtime files: CONFIG/*.json + PNG debug)

- CONFIG/settings.json, actors.json, scheduled_tasks.json,
  git_settings.json, security_baseline.json: NON tracked (token in chiaro)
- PNG screenshot di debug: NON tracked (IMG/ resta)
- .gitignore aggiornato con pattern robusto"
        echo "  ✓  commit fatto"
        echo ""
        echo "Per pushare ora:"
        echo "    git push"
    else
        echo "=== Repo pulito, niente da committare. ==="
    fi
fi
