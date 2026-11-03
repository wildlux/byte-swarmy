"""audit_gate.py — Quality gate per progetti target.

Fornisce `check_audit_gate(project_path)` che esegue l'audit mensile su un
progetto e ritorna un `GateResult` con stato PASS/FAIL e dettagli per
categoria. Usato da:
  - GUI/audit_project_panel.py (pannello "Audit Progetto" nella Plancia)
  - CORE/orchestratore.py (gate bloccante prima di Worker.execute)

Modalità (da CONFIG/config.toml [audit.gates]):
  - "off"       → gate disattivato, sempre PASS
  - "advisory"  → log warning se FAIL, ma non blocca
  - "strict"    → blocca l'esecuzione del task se FAIL

Le categorie "bloccanti" (porte esposte, tunnel, import banditi, file
critici, config) determinano il gate. Le categorie "advisory" (vars
inutilizzate, codice morto) sono solo informative.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

_BASE = Path(__file__).resolve().parent.parent


@dataclass
class CategoryResult:
    """Risultato di una singola categoria di audit."""
    id: str
    name: str
    icon: str
    status: str  # "PASS" | "FAIL" | "SKIP"
    blocking: bool
    critical: int = 0
    warning: int = 0
    total: int = 0
    message: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass
class GateResult:
    """Risultato completo del gate di un progetto."""
    project_path: str
    project_name: str
    gate: str  # "PASS" | "FAIL"
    mode: str  # "off" | "advisory" | "strict"
    timestamp: str
    categories: list[CategoryResult] = field(default_factory=list)
    total_findings: int = 0
    critical_count: int = 0
    warning_count: int = 0
    findings: list[dict] = field(default_factory=list)
    error: Optional[str] = None  # messaggio se l'audit non è partito

    @property
    def passed(self) -> bool:
        """True se il gate è PASS (tenendo conto della modalità)."""
        if self.mode == "off":
            return True
        return self.gate == "PASS"

    @property
    def blocks_execution(self) -> bool:
        """True se il gate blocca l'esecuzione (strict + FAIL)."""
        return self.mode == "strict" and self.gate == "FAIL"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def load_gate_config() -> dict:
    """Carica la configurazione del gate da CONFIG/config.toml.

    Ritorna un dict con chiavi: enabled, mode, target, categories.
    Se la sezione [audit.gates] non esiste, ritorna default (off).
    """
    config_path = _BASE / "CONFIG" / "config.toml"
    if not config_path.exists():
        return {"enabled": False, "mode": "off", "target": "auto",
                "categories": []}
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(config_path, "rb") as f:
            cfg = tomllib.load(f)
        gate_cfg = cfg.get("audit", {}).get("gates", {})
        return {
            "enabled": gate_cfg.get("enabled", False),
            "mode": gate_cfg.get("mode", "advisory"),
            "target": gate_cfg.get("target", "auto"),
            "categories": gate_cfg.get("categories", []),
        }
    except Exception as e:
        return {"enabled": False, "mode": "off", "target": "auto",
                "categories": [], "error": str(e)}


