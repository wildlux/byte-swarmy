#!/usr/bin/env bash
#
# setup-hardening.sh — hardening OPZIONALE a livello di sistema.
#
# Il codice (security.py, tools.py) è già sicuro senza root. Questo script
# aggiunge difese in profondità per chi vuole isolare i worker in un utente
# dedicato, con cgroup e firewall.
#
# NON viene eseguito automaticamente. Leggilo prima di usarlo.
#
# Uso:
#   ./setup-hardening.sh                 # solo diagnostica (nessuna modifica)
#   ./setup-hardening.sh --check         # idem
#   sudo ./setup-hardening.sh --apply    # crea utente byteswarmy + copia progetto + cgroup slice
#   sudo ./setup-hardening.sh --firewall # blocca la rete in uscita per byteswarmy (tranne Ollama)
#   sudo ./setup-hardening.sh --all      # --apply + --firewall
#   sudo ./setup-hardening.sh --undo     # rimuove slice e regole firewall
#   sudo ./setup-hardening.sh --undo --purge-user  # + elimina utente e home (CHIEDE CONFERMA)
#
# Dopo --apply, avvia l'orchestratore isolato con:
#   sudo systemd-run --slice=byteswarmy.slice --uid=byteswarmy --gid=byteswarmy \
#        --working-directory=/home/byteswarmy/byte-swarmy \
#        /home/byteswarmy/byte-swarmy/avvia.sh --orch
#
# La GUI continua a girare come utente reale.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${TARGET_USER:-byteswarmy}"
TARGET_HOME="/home/${TARGET_USER}"
TARGET_DIR="${TARGET_HOME}/byte-swarmy"
SLICE_FILE="/etc/systemd/system/${TARGET_USER}.slice"
IPTABLES_RULES="/etc/iptables/rules.v4"
OLLAMA_PORT=11434

c_reset=$'\033[0m'; c_red=$'\033[31m'; c_green=$'\033[32m'
c_yellow=$'\033[33m'; c_blue=$'\033[34m'; c_bold=$'\033[1m'

say()  { printf '%s\n' "$*"; }
info() { printf '%s[*]%s %s\n' "$c_blue" "$c_reset" "$*"; }
ok()   { printf '%s[+]%s %s\n' "$c_green" "$c_reset" "$*"; }
warn() { printf '%s[!]%s %s\n' "$c_yellow" "$c_reset" "$*"; }
err()  { printf '%s[x]%s %s\n' "$c_red" "$c_reset" "$*" >&2; }

usage() {
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
}

need_root() {
    if [[ ${EUID} -ne 0 ]]; then
        err "Serve root: usa 'sudo $0 $*'"
        exit 1
    fi
}

user_exists() { id -u "$TARGET_USER" >/dev/null 2>&1; }

check() {
    say "${c_bold}Diagnostica hardening${c_reset}"
    say "  Progetto:      ${PROJECT_DIR}"
    say "  Utente target: ${TARGET_USER} (${TARGET_HOME})"
    say

    if user_exists; then
        ok "utente ${TARGET_USER} esiste (uid $(id -u "$TARGET_USER"))"
        if id -nG "$TARGET_USER" | tr ' ' '\n' | grep -Eq '^(sudo|wheel|admin|root)$'; then
            err "  ${TARGET_USER} è in un gruppo amministrativo: rimuovilo!"
        else
            ok "  non è in gruppi amministrativi"
        fi
        perms=$(stat -c '%a %U:%G' "$TARGET_HOME" 2>/dev/null || echo "assente")
        say "  home: ${perms} (atteso 700 ${TARGET_USER}:${TARGET_USER})"
        if [[ -d "$TARGET_DIR" ]]; then
            ok "  progetto copiato in ${TARGET_DIR}"
        else
            warn "  progetto NON copiato in ${TARGET_DIR}"
        fi
    else
        warn "utente ${TARGET_USER} NON esiste (usa --apply)"
    fi

    if [[ -f "$SLICE_FILE" ]]; then
        ok "slice cgroup presente: ${SLICE_FILE}"
    else
        warn "slice cgroup assente (usa --apply)"
    fi

    if command -v iptables >/dev/null 2>&1; then
        if user_exists; then
            uid=$(id -u "$TARGET_USER")
            count=$(iptables -S OUTPUT 2>/dev/null | grep -c -- "--uid-owner ${uid}" || true)
            say "  regole iptables per uid ${uid}: ${count}"
        fi
    else
        warn "iptables non installato"
    fi

    say
    say "Difese già attive nel codice (nessun root richiesto):"
    say "  - run_bash senza shell + allowlist/blacklist (security.py)"
    say "  - path confinati in project/, niente ~/.ssh o .git-credentials"
    say "  - git push/pull/remote disabilitati per i worker"
    say "  - limiti CPU/file/memoria per processo"
    say "  - audit log in logs/security.log"
    say
    say "Test: python -m unittest discover -s tests -t . -v"
}

