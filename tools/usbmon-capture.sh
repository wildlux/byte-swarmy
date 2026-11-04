#!/usr/bin/env bash
# usbmon-capture.sh — M9 (helper di setup-usbmon.sh): cattura il traffico
# USB di UN bus tramite usbmon (tshark formato pcapp, compatibile con la
# lettura di M10/M11 dopo conversione).
#
# USO (senza root, richiede setup-usbmon.sh fatto):
#     usbmon-capture <bus> <outfile> [secondi=60]
#     es: usbmon-capture 3 /tmp/bus3.pcap 30
#
# NOTA SICUREZZA: il dump contiene payload HID (frasi da tastiera):
# questo file NON va versionato né condiviso. Tipicalmente si esegue:
#   chmod 600 /tmp/bus3.pcap
set -euo pipefail

BUS="${1:?uso: usbmon-capture <bus> <file> [secondi=60]}"
OUT="${2:?uso: usbmon-capture <bus> <file> [secondi=60]}"
SECS="${3:-60}"

command -v tshark >/dev/null 2>&1 || { echo "tshark non installato (setup-usbmon.sh install)"; exit 1; }
[[ -e "/dev/usbmon$BUS" ]] || { echo "/dev/usbmon$BUS inesistente: modprobe usbmon?"; exit 1; }

echo "== cattura bus USB $BUS per ${SECS}s → $OUT =="
timeout "$SECS" tshark -i "usbmon$BUS" -w "$OUT" || rc=$?
[[ ${rc:-0} -eq 0 ]] || [[ ${rc:-0} -eq 124 ]]  # 124 = timeout normale
chmod 600 "$OUT" 2>/dev/null || true
echo "fatto: $OUT ($(( $(stat -c%s "$OUT") / 1024 )) KB)"
echo "dump dati: tshark -r $OUT -T fields -e usb.capdata 2>/dev/null | head"
