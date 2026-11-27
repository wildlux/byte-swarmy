#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C2 — report misurabile del loop di auto-miglioramento.

Legge SOLO `state/` (corpus, proposte skill, gate, override) e produce una
tabella Markdown in `RAG/DOCS/`. Zero LLM, zero rete, zero GPU: è il quadro
deterministico che dice se il loop sta migliorando o solo girando.

Uso:
    .venv/bin/python tools/self_improvement_report.py            # scrive RAG/DOCS/
    .venv/bin/python tools/self_improvement_report.py --json     # solo stdout
    .venv/bin/python tools/self_improvement_report.py \
        --state-dir /tmp/state-finto --out /tmp/report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import feedback_corpus as fc  # noqa: E402

DEFAULT_STATE = ROOT / "state"
DEFAULT_OUT = ROOT / "RAG" / "DOCS" / "SELF_IMPROVEMENT_REPORT.md"


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def collect(state_dir=DEFAULT_STATE) -> dict:
    """Raccoglie le metriche dal solo state dir (fail-open su file rotti)."""
    state = Path(state_dir)
    triples: list = []
    for path in sorted((state / "feedback_corpus").glob("*.jsonl")):
        triples.extend(fc.load_task(path.stem, state_dir=state))

    verdicts = Counter(t.verdict for t in triples)
    total = len(triples)
    # Copertura retrieval: task con testo indicizzabile (title/description).
    task_ids = {t.task_id for t in triples}
    indexed = {t.task_id for t in triples
               if (t.title or t.description).strip()}
    coverage = round(len(indexed) / len(task_ids), 3) if task_ids else 0.0

    failures = _load_json(state / "skill_proposals" / "failures.json", {})
    proposals = Counter(
        str(p.get("status") or "unknown")
        for p in (failures.get("proposals") or {}).values()
        if isinstance(p, dict))
    gates = failures.get("gate_reports") or {}
    red_gates = sum(1 for g in gates.values()
                    if isinstance(g, dict) and not g.get("ok"))
    green_gates = sum(1 for g in gates.values()
                      if isinstance(g, dict) and g.get("ok"))
    override_issues = 0
    for name, known in (("auto_skill_keywords.json", "skill"),
                        ("auto_tool_keywords.json", "tool")):
        data = _load_json(state / name, None)
        if data is None:
            continue
        try:
            if known == "skill":
                from CORE.auto_skill import _known_skill_keys
                keys = _known_skill_keys()
            else:
                from CORE.auto_tool import _known_tool_keys
                keys = _known_tool_keys()
            from CORE.override_guard import validate_overrides
            override_issues += len(validate_overrides(data, keys).issues)
        except Exception:
            continue

    return {
        "state_dir": str(state),
        "corpus": fc.stats(triples) | {
            "failed_definitively": verdicts.get("failed_definitively", 0),
            "first_try_rate": round(
                sum(1 for t in triples if t.first_try) / total, 3)
            if total else 0.0,
        },
        "verdicts": {v: verdicts.get(v, 0) for v in fc.VALID_VERDICTS},
        "skill_proposals": {k: proposals.get(k, 0) for k in
                            ("pending", "approved", "rejected")},
        "gates": {"green": green_gates, "red": red_gates},
        "override_issues": override_issues,
        "retrieval": {"tasks": len(task_ids), "indexed": len(indexed),
                      "coverage": coverage},
    }


def _first_try_caveat(c: dict, r: dict) -> str:
    from tools import brutal_honesty_report as bh

    live = bh.live_snapshot()
    if live["accepted"] and live["cases"]:
        widget = live["by_slot"].get("widget", {})
        p, t = widget.get("passed", 0), widget.get("total", 0)
        rate = float(widget.get("rate", 0))
        gui = (f"Task GUI live: misurato {p}/{t} ({rate:.0%}); "
               + ("sopra" if rate >= 0.5 else "sotto")
               + " la soglia del 50%.")
    else:
        gui = "Task GUI live: 🔒 non misurato."
    return (
        "> ⚠️ **Brutal honesty**: il tasso primo colpo è calcolato sulle "
        f"{c['samples']} triple del corpus ({c['unique']} uniche, "
        f"{r['tasks']} task distinti). Sono **fixture interne** (test, "
        "adversarial, regressioni), non task utente reali: non dimostra "
        "la soglia '≥50% task chiusi al primo tentativo'. "
        + gui
    )


def _retrieval_caveat() -> str:
    return (
        "> ⚠️ La copertura indica solo che `title`/`description` sono "
        "indicizzabili; **non misura la qualità del retrieval** né che il "
        "contesto migliori le risposte."
    )


def markdown(m: dict) -> str:
    c = m["corpus"]
    v = m["verdicts"]
    p = m["skill_proposals"]
    g = m["gates"]
    r = m["retrieval"]
    total = c["samples"] or 1
    source = m["state_dir"]
    try:
        rel = Path(source).resolve().relative_to(ROOT)
        source = rel.as_posix()
    except ValueError:
        pass  # state dir fuori dal repo: lascia il path assoluto
    lines = [
        "# 📈 Self-Improvement Report",
        "",
        f"_Fonte: `{source}` — generato deterministicamente, zero LLM._",
        "",
        "## Corpus di feedback",
        "",
        "| Metrica | Valore |",
        "|---|---|",
        f"| Triple totali | {c['samples']} |",
        f"| Triple uniche | {c['unique']} |",
        f"| Task distinti | {r['tasks']} |",
        f"| Tasso primo colpo | {c['first_try_rate']:.3f} |",
        f"| Tasso correzione | {c['correction_rate']:.3f} |",
        "",
        "| Verdetto | Conteggio | Quota |",
        "|---|---|---|",
    ]
    for verdict, count in v.items():
        lines.append(f"| `{verdict}` | {count} | {count / total:.1%} |")

    lines += [
        "",
        _first_try_caveat(c, r),
        "",
        "## Gate e apprendimento",
        "",
        "| Metrica | Valore |",
        "|---|---|",
        f"| Gate verdi (skill) | {g['green']} |",
        f"| Gate rossi (skill) | {g['red']} |",
        f"| Proposte pending | {p['pending']} |",
        f"| Proposte approvate | {p['approved']} |",
        f"| Proposte rifiutate | {p['rejected']} |",
        f"| Override non conformi | {m['override_issues']} |",
        "",
        "## Copertura retrieval",
        "",
        "| Metrica | Valore |",
        "|---|---|",
        f"| Task con testo indicizzabile | {r['indexed']}/{r['tasks']} |",
        f"| Copertura | {r['coverage']:.1%} |",
        "",
        _retrieval_caveat(),
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state-dir", default=str(DEFAULT_STATE),
                    help="directory state da leggere (default: ./state)")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="file Markdown da scrivere (default: RAG/DOCS/)")
    ap.add_argument("--json", action="store_true",
                    help="stampa solo JSON, non scrive file")
    args = ap.parse_args(argv)

    metrics = collect(args.state_dir)
    if args.json:
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(metrics), encoding="utf-8")
    print(f"Report scritto: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
