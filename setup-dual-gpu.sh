#!/usr/bin/env bash
#
# setup-dual-gpu.sh — Configura Ollama per doppia GPU (NVIDIA + Intel)
#
# Cosa fa:
#   1. Rileva le GPU presenti
#   2. Forza Ollama a usare la NVIDIA (CUDA_VISIBLE_DEVICES=0)
#   3. Crea varianti GPU dei modelli (con num_gpu forzato)
#   4. Testa che il modello sia caricato sulla VRAM
#   5. Mostra un riepilogo
#
# Uso:
#   ./setup-dual-gpu.sh              # configura + testa
#   ./setup-dual-gpu.sh --test       # solo test, non modifica
#   ./setup-dual-gpu.sh --status     # solo stato attuale
#

set -euo pipefail

# Colori
c_reset=$'\033[0m'; c_red=$'\033[31m'; c_green=$'\033[32m'
c_yellow=$'\033[33m'; c_blue=$'\033[34m'; c_bold=$'\033[1m'

info() { printf "${c_blue}[*]${c_reset} %s\n" "$*"; }
ok()   { printf "${c_green}[+]${c_reset} %s\n" "$*"; }
warn() { printf "${c_yellow}[!]${c_reset} %s\n" "$*"; }
err()  { printf "${c_red}[x]${c_reset} %s\n" "$*" >&2; }

# Modelli da ottimizzare per GPU (piccoli, entrano in 4GB VRAM)
GPU_MODELS=(
    "qwen2.5:0.5b"
    "qwen2.5:1.5b"
    "qwen2.5-coder:1.5b"
    "deepseek-coder:1.3b"
    "deepseek-r1:1.5b"
    "qwen3:1.7b"
    "gemma3:270m"
    "phi3:mini"
)

# Modelli GROSSI da tenere su CPU (non entrano in 4GB VRAM)
CPU_ONLY_MODELS=(
    "qwen2.5:3b"
    "qwen2.5-coder:3b"
    "qwen3.5:4b"
    "tev1:4b"
    "codellama:7b"
    "qwen3.5:latest"
)

# =================================================================
# FUNZIONI
# =================================================================

detect_gpus() {
    info "Rilevamento GPU..."
    
    # NVIDIA
    if command -v nvidia-smi &>/dev/null; then
        local nvidia_info
        nvidia_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
        if [[ -n "$nvidia_info" ]]; then
            NVIDIA_NAME=$(echo "$nvidia_info" | cut -d',' -f1 | xargs)
            NVIDIA_VRAM=$(echo "$nvidia_info" | cut -d',' -f2 | xargs)
            ok "NVIDIA trovata: ${c_bold}${NVIDIA_NAME}${c_reset} (VRAM: ${NVIDIA_VRAM})"
            NVIDIA_PRESENT=true
        fi
    else
        warn "NVIDIA non rilevata (nvidia-smi non disponibile)"
        NVIDIA_PRESENT=false
    fi
    
    # Intel (integra)
    if command -v lspci &>/dev/null; then
        if lspci 2>/dev/null | grep -qi "VGA.*Intel"; then
            local intel_name
            intel_name=$(lspci 2>/dev/null | grep -i "VGA.*Intel" | head -1 | sed 's/.*Intel/Intel/' | cut -d'(' -f1 | xargs)
            ok "Intel trovata: ${c_bold}${intel_name}${c_reset} (integra, per display)"
            INTEL_PRESENT=true
        fi
    fi
}

configure_ollama_service() {
    info "Configurazione service Ollama per usare NVIDIA..."
    
    if [[ "$NVIDIA_PRESENT" != "true" ]]; then
        err "NVIDIA non presente — impossibile configurare"
        return 1
    fi
    
    # Crea override per il service
    local override_dir="/etc/systemd/system/ollama.service.d"
    local override_file="${override_dir}/gpu-override.conf"
    
    if [[ ! -d "$override_dir" ]]; then
        sudo mkdir -p "$override_dir"
    fi
    
    # Scrivi override
    sudo tee "$override_file" > /dev/null << 'EOF'
[Service]
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="OLLAMA_GPU_VARIANT=cuda"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_KEEP_ALIVE=10m"
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF
    
    ok "Override scritto: ${override_file}"
    
    # Ricarica e riavvia
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    sleep 2
    ok "Ollama riavviato con configurazione GPU"
}

create_gpu_model_variants() {
    info "Creazione varianti GPU dei modelli piccoli..."
    
    for model in "${GPU_MODELS[@]}"; do
        # Verifica che il modello sia installato
        if ! ollama list 2>/dev/null | grep -q "^${model}"; then
            warn "Modello ${model} non installato — salto"
            continue
        fi
        
        local gpu_name="${model}-gpu"
        
        # Crea Modelfile temporaneo
        local tmpfile
        tmpfile=$(mktemp)
        cat > "$tmpfile" << EOF
FROM ${model}

# Forza caricamento su GPU
PARAMETER num_gpu 99

# Ottimizza per 4GB VRAM
PARAMETER num_ctx 2048
PARAMETER num_batch 512

# Mantieni in memoria più a lungo
PARAMETER keep_alive 10m
EOF
        
        # Crea variante GPU
        if ollama create "$gpu_name" -f "$tmpfile" 2>/dev/null; then
            ok "Creato: ${c_bold}${gpu_name}${c_reset}"
        else
            warn "Fallito creare ${gpu_name} — forse già esiste"
        fi
        
        rm -f "$tmpfile"
    done
}

