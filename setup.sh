#!/usr/bin/env bash
#
# setup.sh — Verifica e installa tutte le dipendenze di BYTE-SWARMY
#
# Fa il check di:
#   1. Dipendenze sistema (python3, pip, git, ollama)
#   2. Pacchetti Python (PyQt6, tomli-w, mcp, httpx, httpx-sse, uvicorn, starlette)
#   3. Virtualenv .venv
#   4. Modelli Ollama necessari
#
# Installa ciò che manca (chiede password sudo se serve per pacchetti sistema).
# Poi avvia BYTE-SWARMY.
#

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠️${NC} $1"; }
err()   { echo -e "${RED}❌${NC} $1"; }
info()  { echo -e "${BLUE}ℹ️${NC} $1"; }
title() { echo -e "\n${BLUE}=== $1 ===${NC}\n"; }

# Risolve la directory dello script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Banner
show_banner() {
    cat <<'EOF'
 ____  _____ _   _ _____ __  __   _   _    _    _   _
| __ )| ____| \ | | ____|  \/  | | | | |  / \  | \ | |
|  _ \|  _| |  \| |  _| | |\/| | | | | | / _ \ |  \| |
| |_) | |___| |\  | |___| |  | | | |_| |/ ___ \| |\  |
|____/|_____|_| \_|_____|_|  |_|  \___//_/   \_\_| \_|
        Autonomous Programming Intelligence Swarm
EOF
}

show_banner
echo
title "CHECK DIPENDENZE BYTE-SWARMY"

# === 1. Dipendenze sistema ===
title "1. Dipendenze di sistema"

NEED_SUDO_INSTALL=()
NEED_SUDO_PACKAGES=()

# python3
if command -v python3 &>/dev/null; then
    PYVER=$(python3 --version 2>&1)
    ok "Python3: $PYVER"
else
    err "Python3 non trovato"
    NEED_SUDO_INSTALL+=("python3")
    NEED_SUDO_PACKAGES+=("python3 python3-venv python3-pip python3-dev")
fi

# python3-venv (necessario per creare venv)
if ! python3 -m venv --help &>/dev/null; then
    warn "python3-venv non disponibile"
    NEED_SUDO_PACKAGES+=("python3-venv python3-full")
fi

# pip
if python3 -m pip --version &>/dev/null; then
    ok "pip disponibile"
else
    warn "pip non disponibile"
    NEED_SUDO_PACKAGES+=("python3-pip")
fi

# git
if command -v git &>/dev/null; then
    ok "git: $(git --version)"
else
    warn "git non trovato"
    NEED_SUDO_PACKAGES+=("git")
fi

# bubblewrap (necessario per il sandbox)
if command -v bwrap &>/dev/null; then
    ok "bubblewrap: $(bwrap --version)"
else
    warn "bubblewrap non trovato — i worker non potranno eseguire comandi"
    NEED_SUDO_PACKAGES+=("bubblewrap")
fi

# ollama
if command -v ollama &>/dev/null; then
    ok "ollama: $(ollama --version 2>&1 | head -1)"
else
    err "ollama non trovato — BYTE-SWARMY non può funzionare senza"
    echo
    echo "Installa Ollama con:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo
    read -p "Vuoi installare Ollama ora? (s/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
    else
        err "Ollama è obbligatorio. Installa e ripeti."
        exit 1
    fi
fi

# Verifica che ollama sia attivo (service running)
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    warn "Servizio Ollama non attivo. Avvio..."
    # Prova ad avviarlo
    if command -v systemctl &>/dev/null; then
        sudo systemctl start ollama 2>/dev/null || {
            # Fallback: avvia manualmente in background
            nohup ollama serve > /tmp/ollama.log 2>&1 &
            sleep 3
        }
    else
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    fi
    # Verifica
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        ok "Servizio Ollama avviato"
    else
        err "Impossibile avviare Ollama. Verifica con: ollama serve"
        exit 1
    fi
else
    ok "Servizio Ollama attivo"
fi

