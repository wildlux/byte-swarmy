#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase G — A/B deterministico delle varianti di prompt.

PREPARAZIONE, NON ESPERIMENTO REALE. Il modulo confronta varianti di prompt
sugli 11 casi della eval suite che hanno `expected_marker`; il solver usato
nel dry-run è FINTOS e il verdetto che ne esce è dichiarato SIMULAZIONE.
Nessun client LLM, nessuna rete, nessuna GPU: per il live serve un solver
reale passato dal chiamante e il gate termico verificato.

Uso:
    .venv/bin/python tools/eval_prompt_variants.py --dry-run
    .venv/bin/python tools/eval_prompt_variants.py --dry-run --json
    .venv/bin/python tools/eval_prompt_variants.py --dry-run \
        --out RAG/DOCS/PROMPT_VARIANTS_REPORT.md

Regola di promozione (scritta PRIMA di qualsiasi run live):
    variant >= baseline + MIN_DELTA  E  variant >= MIN_RATE  -> PROMOTE
    variant <= baseline                                     -> REJECT
    altrimenti                                              -> INCONCLUSIVE

Il verdetto live resta bloccato finché `data/state/fan_verified.json` non
contiene `fan_rpm > 0` e `temp_c <= 60`: nessun valore surrogato.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "evals" / "cases.json"
FAN_FILE = ROOT / "data" / "state" / "fan_verified.json"
MAX_TEMP_C = 60.0
MIN_RATE = 0.60
MIN_DELTA = 0.20

# Varianti dichiarate: cambia solo impaginazione/posizione delle refs,
# mai il motore. Nessuna variante inventa contenuto nuovo.
VARIANTS = ("baseline", "refs_off", "refs_first", "plan_compact")
BASELINE = "baseline"


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    description: str
    refs: tuple[str, ...]
    marker: str

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title,
                "description": self.description, "refs": list(self.refs),
                "marker": self.marker}


@dataclass(frozen=True)
class Arm:
    name: str
    passed: int
    total: int

    @property
    def rate(self) -> float:
        return round(self.passed / self.total, 4) if self.total else 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed,
                "total": self.total, "rate": self.rate}


def load_cases(path: Path = CASES) -> list[Case]:
    """Solo casi con expected_marker: gli altri sono gate/chiarimenti."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cases.json deve essere una lista")
    result = [Case(c["id"], c["title"], c["description"],
                   tuple(c.get("refs", [])), c["expected_marker"])
              for c in data if c.get("expected_marker")]
    if len(result) < 10:
        raise ValueError(f"servono >=10 casi con marker, trovati {len(result)}")
    return result


def task_set_id(cases: list[Case]) -> str:
    """Impronta del task set congelato, senza timestamp né random."""
    payload = [c.to_dict() for c in cases]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:12]


def hint_variant(case_id: str) -> str:
    """Variante che il solver finto premia per questo task (deterministica).

    NON è una misura di qualità: serve solo a far esercitare tutte le
    diramazioni della regola di promozione senza LLM.
    """
    digest = hashlib.sha256(case_id.encode()).hexdigest()
    return VARIANTS[int(digest, 16) % len(VARIANTS)]


def make_prompt(case: Case, variant: str) -> str:
    if variant not in VARIANTS:
        raise ValueError(f"variante sconosciuta: {variant!r}")
    lines = [f"# TASK {case.id}", case.title, "", case.description]
    if variant == "refs_off":
        pass
    elif variant == "refs_first":
        refs = ", ".join(case.refs) if case.refs else "nessuna"
        lines = [f"# TASK {case.id}", f"REFS: {refs}", "", case.title,
                 "", case.description]
    elif variant == "plan_compact":
        lines += ["", "REGOLE: 1 azione per turno, output <= 40 righe."]
        if case.refs:
            lines += ["REFS: " + ", ".join(case.refs)]
    else:  # baseline
        if case.refs:
            lines += ["", "REFS: " + ", ".join(case.refs)]

    if variant == hint_variant(case.id):
        lines += ["", f"HINT: {case.marker}"]
    return "\n".join(lines)


def fake_solver(prompt: str) -> str:
    """Solver sintetico: restituisce l'HINT se presente, altrimenti nulla."""
    for line in prompt.splitlines():
        if line.startswith("HINT: "):
            return line.split("HINT: ", 1)[1].strip()
    return "risposta generica senza marker"