test_gpu_loading() {
    info "Test caricamento modello su GPU..."
    
    if [[ "$NVIDIA_PRESENT" != "true" ]]; then
        err "NVIDIA non presente — test impossibile"
        return 1
    fi
    
    # Usa qwen2.5:0.5b (più piccolo, carica veloce)
    local test_model="qwen2.5:0.5b"
    
    info "Caricamento ${test_model} (genera 1 token)..."
    ollama run "$test_model" "ok" --verbose 2>&1 | tail -5 || true
    
    sleep 1
    
    # Verifica dove è caricato
    local ps_output
    ps_output=$(ollama ps 2>/dev/null)
    
    if echo "$ps_output" | grep -q "GPU\|100% GPU"; then
        ok "${c_green}✓ Modello caricato su GPU!${c_reset}"
    elif echo "$ps_output" | grep -q "CPU\|100% CPU"; then
        err "${c_red}✗ Modello caricato su CPU — GPU non usata!${c_reset}"
        warn "Verifica: journalctl -u ollama | grep -i cuda"
        return 1
    else
        warn "Impossibile determinare dove è caricato il modello"
    fi
    
    # Verifica VRAM
    local vram_used
    vram_used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | xargs)
    
    if [[ -n "$vram_used" && "$vram_used" -gt 100 ]]; then
        ok "VRAM usata: ${vram_used} MiB (modello caricato su GPU)"
    else
        warn "VRAM usata: ${vram_used} MiB (sospetto — modello non su GPU?)"
    fi
    
    # Scarica il modello per liberare memoria
    curl -s http://localhost:11434/api/generate -d "{\"model\": \"${test_model}\", \"keep_alive\": 0}" > /dev/null 2>&1 || true
}

show_status() {
    echo
    echo "${c_bold}=== STATO GPU ===${c_reset}"
    echo
    
    if [[ "$NVIDIA_PRESENT" == "true" ]]; then
        echo "${c_green}NVIDIA:${c_reset} ${NVIDIA_NAME} (${NVIDIA_VRAM} VRAM)"
        nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader 2>/dev/null | \
            awk -F', ' '{printf "  VRAM: %s/%s | Util: %s | Temp: %s°C\n", $1, $2, $3, $4}'
    else
        echo "${c_red}NVIDIA: non rilevata${c_reset}"
    fi
    
    echo
    echo "${c_green}Intel:${c_reset} (integra, gestisce il display)"
    
    echo
    echo "${c_bold}=== MODELLI OLLAMA CARICATI ===${c_reset}"
    local ps
    ps=$(ollama ps 2>/dev/null)
    if [[ -z "$ps" || "$ps" == "NAME"* ]]; then
        echo "  (nessun modello caricato)"
    else
        echo "$ps" | head -10
    fi
    
    echo
    echo "${c_bold}=== CONFIGURAZIONE BYTE-SWARMY ===${c_reset}"
    cd ~/Desktop/byte-swarmy 2>/dev/null && \
    python3 -c "
from GUI.settings_store import load_settings
s = load_settings()
print(f'  Strategia hardware: {s.get(\"hardware_strategy\", \"auto\")}')
print(f'  Auto-detect GPU: {s.get(\"detect_gpu_at_startup\", False)}')
" 2>/dev/null || echo "  (impossibile leggere configurazione)"
    
    echo
    echo "${c_bold}=== VARIANTI GPU DISPONIBILI ===${c_reset}"
    ollama list 2>/dev/null | grep "\-gpu" | head -10 || echo "  (nessuna variante GPU creata)"
}

show_help() {
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

# =================================================================
# MAIN
# =================================================================

cd "$(dirname "$0")"

case "${1:-}" in
    --status)
        detect_gpus
        show_status
        ;;
    --test)
        detect_gpus
        test_gpu_loading
        show_status
        ;;
    --help|-h)
        show_help
        ;;
    ""|--all)
        echo "${c_bold}${c_blue}"
        echo "╔═══════════════════════════════════════════════════════════╗"
        echo "║  BYTE-SWARMY — Setup Doppia GPU (NVIDIA + Intel)         ║"
        echo "╚═══════════════════════════════════════════════════════════╝"
        echo "${c_reset}"
        
        detect_gpus
        
        if [[ "$NVIDIA_PRESENT" != "true" ]]; then
            err "NVIDIA non rilevata — impossibile procedere"
            err "Installa i driver: sudo apt install nvidia-driver-580"
            exit 1
        fi
        
        echo
        info "Configurazione Ollama per usare solo NVIDIA..."
        configure_ollama_service
        
        echo
        info "Creazione varianti GPU dei modelli..."
        create_gpu_model_variants
        
        echo
        info "Test caricamento su GPU..."
        test_gpu_loading
        
        echo
        show_status
        
        echo
        ok "${c_green}${c_bold}Setup completato!${c_reset}"
        echo
        echo "Per usare i modelli GPU in BYTE-SWARMY:"
        echo "  1. Apri la GUI: ./avvia.sh"
        echo "  2. Vai su Impostazioni → Attori"
        echo "  3. Scegli i modelli con suffisso '-gpu'"
        echo "  4. Salva e riavvia orchestratore"
        echo
        echo "Per verificare lo stato: ./setup-dual-gpu.sh --status"
        ;;
    *)
        err "Opzione sconosciuta: $1"
        show_help
        exit 1
        ;;
esac
