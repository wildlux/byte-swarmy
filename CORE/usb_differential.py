# -*- coding: utf-8 -*-
"""
usb_differential.py — M11: analisi differenziale tra catture USB.

Confronta due catture (lista di eventi come da `CORE/usb_protocol.py`)
e segnala le differenze RILEVANTI per la sicurezza:

  - endpoint nuovi/scomparsi e cambio di tipo (bulk → interrupt);
  - richieste di setup nuove o che cambiano frequenza (es. una request
    vendor prima rara e ora continua);
  - pattern di payload (media e payload per ep/dir);
  - punteggio di RISCHIO con motivazioni esplicite:
      * HIGH   → request vendor/class nuove dopo l'aggiornamento;
      * MEDIUM → nuovi interrupt/bulk endpoint, salti di frequenza
                 (x5+) su request esistenti, payload medio > x2,
                 cambio di tipo transfer;
      * LOW    → nessuna delle differenze sopra.

Pure: nessun I/O (testabile con catture fabbricate).

CLI: `python -m CORE.usb_differential cattura1.json cattura2.json`
"""

from __future__ import annotations

import json
from collections import Counter

from CORE.usb_protocol import decode_setup, summarize


def _setup_key(ev: dict) -> str | None:
    setup = ev.get("setup")
    if not setup:
        return None
    try:
        if isinstance(setup, str):
            setup = bytes.fromhex(setup.replace(":", "").replace(" ", ""))
        d = decode_setup(setup)
        return f"{d['type']}:{d['name']}"
    except (ValueError, TypeError):
        return "<malformato>"


def diff_captures(before: list, after: list) -> dict:
    """Confronta due catture e ritorna il report differenziale + rischio."""
    r = {
        "before": summarize(before or []),
        "after": summarize(after or []),
        "new_endpoints": [],
        "gone_endpoints": [],
        "type_changes": [],
        "new_setup_requests": [],
        "frequency_changes": {},
        "payload_increase": {},
        "risk": "low",
        "risk_reasons": [],
    }

    # ---- endpoint: chiave (ep, dir), il tipo è un attributo --------------
    before_ep: dict[tuple, str] = {}
    after_ep: dict[tuple, str] = {}
    for ev in before or []:
        k = (ev.get("ep"), str(ev.get("dir", "")).upper())
        before_ep.setdefault(k, str(ev.get("type", "control")).lower())
    for ev in after or []:
        k = (ev.get("ep"), str(ev.get("dir", "")).upper())
        after_ep.setdefault(k, str(ev.get("type", "control")).lower())

    for k in sorted(after_ep.keys() - before_ep.keys(), key=str):
        r["new_endpoints"].append(
            {"ep": k[0], "dir": k[1], "type": after_ep[k]})
    for k in sorted(before_ep.keys() - after_ep.keys(), key=str):
        r["gone_endpoints"].append(
            {"ep": k[0], "dir": k[1], "type": before_ep[k]})
    for k in sorted(before_ep.keys() & after_ep.keys(), key=str):
        if before_ep[k] != after_ep[k]:
            r["type_changes"].append(
                {"ep": k[0], "dir": k[1], "from": before_ep[k],
                 "to": after_ep[k]})

    # ---- richieste di setup: nuova / salto di frequenza ------------------
    b_req = Counter(x for ev in (before or [])
                    if (x := _setup_key(ev)) is not None)
    a_req = Counter(x for ev in (after or [])
                    if (x := _setup_key(ev)) is not None)
    for k in sorted(a_req.keys() - b_req.keys(), key=str):
        r["new_setup_requests"].append(
            {"request": k, "count_after": a_req[k]})
    for k in sorted(a_req.keys() & b_req.keys(), key=str):
        if b_req[k] >= 1 and a_req[k] >= 5 * b_req[k]:
            r["frequency_changes"][k] = {"from": b_req[k], "to": a_req[k]}

    # ---- payload medio per (ep, dir): crescita > x2 ----------------------
    keys = set(before_ep.keys()) | set(after_ep.keys())
    for k in sorted(keys, key=str):
        b_len = [ev.get("payload_len", 0) for ev in (before or [])
                 if (ev.get("ep"), str(ev.get("dir", "")).upper()) == k]
        a_len = [ev.get("payload_len", 0) for ev in (after or [])
                 if (ev.get("ep"), str(ev.get("dir", "")).upper()) == k]
        if a_len and b_len:
            b_avg = sum(b_len) / len(b_len)
            a_avg = sum(a_len) / len(a_len)
            if b_avg > 0 and a_avg > 2 * b_avg:
                r["payload_increase"][f"{k[0]}/{k[1]}"] = {
                    "avg_before": round(b_avg, 1),
                    "avg_after": round(a_avg, 1)}

    # ---- scoring di rischio ---------------------------------------------
    reasons = []
    if any(x["type"] in ("interrupt", "bulk") for x in r["new_endpoints"]):
        reasons.append("nuovi endpoint interrupt/bulk (canale dati) dopo "
                       "l'aggiornamento")
    if any(x["request"].startswith(("vendor:", "class:"))
           for x in r["new_setup_requests"]):
        reasons.append("nuove request vendor/class (controllo "
                       "non-standard) dopo l'aggiornamento")
    if r["frequency_changes"]:
        reasons.append("salti di frequenza (x5+) su setup request "
                       "già presenti")
    if r["payload_increase"]:
        reasons.append("payload medio cresciuto oltre x2 su alcuni endpoint")
    if r["type_changes"]:
        reasons.append("cambio di tipo transfer su endpoint esistenti")
    r["risk_reasons"] = reasons
    if any("vendor" in x or "class" in x for x in reasons):
        r["risk"] = "high"
    elif reasons:
        r["risk"] = "medium"
    else:
        r["risk"] = "low"
    return r


def explain_diff(diff: dict) -> str:
    """Report leggibile (per log e per la GUI)."""
    lines = [f"RISCHIO: {diff.get('risk', 'low').upper()}"]
    lines.extend(f"  • {x}" for x in diff.get("risk_reasons", []))
    lines.append(f"events: {diff['after'].get('events', 0)} "
                 f"(prima: {diff['before'].get('events', 0)})")
    labels = (
        ("new_endpoints", "ENDPOINT NUOVI"),
        ("gone_endpoints", "ENDPOINT RIMOSSI"),
        ("type_changes", "CAMBI DI TIPO"),
        ("new_setup_requests", "REQUEST NUOVE"),
        ("frequency_changes", "SALTI FREQUENZA"),
        ("payload_increase", "CRESCITA PAYLOAD"),
    )
    for section, title in labels:
        if diff.get(section):
            lines.append(f"  {title}: "
                         f"{json.dumps(diff[section], ensure_ascii=False)}")
    return "\n".join(lines)


# -----------------------------------------------------------------------
# Mini-CLI
# -----------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        with open(sys.argv[1], encoding="utf-8") as f:
            a = json.load(f)
        with open(sys.argv[2], encoding="utf-8") as f:
            b = json.load(f)
        print(explain_diff(diff_captures(a, b)))
    else:
        print("uso: python -m CORE.usb_differential "
              "cattura_before.json cattura_after.json")
