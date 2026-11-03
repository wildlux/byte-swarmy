# -*- coding: utf-8 -*-
"""
usb_protocol.py — M10: traduzione descrittori / endpoint / payload USB.

Parser puro (zero dipendenze, zero I/O) per il fitto con M9
(usbmon/tshark):

  - `decode_setup(setup8)` → bmRequestType/bRequest/wValue/wIndex/
    wLength decodificati + anno nomi standard (GET_DESCRIPTOR,
    SET_CONFIGURATION, VENDOR(n(command)).
  - `parse_lsusb_descriptors(text)` → dict strutturato che viene
    dato da `lsusb -v` (device, interfacce, endpoint).
  - `describe_event(evento)` → riga umana leggibile.
  - `summarize(cattura)` → statistiche per ep/dir/tipo/setup.

Il formato evento atteso (schema abbondatamente rilassato):

    {"ts": float, "ep": int, "dir": "IN|OUT", "type": "control|bulk|...",
     "payload_len": int, "data": "hex..." (opzionale),
     "setup": "hex-8-bytes" (solo per i transfer di tipo control)}
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Tabelle spec USB 2.0 §9.3 / §9.4
# ---------------------------------------------------------------------------

_REQUEST_TYPES = {0x00: "standard", 0x01: "class", 0x02: "vendor"}
_RECIPIENTS = {
    0x00: "device", 0x01: "interface", 0x02: "endpoint", 0x03: "other",
    0x04: "port", 0x05: "hub",
}
_STD_REQUESTS = {
    0x00: "GET_STATUS", 0x01: "CLEAR_FEATURE", 0x03: "SET_FEATURE",
    0x05: "SET_ADDRESS", 0x06: "GET_DESCRIPTOR", 0x07: "SET_DESCRIPTOR",
    0x08: "GET_CONFIGURATION", 0x09: "SET_CONFIGURATION",
    0x0A: "GET_INTERFACE", 0x0B: "SET_INTERFACE", 0x0C: "SET_SYNCH_FRAME",
}
_DESCRIPTOR_TYPES = {
    0x01: "DEVICE", 0x02: "CONFIGURATION", 0x03: "STRING",
    0x04: "INTERFACE", 0x05: "ENDPOINT", 0x06: "DEVICE_QUALIFIER",
    0x07: "OTHER_SPEED_CONFIG", 0x0F: "BOS",
}
_TRANSFER_TYPES = {0: "control", 1: "isochronous", 2: "bulk", 3: "interrupt"}


def decode_setup(setup8: bytes) -> dict:
    """Spec §9.3: un packet setup di 8 bytes (little-endian 16-bit)."""
    if len(setup8) != 8:
        raise ValueError(f"setup deve essere 8 bytes: {len(setup8)}")
    bm = setup8[0]
    req = setup8[1]
    wvalue = (setup8[3] << 8) | setup8[2]
    windex = (setup8[5] << 8) | setup8[4]
    wlength = (setup8[7] << 8) | setup8[6]
    # spec USB 2.0: D7=direction, D6..5=type, D4..0=recipient
    rtype_val = (bm >> 5) & 0x03
    rtype = {0: "standard", 1: "class", 2: "vendor"}.get(
        rtype_val, f"reserved({rtype_val})")
    direction = "IN" if (bm & 0x80) else "OUT"
    recipient = _RECIPIENTS.get(bm & 0x1F, f"reserved({bm & 0x1F})")
    if rtype == "standard":
        name = _STD_REQUESTS.get(req, f"standard({req:#04x})")
    elif rtype == "vendor":
        name = f"VENDOR({req:#04x})"
    else:
        name = f"class({req:#04x})"
    out: dict = {
        "bmRequestType": bm,
        "bRequest": req,
        "wValue": wvalue,
        "wIndex": windex,
        "wLength": wlength,
        "direction": direction,
        "type": rtype,
        "recipient": recipient,
        "name": name,
    }
    if name == "GET_DESCRIPTOR":
        dtype = (wvalue >> 8) & 0xFF
        out["descriptor_type"] = _DESCRIPTOR_TYPES.get(dtype,
                                                       f"type({dtype:#04x})")
        out["descriptor_index"] = wvalue & 0xFF
        if dtype == 0x03:
            out["string_langid"] = f"{windex:#06x}"
    if name == "SET_CONFIGURATION":
        out["configuration_value"] = wvalue & 0xFF
    return out


def describe_setup(setup8: bytes) -> str:
    """Riga umana per un control setup: `OUT standard GET_DESCRIPTOR
    descriptor=STRING index=3 wLength=64`."""
    d = decode_setup(setup8)
    bits = [
        d["direction"], d["type"], d["name"],
        f"recipient={d['recipient']}",
    ]
    if "descriptor_type" in d:
        bits.append(f"descriptor={d['descriptor_type']}"
                    f"({d['descriptor_index']})")
    if "configuration_value" in d:
        bits.append(f"conf={d['configuration_value']}")
    bits.append(f"wLength={d['wLength']}")
    return " ".join(bits)


# ---------------------------------------------------------------------------
# Descrittori da `lsusb -v` (testo → struttura)
# ---------------------------------------------------------------------------

_ENDPOINT_RE = re.compile(r"^bEndpointAddress\s+(0x[0-9a-fA-F]+)")
_BCD_RE = re.compile(r"^bcdDevice\s+(\d+)\s*$")
_UINT_RE = re.compile(r"^([A-Za-z]\w+)\s+(0x[0-9a-fA-F]+|\d+)(?:\s.*)?$")
_IFACE_RE = re.compile(r"^bInterfaceNumber\s+(\d+)$")
_IPROD_RE = re.compile(r"^iProduct\s+\d+\s+(.+)$")
_IMANU_RE = re.compile(r"^iManufacturer\s+\d+\s+(.+)$")
_DESC_RE = re.compile(r"^Device Descriptor:", re.I)
_CONF_RE = re.compile(r"^Config(?:uration)?( Descriptor)?:|^bConfigurationValue",
                      re.I)
_IFACE_HDR_RE = re.compile(r"^Interface Descriptor:", re.I)
_EP_HDR_RE = re.compile(r"^  \/*Endpoint Descriptor:", re.I)


def parse_lsusb_descriptors(text: str) -> dict:
    """Parsa l'output di `lsusb -v -d VID:PID`.

    Il parser è indulgente: righe non riconosciute sono ignorate
    (completo di funzioni che il testo disponibile da tshark non ha).
    Torna:
        {"idVendor": int, "idProduct": int, "bcdDevice": int,
         "device_class": int, "manufacturer": str, "product": str,
         "interfaces": [{"number": x, "endpoints": [...]}...],
         "endpoints": [dict plani di singola EP]}
    """
    dev: dict = {"interfaces": [], "endpoints": []}
    current_ep: dict | None = None       # EP corrente bagno cambiad
    current_iface: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _DESC_RE.match(line) or _CONF_RE.match(line):
            continue
        if _IFACE_HDR_RE.match(line):
            current_ep = None
            current_iface = {"number": None, "endpoints": []}
            dev["interfaces"].append(current_iface)
            continue
        if _EP_HDR_RE.match(line):
            current_ep = None
            continue

        m = _IFACE_RE.match(line)
        if m and current_iface is not None:
            current_iface["number"] = int(m.group(1))
            continue

        m = _IMANU_RE.match(line)
        if m:
            dev["manufacturer"] = m.group(1).strip()
            continue
        m = _IPROD_RE.match(line)
        if m:
            dev["product"] = m.group(1).strip()
            continue

        m = _ENDPOINT_RE.match(line)
        if m:
            num = int(m.group(1), 0)
            current_ep = {
                "address": f"{num:#04x}",
                "endpoint": num & 0x0F,
                "direction": "IN" if (num & 0x80) else "OUT",
            }
            dev["endpoints"].append(current_ep)
            if current_iface is not None:
                current_iface["endpoints"].append(current_ep)
            continue

        m = _BCD_RE.match(line)
        if m:
            dev["bcdDevice"] = int(m.group(1), 0)
            continue

        m = _UINT_RE.match(line)
        if not m:
            continue
        key, num = m.group(1), int(m.group(2), 0)
        if key in ("idVendor", "idProduct", "bcdDevice"):
            dev[key] = num
        elif key == "bDeviceClass":
            dev["device_class"] = num
        elif key == "bmAttributes" and current_ep is not None:
            current_ep["type"] = _TRANSFER_TYPES.get(num & 0x03,
                                                     num & 0x03)
        elif key == "wMaxPacketSize" and current_ep is not None:
            current_ep["max_packet_size"] = num
        elif key == "bInterval" and current_ep is not None:
            current_ep["interval"] = num
    return dev


# ---------------------------------------------------------------------------
# Eventi e statistiche
# ---------------------------------------------------------------------------

def describe_event(event: dict) -> str:
    """Riga umana di un evento: `10.40962  EP3 OUT bulk setup=GET_DESCRIPTOR 64B`."""
    ts = float(event.get("ts", 0.0) or 0.0)
    ep = event.get("ep", "?")
    direction = str(event.get("dir", "?")).upper()
    ttype = str(event.get("type", "control")).lower()
    data = event.get("data")
    if isinstance(data, str) and data:
        data = data.replace(":", "").replace(" ", "")
        plen = int(event.get("payload_len", len(data) // 2))
    else:
        plen = int(event.get("payload_len", 0) or 0)
    label = ttype
    setup = event.get("setup")
    if setup:
        if isinstance(setup, str):
            try:
                setup = bytes.fromhex(
                    setup.replace(":", "").replace(" ", ""))
            except ValueError:
                setup = None
                label = f"{ttype} setup=<malformato>"
        if setup is not None:
            try:
                d = decode_setup(setup)
                label = f"{ttype} setup={d['name']}"
            except ValueError:
                label = f"{ttype} setup=<malformato>"
    return f"{ts:.5f}  EP{ep} {direction} {label} {plen}B"


def summarize(cattura: list) -> dict:
    """Statistiche di una sequenza di eventi: direzioni, EP, tipi,
    richieste di setup, payload dimensione massima."""
    stats = {"events": 0, "dirs": {}, "eps": {}, "types": {},
             "setup_requests": {}, "max_payload": 0}
    for ev in cattura or []:
        stats["events"] += 1
        d = str(ev.get("dir", "?")).upper()
        stats["dirs"][d] = stats["dirs"].get(d, 0) + 1
        ep = str(ev.get("ep", "?"))
        stats["eps"][ep] = stats["eps"].get(ep, 0) + 1
        t = str(ev.get("type", "control")).lower()
        stats["types"][t] = stats["types"].get(t, 0) + 1
        setup = ev.get("setup")
        if setup:
            try:
                if isinstance(setup, str):
                    setup = bytes.fromhex(
                        setup.replace(":", "").replace(" ", ""))
                info = decode_setup(setup)
                key = f"{info['type']}:{info['name']}"
                stats["setup_requests"][key] = \
                    stats["setup_requests"].get(key, 0) + 1
            except (ValueError, TypeError):
                stats["setup_requests"]["<malformato>"] = \
                    stats["setup_requests"].get("<malformato>", 0) + 1
        plen = int(ev.get("payload_len", 0) or 0)
        stats["max_payload"] = max(stats["max_payload"], plen)
    return stats
