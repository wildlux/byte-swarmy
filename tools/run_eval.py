#!/usr/bin/env python3
"""run_eval.py — eval suite interna (Fase A, mini-SWE-bench).

Carica i casi da evals/cases.json e produce un report per asse e per
granularità. Due modalità:

  --dry-run  (default): valida i casi e stampa il riepilogo (zero LLM).
  --live     : esegue i casi col worker (richiede gate termico VALIDO).

Uso:
    .venv/bin/python tools/run_eval.py                 # dry-run
    .venv/bin/python tools/run_eval.py --json         # dry-run JSON
    .venv/bin/python tools/run_eval.py --live         # richiede fan_verified.json
    .venv/bin/python tools/run_eval.py --live --model-key worker_coder_big

Il `--live` NON è una misura finché non gira: rifiuta l'avvio senza
`fan_verified.json` valido (RPM attestati + temperatura ≤60 °C riletta
live) e rilegge la temperatura prima di OGNI caso, interrompendo se supera
60 °C. I risultati sono veri solo se prodotti da un worker reale: non
esiste modalità che generi `passed=True` sintetico.

Il file scritto (`data/state/eval_live_results.json`, gitignored) è nel
formato accettato da `tools/eval_by_slot.py --results`: `source: "live"`,
evidenza termica e un record per caso con `expected_marker`. I 2 casi
gate/chiarimento sono elencati in `excluded_cases`: pass@1 non si applica.

Ogni caso ha: id, title, description, axis (asse radar), granularity
(small/medium/large), refs, expected_marker o expected_fail/expected_clarify.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "evals" / "cases.json"
DEFAULT_RESULTS = ROOT / "data" / "state" / "eval_live_results.json"
PROJECT_ROOT = ROOT / "project"
MAX_TEMP_C = 60.0
VALID_AXES = {
    "Task GUI (creazione)", "Modifiche minime", "Refactoring mecc.",
    "Gate / verifica", "Fedeltà API", "Chiarimenti ambigui",
    "Architettura", "Memoria / contesto",
}
VALID_GRAN = {"small", "medium", "large"}


class GateError(RuntimeError):
    """Gate termico non valido: il run live non deve nemmeno iniziare."""


def load_cases(path: Path = CASES) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cases.json deve essere una lista")
    return data


def validate_cases(cases: list[dict]) -> list[str]:
    errors = []
    ids = set()
    for i, c in enumerate(cases):
        for key in ("id", "title", "description", "axis", "granularity"):
            if key not in c:
                errors.append(f"caso #{i}: manca '{key}'")
        if c.get("id") in ids:
            errors.append(f"caso #{i}: id duplicato '{c['id']}'")
        ids.add(c.get("id"))
        if c.get("axis") not in VALID_AXES:
            errors.append(f"{c.get('id')}: axis sconosciuto '{c.get('axis')}'")
        if c.get("granularity") not in VALID_GRAN:
            errors.append(f"{c.get('id')}: granularity sconosciuta")
    if len(cases) < 12:
        errors.append(f"servono >=12 casi, trovati {len(cases)}")
    return errors


def summarize(cases: list[dict]) -> dict:
    by_axis = defaultdict(int)
    by_gran = defaultdict(int)
    for c in cases:
        by_axis[c["axis"]] += 1
        by_gran[c["granularity"]] += 1
    return {
        "total": len(cases),
        "by_axis": dict(by_axis),
        "by_granularity": dict(by_gran),
    }


def _sample_temp(temp_fn=None) -> float:
    """Temperatura CPU live. `temp_fn` serve solo ai test offline."""
    if temp_fn is not None:
        return float(temp_fn())
    from tools import blocker_probe as bp
    return float(bp.read_cpu_temp_c()[0])


def require_gate(fan_file: Path | None = None, temp_fn=None) -> dict:
    """Rifiuta il run se il gate salvato non è valido o se è già caldo.

    Riutilizza `blocker_probe.read_stored_fan` come source of truth: nessun
    RPM viene letto da riga di comando e la temperatura NON viene presa dal
    gate file, ma riletta dai sensori live.
    """
    from tools import blocker_probe as bp
    path = fan_file or bp.FAN_FILE
    stored = bp.read_stored_fan(path)
    if not stored["valid"]:
        checks = ", ".join(f"{k}={v}" for k, v in
                           stored.get("checks", {}).items()) or stored["reason"]
        raise GateError(f"fan_verified.json NON VALIDO ({checks})")
    temp_c = _sample_temp(temp_fn)
    if not 0.0 < temp_c <= MAX_TEMP_C:
        raise GateError(f"temperatura live {temp_c:.1f} °C fuori dal gate "
                        f"(0 < T <= {MAX_TEMP_C:.0f})")
    return {
        "fan_rpm": int(stored["fan_rpm"]),
        "temp_c": round(temp_c, 1),
        "gate_measured_at": stored.get("measured_at"),
        "gate_sources": stored.get("sources", {}),
        "gate_file": str(path),
    }


def verify_case(case: dict, worker, result: str,
                project_root: Path = PROJECT_ROOT) -> dict:
    """Verdetto deterministico del caso: marker nei file toccati dal worker.

    `passed=True` richiede: nessun prefisso ERROR, marker presente nei file
    .py scritti e nessun retry interno del worker (`last_attempts <= 1`).
    Nessun LLM viene interrogato qui.
    """
    marker = str(case.get("expected_marker") or "")
    touched = getattr(getattr(worker, "tools", None), "touched_python", {}) or {}
    text_parts: list[str] = []
    for _rel, full in touched.items():
        path = Path(full)
        if not path.is_file():
            continue
        try:
            text_parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    marker_found = bool(marker) and any(marker in text for text in text_parts)
    result_text = str(result)
    error = result_text[:300] if result_text.startswith("ERROR") else None
    attempts = int(getattr(worker, "last_attempts", 1) or 1)
    return {
        "passed": bool(marker_found and not error and attempts <= 1),
        "output_lines": sum(len(t.splitlines()) for t in text_parts),
        "marker": marker,
        "marker_found": marker_found,
        "attempts": attempts,
        "error": error,
    }


def run_live(cases: list[dict], gate: dict, worker_factory,
             temp_fn=None, out_path: Path = DEFAULT_RESULTS,
             project_root: Path = PROJECT_ROOT) -> dict:
    """Esegue i casi con un factory iniettato e scrive i risultati live.

    Il worker viene creato per caso (memoria isolata). Se la temperatura
    sale oltre il gate, il run si interrompe e i risultati parziali restano
    marcati `aborted`: `eval_by_slot.py` li rifiuterà perché l'evidenza
    termica non è più entro 60 °C. Nessun esito viene mai sintetizzato.
    """
    from tools.eval_by_slot import classify

    if int(gate.get("fan_rpm") or 0) <= 0:
        raise GateError("fan_rpm mancante nel gate")
    if not 0.0 < float(gate.get("temp_c", 0)) <= MAX_TEMP_C:
        raise GateError("temperatura iniziale fuori dal gate")

    marker_cases = [c for c in cases if c.get("expected_marker")]
    excluded = [{"case_id": c["id"],
                 "reason": "nessun expected_marker: pass@1 non applicabile"}
                for c in cases if not c.get("expected_marker")]
    records: list[dict] = []
    max_temp = float(gate["temp_c"])
    aborted = False
    abort_reason: str | None = None

    for case in marker_cases:
        temp_c = _sample_temp(temp_fn)
        max_temp = max(max_temp, temp_c)
        if not 0.0 < temp_c <= MAX_TEMP_C:
            aborted = True
            abort_reason = f"temperatura {temp_c:.1f} °C prima del caso {case['id']}"
            break
        verdict = {
            "case_id": case["id"],
            "slot_kind": classify(case),
            "axis": case.get("axis"),
            "granularity": case.get("granularity"),
            "passed": False,
            "output_lines": 0,
            "marker": str(case.get("expected_marker") or ""),
            "marker_found": False,
            "attempts": 1,
            "error": None,
        }
        try:
            worker = worker_factory(case)
            task = {
                "id": case["id"],
                "title": case.get("title", ""),
                "description": case.get("description", ""),
                "type": "implement",
                "source": "eval_live",
                "axis": case.get("axis"),
            }
            result = worker.execute(task)
            verdict.update(verify_case(case, worker, result, project_root))
        except Exception as exc:  # un errore è un FALLIMENTO, mai un pass
            verdict["error"] = f"{type(exc).__name__}: {exc}"[:300]
        records.append(verdict)

    thermal = dict(gate)
    thermal["temp_c"] = round(max_temp, 1)
    data = {
        "source": "live",
        "thermal": thermal,
        "records": records,
        "excluded_cases": excluded,
        "aborted": aborted,
        "abort_reason": abort_reason,
        "total_cases": len(cases),
        "executed_cases": len(records),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return data


def build_default_worker_factory(model_key: str = "worker_coder"):
    """Factory reale: importa CORE solo quando il gate è già stato superato."""
    def factory(case: dict):
        import logging
        from CORE.orchestrator import load_config
        from CORE.memory import AgentMemory
        from CORE.ollama_client import ModelClient
        from CORE.tools import ToolSet
        from CORE.worker import Worker

        config = load_config(str(ROOT / "CONFIG" / "config.toml"))
        log = logging.getLogger("eval_live")
        models = ModelClient(config, log)
        tools = ToolSet(config, log)
        agent_id = f"eval-{case['id']}"
        memory = AgentMemory(agent_id,
                             Path(config["paths"]["state_dir"]), models, log)
        return Worker(agent_id, model_key, tools, memory, models, log)
    return factory


def _live_text(data: dict, out_path: Path) -> str:
    lines = [
        "Esecuzione LIVE — solo risultati prodotti da worker reale.",
        f"Gate: RPM {data['thermal']['fan_rpm']} "
        f"(attestati), T max {data['thermal']['temp_c']:.1f} °C",
        f"Casi: {data['executed_cases']}/{data['total_cases']} con marker; "
        f"{len(data['excluded_cases'])} esclusi",
        "",
        "| Caso | Slot | pass@1 | Righe | Errore |",
        "|---|---|:-:|---:|---|",
    ]
    for row in data["records"]:
        err = (row.get("error") or "—").replace("|", "\\|")
        lines.append(f"| {row['case_id']} | {row['slot_kind']} | "
                     f"{'✅' if row['passed'] else '❌'} | "
                     f"{row['output_lines']} | {err} |")
    lines += ["", f"Risultati: {out_path}"]
    if data["aborted"]:
        lines += ["", f"⚠️ INTERROTTO: {data['abort_reason']}. "
                      "L'evidenza termica non è più valida: il reporter "
                      "rifiuterà questi risultati."]
    lines += ["", "Nessun verdetto Middle: serve il controllo dei task GUI "
                  "e il verdetto in DOCS/BENCH.md."]
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true",
                        help="esegue i casi col worker (richiede gate termico)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fan-file", type=Path,
                        help="gate da usare (default: data/state/fan_verified.json)")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS,
                        help="file JSON dei risultati live (gitignored)")
    parser.add_argument("--model-key", default="worker_coder",
                        help="modello dei worker (default: worker_coder)")
    args = parser.parse_args(argv)

    cases = load_cases()
    errors = validate_cases(cases)

    if args.live:
        if errors:
            print("ERRORI DI VALIDAZIONE: " + "; ".join(errors), file=sys.stderr)
            return 1
        if Path.cwd().resolve() != ROOT.resolve():
            print("RIFIUTO: --live va lanciato dalla radice del repository "
                  "(i path della config sono relativi).", file=sys.stderr)
            return 2
        try:
            gate = require_gate(args.fan_file)
        except GateError as exc:
            print(f"RIFIUTO: {exc}", file=sys.stderr)
            print("Procedura: DOCS/RPM_MEASUREMENT_PROCEDURE.md",
                  file=sys.stderr)
            return 2
        data = run_live(cases, gate, build_default_worker_factory(args.model_key),
                        out_path=args.results)
        print(json.dumps(data, indent=2, ensure_ascii=False) if args.json
              else _live_text(data, args.results))
        return 3 if data["aborted"] else 0

    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors,
                          "summary": summarize(cases)}, indent=2,
                         ensure_ascii=False))
    else:
        print(f"Eval suite: {len(cases)} casi")
        if errors:
            print("ERRORI DI VALIDAZIONE:")
            for e in errors:
                print(f"  - {e}")
        else:
            print("Validazione OK.")
        s = summarize(cases)
        print("\nPer asse:")
        for axis, n in sorted(s["by_axis"].items()):
            print(f"  {axis}: {n}")
        print("\nPer granularità:")
        for g, n in sorted(s["by_granularity"]):
            print(f"  {g}: {n}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
