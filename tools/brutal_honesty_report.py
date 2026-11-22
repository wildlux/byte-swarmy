#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report deterministico 'brutal honesty' — Cycle 100.

Legge SOLO fonti locali verificabili:

* `pyflakes` sul codice attivo (escluso `tests/archiviati`);
* `CONFIG/config.toml` (fast lane / best_of_n);
* il corpus di feedback in `data/state` (triple, unici, first-try);
* i contatori live di `tools/gen_grafici.py`;
* le correzioni già applicate a `DOCS/MIGLIORAMENTI.md` e
  `DOCS/SELF_IMPROVEMENT_REPORT.md`.

Nessun LLM, rete o GPU, nessun timestamp: stesso input → stesso Markdown.

Uso:
    .venv/bin/python tools/brutal_honesty_report.py
    .venv/bin/python tools/brutal_honesty_report.py --out DOCS/BRUTAL_HONESTY_REPORT.md
    .venv/bin/python tools/brutal_honesty_report.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import feedback_corpus as fc  # noqa: E402
from tools.self_improvement_report import (  # noqa: E402
    DEFAULT_STATE, collect,
)

SOURCE_DIRS = ("CORE", "GUI", "tools", "SAFETY", "tests")
OUT = ROOT / "DOCS" / "BRUTAL_HONESTY_REPORT.md"


def pyflakes_snapshot() -> dict:
    """Conteggio reale di pyflakes sul codice attivo (no archiviati)."""
    files = sorted(
        p.relative_to(ROOT).as_posix()
        for base in SOURCE_DIRS
        for p in (ROOT / base).rglob("*.py")
        if "archiviati" not in p.parts
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pyflakes", *files],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        return {"available": False, "findings": 0, "undefined": [],
                "error": str(exc)}
    if "No module named pyflakes" in proc.stderr:
        return {"available": False, "findings": 0, "undefined": [],
                "error": "pyflakes non installato"}
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return {
        "available": True,
        "findings": len(lines),
        "undefined": [line for line in lines if "undefined name" in line][:5],
        "error": "",
    }


def _find_key(obj, key: str):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    return None


def config_snapshot() -> dict:
    """Stato runtime del best-of-N, letto dal TOML vero."""
    text = (ROOT / "CONFIG" / "config.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    fast = _find_key(data, "enabled")
    # `enabled` compare in più sezioni: serve quello di [fast_lane].
    m = re.search(r"(?ms)^\[fast_lane\]\s*$(.*?)(?=^\[|\Z)", text)
    if m:
        fast_m = re.search(r"(?m)^enabled\s*=\s*(true|false)\b", m.group(1))
        if fast_m:
            fast = fast_m.group(1) == "true"
    return {
        "fast_lane_enabled": bool(fast),
        "best_of_n": int(_find_key(data, "best_of_n") or 1),
    }


def corpus_snapshot(state_dir=None) -> dict:
    """Numeri reali del corpus: totale, unici, task, first-try, provenienza."""
    state = Path(state_dir or DEFAULT_STATE)
    groups = []
    triples = []
    for path in sorted((state / "feedback_corpus").glob("*.jsonl")):
        loaded = fc.load_task(path.stem, state_dir=state)
        triples.extend(loaded)
        if loaded:
            groups.append({
                "file": path.name,
                "n": len(loaded),
                "first_try": sum(1 for t in loaded if t.first_try),
            })
    stats = fc.stats(triples)
    # Prima occorrenza per task: se esiste un triple first_try, il task è
    # stato chiuso al primo colpo. Tenere l'ultima occorrenza falserebbe 0.95.
    unique = {}
    for triple in triples:
        unique.setdefault(triple.task_id, triple)
    tasks = len(unique)
    total = len(triples)
    return {
        "total": total,
        "unique": stats.get("unique", len(unique)),
        "tasks": tasks,
        "first_try_rate": round(
            sum(1 for t in triples if t.first_try) / total, 3) if total else 0.0,
        "unique_first_try_rate": round(
            sum(1 for t in unique.values() if t.first_try) / tasks, 3)
        if tasks else 0.0,
        "groups": sorted(groups, key=lambda g: (-g["n"], g["file"]))[:6],
    }


def retrieval_snapshot(state_dir=None) -> dict:
    """La 'copertura 100%' misura solo testo indicizzabile, non qualità."""
    r = collect(state_dir or DEFAULT_STATE)["retrieval"]
    return {"indexed": r["indexed"], "tasks": r["tasks"],
            "coverage": r["coverage"]}


def docs_snapshot() -> dict:
    """Le correzioni devono essere nel markdown, non solo nella chat."""
    improvements = (ROOT / "DOCS" / "MIGLIORAMENTI.md").read_text(
        encoding="utf-8")
    self_report = (ROOT / "DOCS" / "SELF_IMPROVEMENT_REPORT.md").read_text(
        encoding="utf-8")
    return {
        "link_presente": "BRUTAL_HONESTY_REPORT.md" in improvements,
        "zero_warning_falso_rimosso": (
            "✅ raggiunto (474 → 0)" not in improvements
            and "Zero Warning: pyflakes 474 → 0" not in improvements),
        "fast_lane_attivo_rimosso": (
            "best-of-N attivo (fast lane)" not in improvements),
        "meccanismi_documentati": (
            "meccanismi documentati/implementati" in improvements),
        "corpus_caveat": "fixture interne" in self_report,
        "retrieval_caveat": "non misura la qualità del retrieval" in self_report,
    }


def collect_all(state_dir=None) -> dict:
    from tools import gen_grafici as g

    return {
        "pyflakes": pyflakes_snapshot(),
        "config": config_snapshot(),
        "corpus": corpus_snapshot(state_dir),
        "retrieval": retrieval_snapshot(state_dir),
        "docs": docs_snapshot(),
        "counters": {
            "mechanisms": g.mechanism_count(),
            "skills": g.skill_count(),
            "auto_tools": g.auto_tool_count(),
        },
    }


DOC_LABELS = {
    "link_presente": "Link al report da `DOCS/MIGLIORAMENTI.md`",
    "zero_warning_falso_rimosso": "Claim '0 warning ✅ raggiunto' rimosso",
    "fast_lane_attivo_rimosso": "Claim 'fast lane attivo' rimosso",
    "meccanismi_documentati": "Meccanismi definiti 'documentati/implementati'",
    "corpus_caveat": "Caveat 'fixture interne' nel report self-improvement",
    "retrieval_caveat": "Caveat 'non misura la qualità' nel report retrieval",
}


def _table(headers, rows, aligns=None) -> list:
    aligns = aligns or ["---"] * len(headers)
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(aligns) + "|"]
    out += ["| " + " | ".join(str(cell) for cell in row) + " |"
            for row in rows]
    return out