apply_user() {
    need_root "--apply"

    if ! user_exists; then
        info "creo utente ${TARGET_USER} senza privilegi..."
        useradd --create-home --home-dir "$TARGET_HOME" \
                --shell /bin/bash --user-group "$TARGET_USER"
        passwd -l "$TARGET_USER" >/dev/null 2>&1 || true
        ok "utente creato (password bloccata: accesso solo via sudo -u)"
    else
        info "utente ${TARGET_USER} già presente"
    fi

    chmod 700 "$TARGET_HOME"
    chown "${TARGET_USER}:${TARGET_USER}" "$TARGET_HOME"

    if ! command -v rsync >/dev/null 2>&1; then
        err "rsync non installato: sudo apt install rsync"
        exit 1
    fi

    info "copio il progetto in ${TARGET_DIR} (esclusi venv/log/state/backup)..."
    install -d -m 755 -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_DIR"
    rsync -a --delete \
        --exclude '.venv/' \
        --exclude '__pycache__/' \
        --exclude 'logs/' \
        --exclude 'state/' \
        --exclude 'backups/' \
        --exclude 'mcp_servers.json' \
        --exclude '*.pyc' \
        "$PROJECT_DIR"/ "$TARGET_DIR"/
    chown -R "${TARGET_USER}:${TARGET_USER}" "$TARGET_DIR"
    chmod 750 "$TARGET_DIR"
    ok "progetto copiato"

    if [[ -d "$TARGET_DIR/.git" ]]; then
        info "verifico che .git non contenga credenziali in chiaro..."
        if grep -rIl --exclude='*.pack' --exclude='*.idx' \
                -E '(ghp_[A-Za-z0-9]{20,}|github_pat_|AKIA[0-9A-Z]{16})' \
                "$TARGET_DIR/.git" >/dev/null 2>&1; then
            warn "possibili token dentro .git: controlla prima di avviare!"
        else
            ok "nessun token evidente in .git"
        fi
    fi

    warn "Il venv NON è stato copiato (i path assoluti si romperebbero)."
    warn "Crealo come utente isolato:"
    warn "  sudo -u ${TARGET_USER} -H bash -lc 'cd ${TARGET_DIR} && ./setup.sh'"
}

apply_slice() {
    need_root "--apply"
    if ! command -v systemctl >/dev/null 2>&1; then
        warn "systemd non disponibile: salto il cgroup"
        return
    fi

    info "scrivo ${SLICE_FILE}..."
    cat > "$SLICE_FILE" <<EOF
[Unit]
Description=BYTE-SWARMY sandbox slice

[Slice]
MemoryMax=4G
CPUQuota=200%
TasksMax=100
BlockIOWeight=500
EOF
    systemctl daemon-reload
    systemctl start "${TARGET_USER}.slice" 2>/dev/null || true
    ok "slice ${TARGET_USER}.slice configurata (RAM 4G, CPU 200%, task 100)"
}

