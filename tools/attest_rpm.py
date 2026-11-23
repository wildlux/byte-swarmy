#!/usr/bin/env python3
"""attest_rpm.py — ricevuta RPM del tachometro e gate termico in un comando.

Chiede i campi al terminale (nessun valore passato a riga di comando),
scrive `data/state/rpm_attestation.json` (0600, gitignored), valida la
ricevuta con le stesse regole di `blocker_probe.py`, rilegge la temperatura
CPU **live** e scrive `fan_verified.json` solo se `fan_rpm > 0` e
`0 < temp_c <= 60`. Non esiste un modo per inventare i giri: il numero
deve essere digitato dall'operatore che ha letto il tachometro.

Uso (un solo comando):
    ./tools/attest_rpm.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import blocker_probe as bp  # noqa: E402

MIN_RPM = bp.MIN_ATTESTED_RPM
MAX_RPM = bp.MAX_ATTESTED_RPM


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        raise SystemExit("Annullato: nessuna ricevuta scritta")


def _cancel(value: str) -> bool:
    return value.lower() in {"q", "quit", "esci"}


def prompt_rpm() -> int:
    """Chiede l'RPM letto al tachometro; 'q' annulla, valori errati si ripetono."""
    print("Prima misura i giri della ventola CPU con un tachometro fisico.")
    print("Non digitare un valore stimato: serve la lettura dello strumento.")
    while True:
        raw = _ask("RPM letti (es. 2400) o 'q' per annullare: ")
        if _cancel(raw):
            raise SystemExit("Annullato: nessuna ricevuta scritta")
        try:
            rpm = int(raw)
        except ValueError:
            print("  non è un numero: ripeti (es. 2400)")
            continue
        if not MIN_RPM <= rpm <= MAX_RPM:
            print(f"  fuori dal range fisico {MIN_RPM}-{MAX_RPM}: ripeti")
            continue
        return rpm


def prompt_field(label: str, example: str, *, required: bool = True) -> str:
    """Campo obbligatorio: se vuoto si ripete; 'q' annulla senza scrivere."""
    if not required:
        return _ask(f"{label} (opzionale, Invio per saltare): ")
    while True:
        value = _ask(f"{label} (es. {example}) o 'q' per annullare: ")
        if _cancel(value):
            raise SystemExit("Annullato: nessuna ricevuta scritta")
        if value:
            return value
        print("  campo obbligatorio: scrivi una risposta oppure 'q' per annullare")


def build_attestation(rpm: int, instrument: str, method: str, operator: str,
                      notes: str, now: datetime | None = None) -> dict:
    """Costruisce la ricevuta con timestamp UTC generato al momento."""
    stamp = now or datetime.now(timezone.utc)
    return {
        "fan_rpm": int(rpm),
        "instrument": instrument.strip(),
        "method": method.strip(),
        "operator": operator.strip(),
        "measured_at": stamp.isoformat(timespec="seconds"),
        "notes": notes.strip(),
    }


def attest(attestation: dict, *, state_dir: Path | None = None,
           gate_file: Path | None = None, now: datetime | None = None) -> dict:
    """Scrive ricevuta + gate, senza mai accettare un RPM da CLI.

    Tutta la validazione è delegata a `blocker_probe`, source of truth del
    gate. La temperatura non viene mai letta dalla ricevuta.
    """
    state_dir = Path(state_dir) if state_dir else ROOT / "data" / "state"
    gate_path = Path(gate_file) if gate_file else bp.FAN_FILE
    path = state_dir / "rpm_attestation.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(attestation, indent=2,
                               ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)

    validated = bp.load_rpm_attestation(path, now=now)
    snapshot = bp.attested_rpm_snapshot(validated)
    bp.write_fan_verification(snapshot, out=gate_path)
    stored = bp.read_stored_fan(gate_path)
    return {
        "attestation_path": path,
        "gate_path": gate_path,
        "gate": stored,
        "snapshot": snapshot,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path,
                        help="cartella della ricevuta (default: data/state)")
    parser.add_argument("--gate-file", type=Path,
                        help="file del gate (default: data/state/fan_verified.json)")
    args = parser.parse_args(argv)

    rpm = prompt_rpm()
    instrument = prompt_field("Strumento", "tachometro ottico DT-6234B")
    method = prompt_field("Metodo", "lettura ottica su paletta attraverso griglia")
    operator = prompt_field("Operatore", "wildlux")
    notes = prompt_field("Note", "3 letture consecutive", required=False)
    attestation = build_attestation(rpm, instrument, method, operator, notes)

    print("\nRiepilogo di quanto verra' registrato:")
    for key, value in attestation.items():
        print(f"  {key}: {value}")
    confirm = _ask("\nRegistrare e aprire il gate? (s/N): ")
    if confirm.lower() != "s":
        raise SystemExit("Annullato: nessun file scritto")

    try:
        result = attest(attestation, state_dir=args.state_dir,
                        gate_file=args.gate_file)
    except ValueError as exc:
        print(f"RIFIUTO: {exc}", file=sys.stderr)
        print("Nessun gate valido: ripeti la misura con la CPU sotto 60 °C.",
              file=sys.stderr)
        return 1

    snap = result["snapshot"]
    gate = result["gate"]
    print(f"Ricevuta: {result['attestation_path']} (0600)")
    print(f"RPM attestati: {snap['fan_rpm']} — temperatura live: "
          f"{snap['cpu_temp_c']:.1f} °C")
    if gate["valid"]:
        print(f"Gate VALIDO: {result['gate_path']}")
        print("Ora puoi eseguire: .venv/bin/python tools/run_eval.py --live")
        return 0
    print(f"Gate NON VALIDO: {result['gate_path']} "
          f"({gate.get('reason', gate.get('checks'))})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