def _verdict_rows(s: dict) -> list:
    pf, cfg = s["pyflakes"], s["config"]
    corpus, ret = s["corpus"], s["retrieval"]
    counts = s["counters"]

    if not pf["available"]:
        zero = ("⚠️ NON VERIFICABILE", pf["error"])
    elif pf["findings"] == 0:
        zero = ("✅ PASS", "0 finding di pyflakes")
    else:
        zero = ("❌ FAIL", f"{pf['findings']} finding di pyflakes")
    if pf["undefined"]:
        zero = (zero[0], zero[1] + "; undefined: "
                + "; ".join(pf["undefined"][:2]))
    lane = ("⚠️ DISABILITATO" if not cfg["fast_lane_enabled"]
            else "✅ ATTIVO")
    lane_detail = (f"`fast_lane.enabled={str(cfg['fast_lane_enabled']).lower()}`, "
                   f"`best_of_n={cfg['best_of_n']}`")

    return [
        ("Zero Warning (pyflakes)", *zero),
        ("best-of-N 'attivo (fast lane)'", lane, lane_detail),
        ("First-try 0.958 come task reali", "⚠️ FIXTURE INTERNE",
         f"{corpus['total']} triple, {corpus['unique']} uniche, "
         f"{corpus['tasks']} task distinti; "
         f"{corpus['unique_first_try_rate']:.3f} sugli unici"),
        ("Copertura retrieval 100%", "⚠️ DEFINIZIONE RISTRETTA",
         f"{ret['indexed']}/{ret['tasks']}: solo presenza di testo "
         "indicizzabile, non qualità del retrieval"),
        ("41 meccanismi 'attivi'", "⚠️ DOCUMENTATI/IMPLEMENTATI",
         f"{counts['mechanisms']} righe contate; non tutti abilitati a runtime"),
        ("Auto-skill 23 / auto-tool 30 (Cycle 86)", "⚠️ STALE",
         f"oggi {counts['skills']} skill / {counts['auto_tools']} tool"),
    ]


def _doc_rows(docs: dict) -> list:
    return [(label, "✅" if docs[key] else "❌")
            for key, label in DOC_LABELS.items()]


def _corpus_rows(corpus: dict) -> list:
    return [(f"`{g['file']}`", g["n"], g["first_try"])
            for g in corpus["groups"]]


def markdown(s: dict) -> str:
    corpus = s["corpus"]
    lines = [
        "# 🧾 Brutal honesty — verifica dei report",
        "",
        "_Generato deterministicamente da `tools/brutal_honesty_report.py` "
        "— zero LLM, zero rete, zero GPU, zero timestamp._",
        "",
        "Scopo: dire cosa è **veramente verificabile** nei report e nei "
        "documenti di `DOCS/`. Quando un numero cambia, cambia questo file: "
        "non si scrive a mano un verdetto diverso dai dati.",
        "",
        "## Verdetto sintetico",
        "",
    ]
    lines += _table(("Affermazione", "Verdetto", "Evidenza"),
                    _verdict_rows(s))
    lines += ["", "## Correzione applicata ai documenti", ""]
    lines += _table(("Controllo", "Stato"), _doc_rows(s["docs"]))
    lines += [
        "",
        "## Da dove viene il 0.958",
        "",
        f"Il tasso `first_try` è `{corpus['first_try_rate']:.3f}` su "
        f"{corpus['total']} triple. Il corpus contiene **fixture interne** "
        "(test, adversarial, regressioni), non task utente reali: "
        "non può dimostrare la soglia '≥50% task chiusi al primo tentativo' "
        "del radar. Sugli unici task distinti il valore è "
        f"`{corpus['unique_first_try_rate']:.3f}`; il task GUI live resta "
        "🔒 non misurato.",
        "",
    ]
    lines += _table(("File corpus", "Triple", "First-try"),
                    _corpus_rows(corpus), ["---", "---:", "---:"])
    lines += [
        "",
        "## Limiti che NON sono stati toccati",
        "",
        "- I valori del radar restano **giudizi espliciti**, non misure "
        "derivate: questo report corregge le frasi, non alza o abbassa gli assi.",
        "- La suite completa non è stata rieseguita in questo ciclo: "
        "l'ultima green resta il run3 del 2026-11-19.",
        "- E1/E2 sono gate validati su campioni sintetici, non una garanzia "
        "repo-wide; E3 live e A/B live restano 🔒 bloccati termicamente.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT), help="file Markdown da scrivere")
    ap.add_argument("--json", action="store_true", help="stampa solo JSON")
    args = ap.parse_args(argv)

    snapshot = collect_all()
    if args.json:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(snapshot), encoding="utf-8")
    print(f"Report scritto: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