def check_audit_gate(project_path: str | Path,
                     mode: Optional[str] = None) -> GateResult:
    """Esegue l'audit gate su project_path.

    Args:
        project_path: path assoluto della directory del progetto da auditare
        mode: modalità override ("off"|"advisory"|"strict"). Se None, legge
              da CONFIG/config.toml [audit.gates].mode

    Returns:
        GateResult con stato PASS/FAIL e dettagli per categoria.
    """
    from datetime import datetime, timezone
    target = Path(project_path)
    cfg = load_gate_config()
    effective_mode = mode or cfg.get("mode", "advisory")

    # Mode off → gate sempre PASS
    if effective_mode == "off" or not cfg.get("enabled", False) and effective_mode != "off" and mode is None:
        # Se non esplicitamente richiesto e config dice off → PASS
        if cfg.get("mode", "off") == "off" and mode is None:
            return GateResult(
                project_path=str(target),
                project_name=target.name,
                gate="PASS",
                mode="off",
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                categories=[],
                error="Gate disattivato (mode=off in config.toml)",
            )

    # Esegui l'audit via subprocess (isolamento: se crasha, non porta giù l'orchestratore)
    try:
        result = subprocess.run(
            [sys.executable, str(_BASE / "tests" / "test_monthly_audit.py"),
             "--target", str(target), "--json"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_BASE),
        )
        if result.returncode not in (0, 1) or not result.stdout.strip():
            return GateResult(
                project_path=str(target),
                project_name=target.name,
                gate="FAIL",
                mode=effective_mode,
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                error=f"Audit subprocess fallito (exit {result.returncode}): {result.stderr[:300]}",
            )
        report = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return GateResult(
            project_path=str(target),
            project_name=target.name,
            gate="FAIL",
            mode=effective_mode,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            error="Audit timeout (>120s)",
        )
    except json.JSONDecodeError as e:
        return GateResult(
            project_path=str(target),
            project_name=target.name,
            gate="FAIL",
            mode=effective_mode,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            error=f"Risposta audit non valida JSON: {e}",
        )
    except Exception as e:
        return GateResult(
            project_path=str(target),
            project_name=target.name,
            gate="FAIL",
            mode=effective_mode,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            error=f"Errore inatteso: {e}",
        )

    # Converti il report in GateResult
    categories = [
        CategoryResult(
            id=c["id"], name=c["name"], icon=c["icon"],
            status=c["status"], blocking=c["blocking"],
            critical=c.get("critical", 0), warning=c.get("warning", 0),
            total=c.get("total", 0), message=c.get("message", ""),
        )
        for c in report.get("categories", [])
    ]
    summary = report.get("summary", {})
    return GateResult(
        project_path=str(target),
        project_name=report.get("target_name", target.name),
        gate=summary.get("gate", "PASS"),
        mode=effective_mode,
        timestamp=report.get("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        categories=categories,
        total_findings=summary.get("total", 0),
        critical_count=summary.get("critical", 0),
        warning_count=summary.get("warning", 0),
        findings=report.get("findings", []),
    )


def save_gate_status(project_path: str | Path, result: GateResult) -> Path:
    """Salva lo stato del gate in <project>/.audit_status.json.

    Permette alla GUI di mostrare l'ultimo stato noto senza rilanciare
    l'audit ogni volta.
    """
    target = Path(project_path)
    status_file = target / ".audit_status.json"
    try:
        status_file.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except OSError:
        pass  # se il progetto è read-only, non bloccare
    return status_file


def load_gate_status(project_path: str | Path) -> Optional[GateResult]:
    """Carica l'ultimo stato del gate salvato per project_path.

    Returns None se non c'è stato salvato.
    """
    target = Path(project_path)
    status_file = target / ".audit_status.json"
    if not status_file.exists():
        return None
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        return GateResult(
            project_path=data["project_path"],
            project_name=data["project_name"],
            gate=data["gate"],
            mode=data["mode"],
            timestamp=data["timestamp"],
            categories=[CategoryResult(**c) for c in data.get("categories", [])],
            total_findings=data.get("total_findings", 0),
            critical_count=data.get("critical_count", 0),
            warning_count=data.get("warning_count", 0),
            findings=data.get("findings", []),
            error=data.get("error"),
        )
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# CLI per test rapido
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Audit gate check")
    parser.add_argument("project", help="Path del progetto da auditare")
    parser.add_argument("--mode", choices=["off", "advisory", "strict"],
                        default=None, help="Modalità gate (default: da config.toml)")
    args = parser.parse_args()
    result = check_audit_gate(args.project, mode=args.mode)
    print(f"Project: {result.project_name}")
    print(f"Gate:    {result.gate} (mode={result.mode})")
    print(f"Totale:  {result.total_findings} (critical={result.critical_count}, warning={result.warning_count})")
    if result.error:
        print(f"Error:   {result.error}")
    print()
    for cat in result.categories:
        icon = "🔒" if cat.blocking else "  "
        print(f"  {icon} {cat.icon} {cat.name:<26s} {cat.status:<6s} "
              f"crit={cat.critical} warn={cat.warning}")
    print()
    print(f"blocks_execution: {result.blocks_execution}")
