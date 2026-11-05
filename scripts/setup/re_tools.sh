#!/usr/bin/env bash
# setup_re_tools.sh — Installa i tool di sistema per Reverse Engineering
#
# Installa:
#   - radare2 (r2)
#   - tshark (Wireshark CLI)
#   - binutils (file, readelf, nm, strings, objdump)
#   - Ghidra (download + symlink, NON apt)
#   - yara (per yara-python)
#
# Usage:
#   ./scripts/setup/re_tools.sh           # installa tutto
#   ./scripts/setup/re_tools.sh --check   # solo verifica ambiente
#   ./scripts/setup/re_tools.sh --no-ghidra  # salta Ghidra (richiede Java 17+)
#
# Requisiti:
#   - Ubuntu/Debian (usa apt)
#   - sudo privileges
#   - Per Ghidra: Java 17+ (sudo apt install openjdk-17-jdk)

set -euo pipefail

# Colori
GREEN='\033[92m'; RED='\033[91m'; YELLOW='\033[93m'; BLUE='\033[94m'; RESET='\033[0m'
ok() { echo -e "${GREEN}✓${RESET} $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET} $1"; }
info() { echo -e "${BLUE}ℹ${RESET} $1"; }

# Risolvi root progetto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

NO_GHIDRA=false
ONLY_CHECK=false

for arg in "$@"; do
    case "$arg" in
        --check) ONLY_CHECK=true ;;
        --no-ghidra) NO_GHIDRA=true ;;
        -h|--help)
            head -22 "$0" | tail -20
            exit 0
            ;;
    esac
done

echo ""
echo "============================================================"
echo "  🐝 byte-swarmy — RE tools setup"
echo "============================================================"
echo ""

# === 1. Verifica apt ===
if ! command -v apt &>/dev/null; then
    fail "Questo script richiede apt (Ubuntu/Debian)."
    echo "Per altre distro installa manualmente:"
    echo "  - radare2"
    echo "  - tshark"
    echo "  - binutils"
    echo "  - Ghidra (https://ghidra-sre.org/)"
    exit 1
fi

# === 2. Verifica sistema ===
check_tool() {
    local name="$1"
    if command -v "$name" &>/dev/null; then
        ok "$name trovato: $(command -v "$name")"
        return 0
    else
        fail "$name non trovato"
        return 1
    fi
}

echo "=== Stato attuale ==="
check_tool file || true
check_tool readelf || true
check_tool nm || true
check_tool strings || true
check_tool objdump || true
check_tool r2 || true
check_tool tshark || true
check_tool yara || true
if [ "$NO_GHIDRA" = false ]; then
    check_tool analyzeHeadless || true
fi
echo ""

if [ "$ONLY_CHECK" = true ]; then
    echo "Solo verifica (--check). Per installare: ./scripts/setup/re_tools.sh"
    exit 0
fi

# === 3. Installa pacchetti apt ===
echo "=== Installazione pacchetti apt ==="
info "Aggiorno apt..."
sudo apt update -qq

info "Installo: radare2 tshark binutils file coreutils yara"
sudo apt install -y radare2 tshark binutils file coreutils yara

ok "Pacchetti apt installati"
echo ""

