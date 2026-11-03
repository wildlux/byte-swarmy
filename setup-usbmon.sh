#!/usr/bin/env bash
# setup-usbmon.sh — M9: ambiente usbmon/tshark per le catture USB di
# BYTE-SWARMY (M10/M11 leggono i dump prodotti con questo).
#
# USO (richiede root):
#     sudo ./setup-usbmon.sh install     # driver + tshark + permessi
#     usbmon-capture 3 usb3.json         # helper di cattura (installato)
#
# Cosa fa:
#   1. carica il kernel module `usbmon` (necessario per monitorare il
#      traffico USB in user space);
#   2. installa `tshark` (parser di dump) se assente;
#   3. crea il gruppo `usbmon` (o usa un gruppo esistente non-root) e
#      impone una udev rule per chmod 0660 su /dev/usbmon* — così la
#      cattura NON richiede sudo a ogni run;
#   4. installa `usbmon-capture` in /usr/local/bin.
#
# Limiti di sicurezza espliciti:
#   - il gruppo `usbmon` può leggere TUTTO il traffico USB: solo utenti
#     fidati; NON aggiungere utenti random al gruppo;
#   - le catture contengono payload potenzialmente sensibili (HID:
#     tastiera!). Non salvarle nel repo e non versionarle. I test
#     M10/M11 del progetto usano catture fabbricate.

set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "richiede root: sudo $0 install"; exit 1; }

CAPTURE_SCRIPT=/tmp/opencode/usbmon-capture.sh
[[ -f "$CAPTURE_SCRIPT" ]] || CAPTURE_SCRIPT="$(dirname "$0")/usbmon-capture.sh"

echo "== 1/4 usbmon kernel module =="
modprobe usbmon || echo "⚠ modprobe usbmon fallito (kernel senza CONFIG_USB_MON?)"
if lsmod | grep -q "^usbmon"; then
    echo "   usbmon attivo"
else
    echo "   ⚠ usbmon NON attivo: le catture non funzioneranno"
fi

echo "== 2/4 tshark =="
if ! command -v tshark >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update -qq && apt-get install -y -qq tshark
    else
        echo "⚠ nessun apt-get: installa tshark con il gestore locale"
    fi
fi
command -v tshark >/dev/null 2>&1 && echo "   tshark: $(tshark --version | head -1)" \
    || echo "   ⚠ tshark non disponibile"

echo "== 3/4 gruppo + udev rule (permessi NON-root sulle /dev/usbmon*) =="
getent group usbmon >/dev/null || groupadd --system usbmon
cat > /etc/udev/rules.d/99-usbmon-group.rules <<'RULE'
# usbmon leggibile al gruppo usbmon (catture senza sudo)
KERNEL=="usbmon*", MODE="0660", GROUP="usbmon"
RULE
udevadm control --reload-rules
for d in /dev/usbmon*; do
    [[ -e "$d" ]] && chown root:usbmon "$d" && chmod 0660 "$d"
done
echo "   regola installata: aggiungi il tuo utente con"
echo "   sudo usermod -aG usbmon $USER (poi riloggati)"

echo "== 4/4 helper di cattura =="
if [[ -f "$CAPTURE_SCRIPT" ]]; then
    install -m 0755 "$CAPTURE_SCRIPT" /usr/local/bin/usbmon-capture
    echo "   installato: /usr/local/bin/usbmon-capture"
else
    echo "   ⚠ usbmon-capture.sh non trovato accanto a $0: skip"
fi

echo "OK. Cattura di prova:"
echo "  ls /sys/kernel/debug/usb/devices   # inventario bus/EP"
echo "  usbmon-capture 3 /tmp/usb3.pcap    # 60s sul bus 3"
echo "  poi: python -m CORE.usb_protocol (M10) / CORE.usb_differential (M11)"
