#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase H — giudice di qualità OPTIONALE e NON sovrano.

Il gate deterministico resta l'unica autorità. Il giudice (decision model,
"Timestral") è consultato SOLO a titolo consultivo quando il gate passa; il
suo parere viene LOGATO (accordo/disaccordo) ma NON può cambiare l'esito del
gate in nessuna direzione:

  - gate FAIL + giudice "approve"  -> final resta FAIL (mai ribaltato);
  - gate PASS + giudice "reject"   -> final resta PASS (solo dissenso loggato);
  - richiesta esplicita di override -> bloccata e segnalata, mai applicata.

Nessun LLM qui: il tool riceve pareri già prodotti esternamente. Un parere
con `source: "live"` è accettato SOLO con evidenza termica verificata
(`fan_rpm > 0`, `temp_c <= 60`); altrimenti viene rifiutato con exit 2.
Senza `--results` il tool genera pareri SINTETICI per esercitare la struttura
del report, dichiarati SIMULAZIONE.

Uso:
    .venv/bin/python tools/quality_judge.py                    # simulazione
    .venv/bin/python tools/quality_judge.py --json
    .venv/bin/python tools/quality_judge.py --results judge_results.json
    .venv/bin/python tools/quality_judge.py --out RAG/DOCS/QUALITY_JUDGE_REPORT.md

Criterio done Fase H: tool + report accordo gate↔giudice su 20 casi REALI.
I 13 casi della eval suite qui sono solo struttura, non misura.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "evals" / "cases.json"
MAX_TEMP_C = 60.0
VERDICTS = ("approve", "reject")


def load_cases(path: Path = CASES) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("cases.json deve essere una lista non vuota")
    return data


def thermal_ok(evidence: dict | None) -> bool:
    evidence = evidence or {}
    try:
        return (float(evidence.get("fan_rpm", 0)) > 0
                and float(evidence.get("temp_c", 999)) <= MAX_TEMP_C)
    except (TypeError, ValueError):
        return False


def adjudicate(case_id: str, gate_pass: bool,
               judge: str | None = None,
               override: bool = False) -> dict:
    """Applica l'invariante: il gate decide, il giudice solo consiglia.

    `override=True` simula un tentativo di sovrascrittura: viene segnalato
    e bloccato, mai applicato al verdetto finale.
    """
    gate = bool(gate_pass)
    if judge is not None and judge not in VERDICTS:
        raise ValueError(f"verdetto giudice sconosciuto: {judge!r} "
                         f"(ammessi: {VERDICTS})")

    if judge is None:
        agreement = "not_consulted"
    elif not gate:
        agreement = "judge_ignored_gate_fail"
    elif judge == "approve":
        agreement = "concur_pass"
    else:
        agreement = "judge_dissent"

    return {
        "case_id": case_id,
        "gate_pass": gate,
        "judge": judge,
        "agreement": agreement,
        "override_requested": bool(override),
        "override_blocked": bool(override),
        "final": gate,  # INVARIANTE: identico al gate, sempre.
    }


def synthetic_results(cases: list[dict]) -> dict:
    """Pareri finti deterministici: servono solo a esercitare il report."""
    records = []
    for case in cases:
        digest = int(hashlib.sha256(case["id"].encode()).hexdigest(), 16)
        gate = digest % 2 == 0
        judge = None if digest % 3 == 0 else (
            "approve" if digest % 5 else "reject")
        records.append(adjudicate(case["id"], gate, judge,
                                  override=bool(digest % 17 == 0)))
    return {"source": "simulation", "records": records}


def load_results(path: Path, cases: list[dict]) -> tuple[dict, bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError("results: serve un oggetto con 'records' lista")
    known = {c["id"] for c in cases}
    out = []
    for row in data["records"]:
        if not isinstance(row, dict):
            raise ValueError(f"record non valido: {row!r}")
        cid = row.get("case_id")
        if cid not in known:
            raise ValueError(f"case_id sconosciuto: {cid!r}")
        try:
            out.append(adjudicate(
                str(cid), row.get("gate_pass", False),
                row.get("judge"), row.get("override", False)))
        except ValueError as exc:
            raise ValueError(f"{cid}: {exc}") from exc
    source = data.get("source")
    if source == "live" and not thermal_ok(data.get("thermal")):
        raise ValueError("source=live senza fan_rpm>0 e temp_c<=60: "
                         "nessun parere live accettato")
    if source not in ("live", "simulation"):
        raise ValueError("source deve essere 'live' o 'simulation'")
    return {"source": source, "records": out}, source == "live"


def summarize(data: dict) -> dict:
    rows = data["records"]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["agreement"]] = counts.get(row["agreement"], 0) + 1
    consultati = [r for r in rows if r["agreement"] != "not_consulted"]
    concordi = [r for r in consultati
                if r["agreement"].startswith("concur")]
    overrides = [r for r in rows if r["override_blocked"]]
    # Invariante verificata a runtime, non solo nei test.
    assert all(r["final"] == r["gate_pass"] for r in rows), \
        "INVARIANTE VIOLATA: il giudice ha cambiato il gate"
    return {
        "totali": len(rows),
        "consultati": len(consultati),
        "concordi": len(concordi),
        "tasso_accordo": (round(len(concordi) / len(consultati), 4)
                          if consultati else None),
        "conteggi": counts,
        "override_bloccati": len(overrides),
        "gate_invariato": True,
    }


def markdown(data: dict, summary: dict, live: bool) -> str:
    tag = "LIVE" if live else "DRY-RUN / SIMULAZIONE"
    lines = [
        "# Fase H — giudice di qualità (mai sovrano)",
        "",
        f"Modalità: **{tag}**",
        "",
        "Il gate deterministico è l'unica autorità: il parere del giudice è "
        "consultivo e non cambia mai il verdetto finale.",
        "",
        "| Metrica | Valore |",
        "|---|---:|",
        f"| Casi | {summary['totali']} |",
        f"| Giudice consultato | {summary['consultati']} |",
        f"| Concordi | {summary['concordi']} |",
        f"| Tasso accordo | {summary['tasso_accordo']} |",
        f"| Override bloccati | {summary['override_bloccati']} |",
        f"| Gate invariato | {summary['gate_invariato']} |",
        "",
        "| Classificazione | Conteggio |",
        "|---|---:|",
    ]
    for key in sorted(summary["conteggi"]):
        lines.append(f"| `{key}` | {summary['conteggi'][key]} |")
    lines.append("")
    if not live:
        lines += [
            "> ⚠️ Pareri **sintetici** derivati da un hash del case_id: questa "
            "tabella **non è una misura** e non chiude Fase H.",
            "> Criterio done: report accordo gate↔giudice su **20 casi reali** "
            "con pareri `source: \"live\"` e gate termico verificato.",
            "",
        ]
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path,
                   help="file JSON di pareri (default: simulazione)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", type=Path, help="scrive il report Markdown")
    args = p.parse_args(argv)

    cases = load_cases()
    if args.results:
        try:
            data, live = load_results(args.results, cases)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"RIFIUTATO: {exc}", file=sys.stderr)
            return 2
    else:
        data, live = synthetic_results(cases), False
    summary = summarize(data)
    text = (json.dumps({"live": live, "summary": summary, **data},
                       indent=2, ensure_ascii=False) if args.json
            else markdown(data, summary, live))
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Report scritto: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