# Installa pacchetti sistema se necessari
if [ ${#NEED_SUDO_PACKAGES[@]} -gt 0 ]; then
    title "INSTALLAZIONE PACCHETTI SISTEMA"
    info "Sono necessari questi pacchetti: ${NEED_SUDO_PACKAGES[*]}"
    echo
    read -p "Vuoi installarli ora con apt? (richiede password sudo) (s/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        # Rimuovi duplicati
        UNIQUE_PKGS=$(echo "${NEED_SUDO_PACKAGES[*]}" | tr ' ' '\n' | sort -u | tr '\n' ' ')
        sudo apt update
        sudo apt install -y $UNIQUE_PKGS
        ok "Pacchetti sistema installati"
    else
        warn "Salto installazione. Alcune funzioni potrebbero non funzionare."
    fi
fi

# === 2. Virtualenv ===
title "2. Virtualenv Python"

RECREATE_VENV=false

if [ ! -d ".venv" ]; then
    info "Virtualenv non presente, creo..."
    RECREATE_VENV=true
else
    # Verifica che .venv/bin/python e pip esistano e funzionino
    if [ ! -x ".venv/bin/python" ]; then
        warn ".venv/bin/python non trovato — ricreo venv"
        RECREATE_VENV=true
    elif ! .venv/bin/python -c "print('ok')" &>/dev/null; then
        warn ".venv/bin/python non funziona — ricreo venv"
        RECREATE_VENV=true
    elif [ ! -f ".venv/bin/pip" ] && ! .venv/bin/python -m pip --version &>/dev/null; then
        warn "pip non disponibile nel venv — ricreo venv"
        RECREATE_VENV=true
    else
        VENV_PY=$(.venv/bin/python --version 2>&1)
        ok "Virtualenv .venv/ presente ($VENV_PY)"
    fi
fi

if [ "$RECREATE_VENV" = true ]; then
    rm -rf .venv
    info "Creo virtualenv .venv/..."
    if ! python3 -m venv .venv; then
        err "Impossibile creare venv"
        echo
        echo "Prova a installare python3-venv:"
        echo "  sudo apt install python3-venv python3-full"
        read -p "Vuoi installare ora? (s/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            sudo apt update
            sudo apt install -y python3-venv python3-full
            python3 -m venv .venv || { err "Ancora fallito"; exit 1; }
        else
            exit 1
        fi
    fi
    # Assicurati che pip sia presente nel venv
    if [ ! -f ".venv/bin/pip" ]; then
        warn "pip non nel venv, provo ensurepip..."
        if ! .venv/bin/python -m ensurepip --upgrade 2>/dev/null; then
            err "ensurepip fallito."
            echo "Installa pip dal repository della distro (consigliato), ad esempio:"
            echo "  sudo apt install python3-pip python3-venv"
            echo "oppure scarica https://bootstrap.pypa.io/get-pip.py, controllalo e poi eseguilo."
            echo "Non eseguiamo automaticamente script scaricati da internet."
            exit 1
        fi
    fi
    ok "Virtualenv creato"
fi

# Attiva venv
source .venv/bin/activate

# Verifica esplicita che stiamo usando il python del venv (non di sistema)
info "Verifica python attivo:"
which python
which pip

# Path assoluti per evitare ambiguità
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
VENV_PIP="$SCRIPT_DIR/.venv/bin/pip"

# Se .venv/bin/pip non esiste, usa python -m pip
if [ ! -x "$VENV_PIP" ]; then
    VENV_PIP="$VENV_PYTHON -m pip"
fi

# Verifica pip funzionante
if ! $VENV_PIP --version &>/dev/null; then
    err "pip non funziona nel venv ($VENV_PIP)"
    echo
    echo "Prova a ricostruire il venv:"
    echo "  rm -rf .venv"
    echo "  sudo apt install python3-venv python3-full"
    echo "  python3 -m venv .venv --upgrade-deps"
    exit 1
fi
ok "pip del venv funzionante: $VENV_PIP"

# === 3. Pacchetti Python ===
title "3. Pacchetti Python"

# Verifica ogni pacchetto e installa se mancante.
# USA SEMPRE il python/pip del venv con path assoluto.
check_pip_package() {
    local pkg_import="$1"
    local pip_name="$2"
    if $VENV_PYTHON -c "import $pkg_import" 2>/dev/null; then
        ok "$pip_name installato"
        return 0
    else
        warn "$pip_name mancante — installazione nel venv..."
        if $VENV_PIP install "$pip_name"; then
            if $VENV_PYTHON -c "import $pkg_import" 2>/dev/null; then
                ok "$pip_name installato con successo"
                return 0
            else
                err "$pip_name installato ma import fallito"
                return 1
            fi
        else
            err "Installazione di $pip_name fallita"
            echo
            echo "Prova manualmente:"
            echo "  rm -rf .venv"
            echo "  python3 -m venv .venv --upgrade-deps"
            echo "  source .venv/bin/activate"
            echo "  pip install $pip_name"
            return 1
        fi
    fi
}

check_pip_package "PyQt6" "PyQt6" || exit 1
check_pip_package "tomli_w" "tomli-w" || exit 1
# tomllib è stdlib in Python 3.11+
if $VENV_PYTHON -c "import tomllib" 2>/dev/null; then
    ok "tomllib (stdlib) disponibile"
else
    warn "tomllib non disponibile (Python < 3.11), installo tomli..."
    check_pip_package "tomli" "tomli" || exit 1
fi
check_pip_package "mcp" "mcp" || exit 1
check_pip_package "httpx" "httpx" || exit 1
check_pip_package "httpx_sse" "httpx-sse" || exit 1
check_pip_package "uvicorn" "uvicorn" || exit 1
check_pip_package "starlette" "starlette" || exit 1

# Verifica finale (usa VENV_PYTHON esplicito)
echo
info "Verifica finale pacchetti Python:"
$VENV_PYTHON -c "
import sys
missing = []
for mod, name in [
    ('PyQt6', 'PyQt6'),
    ('tomli_w', 'tomli-w'),
    ('mcp', 'mcp'),
    ('httpx', 'httpx'),
    ('httpx_sse', 'httpx-sse'),
    ('uvicorn', 'uvicorn'),
    ('starlette', 'starlette'),
]:
    try:
        __import__(mod)
        print(f'  ✓ {name}')
    except ImportError:
        print(f'  ❌ {name}')
        missing.append(name)
if missing:
    print()
    print('Pacchetti mancanti:', missing)
    sys.exit(1)
else:
    print()
    print('Tutti i pacchetti Python OK')
" || {
    err "Alcuni pacchetti Python non sono stati installati correttamente"
    exit 1
}

# === 4. Modelli Ollama ===
title "4. Modelli Ollama"

# Modelli richiesti: name|descrizione
REQUIRED_MODELS=(
    "qwen2.5:0.5b|Orchestratore (700 MB)"
    "phi3:mini|Planner (2.2 GB)"
    "qwen2.5-coder:1.5b|Worker coding (1 GB)"
    "qwen2.5:1.5b|Worker general (1 GB)"
    "nomic-embed-text|Embedding (274 MB)"
)

# Modelli opzionali (decision models)
OPTIONAL_MODELS=(
    "tev1:4b|Decision model attivo (2.5 GB)"
)

# Modelli disponibili
AVAILABLE_MODELS=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')

model_installed() {
    local model_name="$1"
    # Match esatto o con suffisso :latest
    echo "$AVAILABLE_MODELS" | grep -q "^${model_name}$" && return 0
    echo "$AVAILABLE_MODELS" | grep -q "^${model_name%:.*}:latest$" && return 0
    return 1
}

# Verifica modelli richiesti
MISSING_REQUIRED=()
for entry in "${REQUIRED_MODELS[@]}"; do
    model="${entry%%|*}"
    desc="${entry##*|}"
    if model_installed "$model"; then
        ok "$model ($desc)"
    else
        warn "$model MANCANTE ($desc)"
        MISSING_REQUIRED+=("$model")
    fi
done

# Verifica modelli opzionali
MISSING_OPTIONAL=()
for entry in "${OPTIONAL_MODELS[@]}"; do
    model="${entry%%|*}"
    desc="${entry##*|}"
    if model_installed "$model"; then
        ok "$model ($desc)"
    else
        warn "$model opzionale mancante ($desc)"
        MISSING_OPTIONAL+=("$model")
    fi
done

# Installa modelli mancanti se richiesto
if [ ${#MISSING_REQUIRED[@]} -gt 0 ] || [ ${#MISSING_OPTIONAL[@]} -gt 0 ]; then
    echo
    info "Modelli mancanti: ${#MISSING_REQUIRED[@]} richiesti, ${#MISSING_OPTIONAL[@]} opzionali"
    
    if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
        echo
        read -p "Scaricare i modelli RICHIESTI mancanti ora? (${MISSING_REQUIRED[*]}) (s/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            for model in "${MISSING_REQUIRED[@]}"; do
                info "Scaricando $model (può richiedere minuti)..."
                ollama pull "$model"
                ok "$model scaricato"
            done
        else
            warn "Senza questi modelli BYTE-SWARMY non può funzionare correttamente"
        fi
    fi
    
    if [ ${#MISSING_OPTIONAL[@]} -gt 0 ]; then
        echo
        read -p "Scaricare anche i modelli OPZIONALI? (${MISSING_OPTIONAL[*]}) (s/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            for model in "${MISSING_OPTIONAL[@]}"; do
                info "Scaricando $model..."
                ollama pull "$model"
                ok "$model scaricato"
            done
        fi
    fi
fi

# === 5. Directory di lavoro ===
title "5. Directory di lavoro"
for d in tasks state logs project backups; do
    if [ ! -d "$d" ]; then
        mkdir -p "$d"
        ok "Creata directory $d/"
    else
        ok "Directory $d/ presente"
    fi
done

# === 6. Verifica configurazione ===
title "6. Configurazione"
if [ -f "config.toml" ]; then
    ok "config.toml presente"
    # Verifica sintassi
    if python -c "import tomllib; tomllib.load(open('config.toml','rb'))" 2>/dev/null; then
        ok "config.toml sintassi valida"
    else
        err "config.toml ha errori di sintassi — modificalo prima di avviare"
        exit 1
    fi
else
    err "config.toml NON TROVATO — devi essere nella directory byte-swarmy/"
    exit 1
fi

# === RIEPILOGO FINALE ===
title "RIEPILOGO"

ALL_OK=true

if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
    err "Modelli richiesti ancora mancanti: ${MISSING_REQUIRED[*]}"
    ALL_OK=false
fi

if [ "$ALL_OK" = true ]; then
    ok "Tutte le dipendenze sono soddisfatte!"
    echo
    echo "BYTE-SWARMY è pronto."
    echo
    echo "Per avviare:"
    echo "  ./avvia.sh           # orchestratore + GUI"
    echo "  ./avvia.sh --gui     # solo GUI"
    echo "  ./avvia.sh --status  # solo stato"
    echo
    
    # Chiedi se avviare ora
    read -p "Vuoi avviare BYTE-SWARMY ora? (s/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        exec ./avvia.sh
    fi
    exit 0
else
    err "Setup non completo. Risolvi i problemi sopra e ripeti."
    exit 1
fi