apply_firewall() {
    need_root "--firewall"
    if ! command -v iptables >/dev/null 2>&1; then
        err "iptables non installato: sudo apt install iptables"
        exit 1
    fi
    if ! user_exists; then
        err "utente ${TARGET_USER} assente: esegui prima --apply"
        exit 1
    fi

    uid=$(id -u "$TARGET_USER")
    info "blocco la rete in uscita per uid ${uid} (tranne Ollama su 127.0.0.1:${OLLAMA_PORT})..."

    if ! iptables -C OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.1 \
            -p tcp --dport "$OLLAMA_PORT" -j ACCEPT 2>/dev/null; then
        iptables -I OUTPUT 1 -m owner --uid-owner "$uid" -d 127.0.0.1 \
                 -p tcp --dport "$OLLAMA_PORT" -j ACCEPT
    fi
    if ! iptables -C OUTPUT -m owner --uid-owner "$uid" -j DROP 2>/dev/null; then
        iptables -A OUTPUT -m owner --uid-owner "$uid" -j DROP
    fi

    if command -v ip6tables >/dev/null 2>&1; then
        if ! ip6tables -C OUTPUT -m owner --uid-owner "$uid" -o lo -j ACCEPT 2>/dev/null; then
            ip6tables -I OUTPUT 1 -m owner --uid-owner "$uid" -o lo -j ACCEPT 2>/dev/null || true
        fi
        if ! ip6tables -C OUTPUT -m owner --uid-owner "$uid" -j DROP 2>/dev/null; then
            ip6tables -A OUTPUT -m owner --uid-owner "$uid" -j DROP 2>/dev/null || true
        fi
    fi

    ok "regole firewall applicate"

    if [[ -d "$(dirname "$IPTABLES_RULES")" ]]; then
        cp -a "$IPTABLES_RULES" "${IPTABLES_RULES}.bak.$(date +%s)" 2>/dev/null || true
        iptables-save > "$IPTABLES_RULES"
        ok "regole salvate in ${IPTABLES_RULES}"
    else
        warn "regole NON persistenti al reboot."
        warn "Installa iptables-persistent oppure salva con: iptables-save > /etc/iptables/rules.v4"
    fi
}

undo_firewall() {
    need_root "--undo"
    command -v iptables >/dev/null 2>&1 || return 0
    user_exists || return 0
    uid=$(id -u "$TARGET_USER")

    while iptables -C OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.1 \
            -p tcp --dport "$OLLAMA_PORT" -j ACCEPT 2>/dev/null; do
        iptables -D OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.1 \
                 -p tcp --dport "$OLLAMA_PORT" -j ACCEPT
    done
    while iptables -C OUTPUT -m owner --uid-owner "$uid" -j DROP 2>/dev/null; do
        iptables -D OUTPUT -m owner --uid-owner "$uid" -j DROP
    done

    if command -v ip6tables >/dev/null 2>&1; then
        while ip6tables -C OUTPUT -m owner --uid-owner "$uid" -j DROP 2>/dev/null; do
            ip6tables -D OUTPUT -m owner --uid-owner "$uid" -j DROP
        done
    fi
    ok "regole firewall rimosse (verifica con: sudo iptables -S OUTPUT)"
}

undo_slice() {
    need_root "--undo"
    if [[ -f "$SLICE_FILE" ]]; then
        rm -f "$SLICE_FILE"
        systemctl daemon-reload 2>/dev/null || true
        systemctl stop "${TARGET_USER}.slice" 2>/dev/null || true
        ok "slice rimossa"
    fi
}

purge_user() {
    need_root "--purge-user"
    user_exists || { warn "utente assente"; return; }
    warn "Stai per ELIMINARE ${TARGET_USER} e la sua home ${TARGET_HOME}."
    read -r -p "Scrivi ELIMINA per confermare: " answer
    if [[ "$answer" != "ELIMINA" ]]; then
        warn "annullato"
        return
    fi
    pkill -u "$TARGET_USER" 2>/dev/null || true
    userdel -r "$TARGET_USER"
    ok "utente e home eliminati"
}

case "${1:-}" in
    ""|--check)
        check
        ;;
    --apply)
        apply_user
        apply_slice
        check
        ;;
    --firewall)
        apply_firewall
        ;;
    --all)
        apply_user
        apply_slice
        apply_firewall
        check
        ;;
    --undo)
        undo_firewall
        undo_slice
        if [[ "${2:-}" == "--purge-user" ]]; then
            purge_user
        fi
        check
        ;;
    -h|--help)
        usage
        ;;
    *)
        err "opzione sconosciuta: $1"
        usage
        exit 1
        ;;
esac