def check_answer(answer: str, case: Case) -> bool:
    return case.marker.lower() in str(answer).lower()


def thermal_gate_ok(live: bool) -> bool:
    if not live:
        return True
    try:
        data = json.loads(FAN_FILE.read_text(encoding="utf-8"))
        return (float(data.get("fan_rpm", 0)) > 0
                and float(data.get("temp_c", 999)) <= MAX_TEMP_C)
    except (OSError, ValueError, TypeError):
        return False


def verdict(rate: float, baseline_rate: float) -> str:
    """Promuove solo chi vince con margine e tasso assoluto sufficiente."""
    delta = round(rate - baseline_rate, 4)
    if rate >= MIN_RATE and delta >= MIN_DELTA:
        return "PROMOTE"
    if delta <= 0:
        return "REJECT"
    return "INCONCLUSIVE"


def run_ab(live: bool = False, solver=None) -> dict:
    """Confronta le varianti; `solver` reale obbligatorio solo per il live."""
    if live and not thermal_gate_ok(live=True):
        raise RuntimeError("live bloccato: serve fan_verified.json con "
                           "fan_rpm > 0 e temp_c <= 60")
    if live and solver is None:
        raise RuntimeError("live richiede un solver reale esplicito: "
                           "il modello non è integrato in questo modulo")

    cases = load_cases()
    arms = {}
    for variant in VARIANTS:
        passed = 0
        for case in cases:
            answer = (solver(make_prompt(case, variant)) if live
                      else fake_solver(make_prompt(case, variant)))
            passed += int(check_answer(answer, case))
        arms[variant] = Arm(variant, passed, len(cases))

    base_rate = arms[BASELINE].rate
    results = {}
    for variant in VARIANTS:
        if variant == BASELINE:
            continue
        rate = arms[variant].rate
        results[variant] = {
            "rate": rate,
            "delta": round(rate - base_rate, 4),
            "verdict": verdict(rate, base_rate),
        }
    return {
        "live": live,
        "simulation": not live,
        "task_set_id": task_set_id(cases),
        "cases": [c.id for c in cases],
        "soglia": {"min_rate": MIN_RATE, "min_delta": MIN_DELTA},
        "arms": {name: arm.to_dict() for name, arm in arms.items()},
        "confronti": results,
    }


def markdown(result: dict) -> str:
    tag = "LIVE" if result["live"] else "DRY-RUN / SIMULAZIONE"
    lines = [
        "# A/B varianti prompt — Fase G",
        "",
        f"Modalità: **{tag}**",
        f"Task set congelato: `{result['task_set_id']}` "
        f"({len(result['cases'])} casi della eval suite con expected_marker)",
        "",
        "| Variante | Passati | Totale | Tasso |",
        "|---|---:|---:|---:|",
    ]
    for name, arm in result["arms"].items():
        lines.append(f"| `{name}` | {arm['passed']} | {arm['total']} | "
                     f"{arm['rate']:.2f} |")
    lines += [
        "",
        "| Variante vs baseline | Delta | Verdetto |",
        "|---|---:|---|",
    ]
    for name, row in result["confronti"].items():
        lines.append(f"| `{name}` | {row['delta']:+.2f} | "
                     f"**{row['verdict']}** |")
    lines += [
        "",
        f"Regola: rate >= {MIN_RATE:.2f} e delta >= {MIN_DELTA:.2f} → PROMOTE; "
        "delta <= 0 → REJECT; altrimenti INCONCLUSIVE.",
        "",
    ]
    if result["simulation"]:
        lines += [
            "> ⚠️ Il solver è **finto**: l'HINT è assegnato per hash del case_id. "
            "Questo verdetto **NON è un esperimento reale** e non autorizza "
            "alcuna promozione di prompt.",
            "> Il live richiede `data/state/fan_verified.json` con `fan_rpm > 0` "
            "e `temp_c <= 60`, più un solver reale passato dal chiamante.",
            "",
        ]
    else:
        lines += ["> Esecuzione live con solver reale: verificare comunque "
                  "il consenso umano prima della promozione.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true",
                        help="richiede gate termico e solver reale (non integrato)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, help="scrive il report Markdown")
    args = parser.parse_args(argv)

    try:
        result = run_ab(live=args.live)
    except RuntimeError as exc:
        print(f"BLOCCATO: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(result, indent=2, ensure_ascii=False) if args.json \
        else markdown(result)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Report scritto: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
