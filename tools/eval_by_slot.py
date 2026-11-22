#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SLOT-5 — reporter deterministico di pass@1 per tipo di slot.

PREPARAZIONE, NON MISURA REALE. Il tool classifica i casi della eval suite
per tipo di slot (function/method/handler/widget/import/class/statement) e per
dimensione dell'output, e produce la tabella che SLOT-5 chiede in BENCH.md.
Senza `--results` usa dati SINTETICI con etichetta SIMULAZIONE: nessun
verdetto reale può venire fuori dal dry-run.

Un file di risultati live è accettato SOLO se dichiara `source: "live"` e
riporta evidenza termica coerente con il gate (`fan_rpm > 0`, `temp_c <= 60`).
Altrimenti il tool rifiuta il file con exit 2 — nessun surrogato.

Uso:
    .venv/bin/python tools/eval_by_slot.py                 # simulazione
    .venv/bin/python tools/eval_by_slot.py --json
    .venv/bin/python tools/eval_by_slot.py --results evals/slot_results.json
    .venv/bin/python tools/eval_by_slot.py --out DOCS/SLOT5_EVAL_REPORT.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "evals" / "cases.json"
MAX_TEMP_C = 60.0
SLOT_KINDS = ("function", "method", "handler", "widget", "import", "class",
              "statement")
SIZES = (("small", 0, 40), ("medium", 41, 120), ("large", 121, 10 ** 9))


def load_cases(path: Path = CASES) -> list[dict]:
    """Solo casi con expected_marker: gli altri sono gate/chiarimenti."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cases.json deve essere una lista")
    cases = [c for c in data if c.get("expected_marker")]
    if len(cases) < 10:
        raise ValueError(f"servono >=10 casi con marker, trovati {len(cases)}")
    return cases


def classify(case: dict) -> str:
    """Classificazione deterministica dal marker e dal testo del caso."""
    marker = str(case.get("expected_marker", ""))
    text = (str(case.get("title", "")) + " " +
            str(case.get("description", ""))).lower()
    refs = case.get("refs") or []
    if "import" in text or marker.startswith("import"):
        return "import"
    if "pyqt6" in refs or marker in {"QApplication", "QVBoxLayout",
                                     "pyqtSignal"}:
        return "widget"
    if marker.startswith("class "):
        return "class"
    if marker.startswith("def "):
        if "funzione" in text or "function" in text:
            return "function"
        if "metodo" in text:
            return "method"
        if "slot" in text or "handler" in text or "segnal" in text:
            return "handler"
        return "function"
    return "statement"


def size_bucket(lines: int) -> str:
    for name, low, high in SIZES:
        if low <= lines <= high:
            return name
    return "large"


def synthetic_results(cases: list[dict]) -> dict:
    """Risultati finti deterministici: servono solo a esercitare il reporter."""
    records = []
    for case in cases:
        digest = int(hashlib.sha256(case["id"].encode()).hexdigest(), 16)
        records.append({
            "case_id": case["id"],
            "slot_kind": classify(case),
            "output_lines": 20 + digest % 150,
            "passed": digest % 3 != 0,
        })
    return {"source": "simulation", "records": records}


def thermal_ok(data: dict) -> bool:
    evidence = data.get("thermal") or {}
    try:
        return (float(evidence.get("fan_rpm", 0)) > 0
                and float(evidence.get("temp_c", 999)) <= MAX_TEMP_C)
    except (TypeError, ValueError):
        return False


def load_results(path: Path, cases: list[dict]) -> tuple[dict, bool]:
    """Carica risultati reali; rifiuta source live senza evidenza termica."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError("results: serve un oggetto con 'records' lista")
    expected = {c["id"] for c in cases}
    seen = set()
    for row in data["records"]:
        for key in ("case_id", "slot_kind", "output_lines", "passed"):
            if key not in row:
                raise ValueError(f"record senza '{key}': {row!r}")
        if row["case_id"] not in expected:
            raise ValueError(f"case_id sconosciuto: {row['case_id']}")
        if row["case_id"] in seen:
            raise ValueError(f"case_id duplicato: {row['case_id']}")
        if row["slot_kind"] not in SLOT_KINDS:
            raise ValueError(f"slot_kind sconosciuto: {row['slot_kind']}")
        seen.add(row["case_id"])
    if data.get("source") == "live":
        if not thermal_ok(data):
            raise ValueError("source=live senza fan_rpm>0 e temp_c<=60: "
                             "nessun surrogato accettato")
    elif data.get("source") != "simulation":
        raise ValueError("source deve essere 'live' o 'simulation'")
    return data, data.get("source") == "live"


def summarize(data: dict) -> dict:
    by_kind: dict[str, list[bool]] = defaultdict(list)
    by_size: dict[str, list[bool]] = defaultdict(list)
    for row in data["records"]:
        ok = bool(row["passed"])
        by_kind[row["slot_kind"]].append(ok)
        by_size[size_bucket(int(row["output_lines"]))].append(ok)
    return {
        "by_slot": {k: {"passed": sum(v), "total": len(v),
                        "rate": round(sum(v) / len(v), 4)}
                    for k, v in sorted(by_kind.items())},
        "by_size": {k: {"passed": sum(v), "total": len(v),
                        "rate": round(sum(v) / len(v), 4)}
                    for k, v in sorted(by_size.items())},
        "total": len(data["records"]),
    }


def markdown(data: dict, summary: dict, live: bool) -> str:
    tag = "LIVE" if live else "DRY-RUN / SIMULAZIONE"
    lines = [
        "# SLOT-5 — pass@1 per tipo di slot",
        "",
        f"Modalità: **{tag}**",
        f"Casi con expected_marker: **{summary['total']}** "
        "(2 casi gate/chiarimento esclusi: pass@1 non si applica)",
        "",
        "| Tipo slot | Passati | Totale | pass@1 |",
        "|---|---:|---:|---:|",
    ]
    for kind, row in summary["by_slot"].items():
        lines.append(f"| `{kind}` | {row['passed']} | {row['total']} | "
                     f"{row['rate']:.2f} |")
    lines += ["", "| Dimensione output | Passati | Totale | pass@1 |",
              "|---|---:|---:|---:|"]
    ranges = {name: (f"{low}+ righe" if high >= 10 ** 9
                     else f"{low}-{high} righe")
              for name, low, high in SIZES}
    for size, row in summary["by_size"].items():
        lines.append(f"| `{size}` ({ranges[size]}) | {row['passed']} | "
                     f"{row['total']} | {row['rate']:.2f} |")
    lines += [
        "",
        "Dimensioni: small 0-40, medium 41-120, large 121+ righe. "
        "Nessun asse del radar viene alzato da questo report.",
        "",
    ]
    if not live:
        lines += [
            "> ⚠️ Risultati **sintetici**: `passed` deriva da un hash del case_id. "
            "Questa tabella **non è una misura** e non chiude SLOT-5.",
            "> Serve un file `--results` con `source: \"live\"`, evidenza termica "
            "(`fan_rpm > 0`, `temp_c <= 60`) e 12+ casi reali.",
            "",
        ]
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path,
                   help="file JSON di risultati live (default: simulazione)")
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
    text = json.dumps({"live": live, "summary": summary, **data},
                      indent=2, ensure_ascii=False) if args.json \
        else markdown(data, summary, live)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Report scritto: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