# === 4. Ghidra (se non skipped) ===
if [ "$NO_GHIDRA" = false ]; then
    if command -v analyzeHeadless &>/dev/null; then
        ok "Ghidra già installato (analyzeHeadless in PATH)"
    else
        echo "=== Installazione Ghidra ==="

        # Verifica Java
        if ! command -v java &>/dev/null; then
            warn "Java non trovato. Installo openjdk-17..."
            sudo apt install -y openjdk-17-jdk
        fi

        # Verifica versione Java
        JAVA_VER=$(java -version 2>&1 | head -1 | awk -F '"' '{print $2}' | cut -d. -f1)
        if [ -z "$JAVA_VER" ] || [ "$JAVA_VER" -lt 17 ]; then
            warn "Java versione $JAVA_VER (richiesta 17+). Aggiorno..."
            sudo apt install -y openjdk-17-jdk
            sudo update-alternatives --set java /usr/lib/jvm/java-17-openjdk-amd64/bin/java
        fi

        # Versione Ghidra (URL formato: ghidra_X.Y.Z_PUBLIC_DATE.zip)
        info "Cerco versione Ghidra..."
        GHIDRA_VERSION="11.4.3"
        GHIDRA_BUILD_DATE="20251203"
        GHIDRA_URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/ghidra_${GHIDRA_VERSION}_PUBLIC_${GHIDRA_BUILD_DATE}.zip"
        GHIDRA_ZIP="/tmp/ghidra_${GHIDRA_VERSION}.zip"
        GHIDRA_DIR="/opt/ghidra"

        info "Download Ghidra v${GHIDRA_VERSION}..."
        info "URL: $GHIDRA_URL"

        rm -f "$GHIDRA_ZIP"
        wget --show-progress -L -O "$GHIDRA_ZIP" "$GHIDRA_URL" || {
            fail "Download fallito. URL: $GHIDRA_URL"
            fail "Verifica su: https://github.com/NationalSecurityAgency/ghidra/releases"
            exit 1
        }

        if ! unzip -l "$GHIDRA_ZIP" >/dev/null 2>&1; then
            fail "File scaricato non è zip valido. URL: $GHIDRA_URL"
            rm -f "$GHIDRA_ZIP"
            exit 1
        fi

        info "Estraggo in /opt/..."
        sudo unzip -q -o "$GHIDRA_ZIP" -d /opt/
        EXTRACTED_DIR="ghidra_${GHIDRA_VERSION}_PUBLIC"
        if [ -d "/opt/$EXTRACTED_DIR" ] && [ ! -d "$GHIDRA_DIR" ]; then
            sudo mv "/opt/$EXTRACTED_DIR" "$GHIDRA_DIR"
        elif [ -d "/opt/$EXTRACTED_DIR" ] && [ -d "$GHIDRA_DIR" ]; then
            sudo rm -rf "$GHIDRA_DIR"
            sudo mv "/opt/$EXTRACTED_DIR" "$GHIDRA_DIR"
        fi

        # Crea symlink in /usr/local/bin
        if [ -f "$GHIDRA_DIR/support/analyzeHeadless" ]; then
            sudo ln -sf "$GHIDRA_DIR/support/analyzeHeadless" /usr/local/bin/analyzeHeadless
            sudo chmod +x /usr/local/bin/analyzeHeadless
            ok "Ghidra installato: analyzeHeadless -> /usr/local/bin/"
        else
            fail "analyzeHeadless non trovato dopo estrazione"
            exit 1
        fi

        # Cleanup
        rm -f "$GHIDRA_ZIP"
    fi
    echo ""
fi

# === 5. Pip packages ===
echo "=== Installazione pip packages ==="
if [ -f "$ROOT/requirements_re.txt" ]; then
    info "Installo requirements_re.txt..."
    if [ -f "$ROOT/.venv/bin/pip" ]; then
        "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements_re.txt"
    else
        pip install -r "$ROOT/requirements_re.txt"
    fi
    ok "Pip packages installati"
else
    warn "requirements_re.txt non trovato in $ROOT"
    warn "Installalo manualmente: pip install capstone r2pipe pyshark pefile lief scapy yara-python"
fi
echo ""

# === 6. Verifica finale ===
echo "=== Verifica finale ==="
check_tool file
check_tool readelf
check_tool nm
check_tool strings
check_tool objdump
check_tool r2
check_tool tshark
check_tool yara
if [ "$NO_GHIDRA" = false ]; then
    check_tool analyzeHeadless
fi
echo ""

# Self-test Python
echo "=== Self-test Python bindings ==="
python3 -c "
import sys
sys.path.insert(0, '$ROOT')

# Verifica singoli moduli
try:
    import capstone
    print(f'  ✓ capstone v{capstone.__version__ if hasattr(capstone, \"__version__\") else \"?\"}')
except ImportError as e:
    print(f'  ✗ capstone: {e}')

try:
    import r2pipe
    print(f'  ✓ r2pipe')
except ImportError as e:
    print(f'  ✗ r2pipe: {e}')

try:
    import pyshark
    print(f'  ✓ pyshark')
except ImportError as e:
    print(f'  ✗ pyshark: {e}')

try:
    import pefile
    print(f'  ✓ pefile v{pefile.__version__}')
except ImportError as e:
    print(f'  ✗ pefile: {e}')

try:
    import lief
    print(f'  ✓ lief')
except ImportError as e:
    print(f'  ✗ lief: {e}')

try:
    import scapy
    print(f'  ✓ scapy v{scapy.__version__ if hasattr(scapy, \"__version__\") else \"?\"}')
except ImportError as e:
    print(f'  ✗ scapy: {e}')

try:
    import yara
    print(f'  ✓ yara-python')
except ImportError as e:
    print(f'  ✗ yara-python: {e}')
"

echo ""
if [ -f "$ROOT/CORE/re_tools.py" ]; then
    info "Self-test completo del modulo RE:"
    python3 "$ROOT/CORE/re_tools.py" --check
fi

echo ""
ok "Setup completato!"
echo ""
echo "Per testare su un binario reale:"
echo "  python3 CORE/re_tools.py --call binary_info /bin/ls"
echo "  python3 CORE/re_tools.py --call extract_strings /bin/ls"
echo "  python3 CORE/re_tools.py --call disassemble_capstone /bin/ls"
echo ""
echo "Per integrare nel worker, aggiungi in CORE/tools.py:"
echo "  from CORE.re_tools import RE_TOOLS, call_re_tool"
echo ""
