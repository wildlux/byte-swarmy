#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonda deterministiche per gli sblocchi M2-M6 (nessun dato inventato).

Legge LO STATO REALE: sensori termici, nbfc, hardening, credenziali e workflow
CI. Non invia richieste di rete, non importa client LLM, non usa GPU.

L'unica scrittura possibile è ``--write-fan``: anche in quel caso la sonda
RIELLEGGE i sensori nell'esecuzione corrente e rifiuta di scrivere se non ci
sono giri ventola reali (> 0 RPM) e temperatura CPU entro 60 °C. Non esiste
un'opzione per passare `fan_rpm`/`temp_c` a mano: scrivere un valore falso
deve essere impossibile per costruzione.

Uso:
    .venv/bin/python tools/blocker_probe.py
    .venv/bin/python tools/blocker_probe.py --out DOCS/BLOCKER_PROBE_REPORT.md
    .venv/bin/python tools/blocker_probe.py --json
    .venv/bin/python tools/blocker_probe.py --check-fan   # gate 0/1
    .venv/bin/python tools/blocker_probe.py --write-fan   # solo se misure OK
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAN_FILE = ROOT / "data" / "state" / "fan_verified.json"
MAX_TEMP_C = 60.0
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
RPM_RE = re.compile(r"(?<![\d.])(\d{2,6})\s*RPM\b", re.IGNORECASE)
SPEED_RE = re.compile(r"Current Fan Speed\s*:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
DUTY_RE = re.compile(r"Target Fan Speed\s*:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
TOKEN_URL_RE = re.compile(r"(https?://)[^/@\s]+@")
GH_BROWSER_MARKER = "Open your Github project in a browser"


def _cmd(argv: list[str], timeout: int = 8) -> str:
    """Esegue un comando di sola lettura; ritorna stdout+stderr, mai eccezioni."""
    try:
        cp = subprocess.run(argv, capture_output=True, text=True,
                            timeout=timeout, check=False)
        return (cp.stdout or "") + (cp.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_nbfc_rpm(text: str) -> int:
    """RPM da `nbfc status`: sia '3200 RPM' sia 'Current Fan Speed: 0.00'.

    nbfc 0.5.3 su questa macchina NON stampa l'unità RPM: ignorare il formato
    vecchio sarebbe un falso '0 RPM' anche quando il valore è positivo.
    """
    vals = [int(v) for v in RPM_RE.findall(text or "")]
    vals += [int(float(v)) for v in SPEED_RE.findall(text or "")]
    return max(vals, default=0)


def parse_nbfc_duty(text: str) -> float | None:
    """Duty cycle richiesto ('Target Fan Speed'), se presente."""
    found = DUTY_RE.findall(text or "")
    return float(found[-1]) if found else None


def parse_hwmon_temp(text: str) -> float:
    """Milli-gradi Celsius dai sysfs hwmon → gradi; 0.0 se non leggibile."""
    try:
        return float((text or "").strip()) / 1000.0
    except (TypeError, ValueError):
        return 0.0


def read_cpu_temp_c(base: Path = Path("/sys")) -> tuple[float, str]:
    """Max per-core di coretemp (fonte VERA; B0D4 satura e non si usa)."""
    vals: list[float] = []
    sources: list[str] = []
    for hwmon in sorted(base.glob("class/hwmon/hwmon*")):
        try:
            name = (hwmon / "name").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if name != "coretemp":
            continue
        for probe in sorted(hwmon.glob("temp*_input")):
            temp = parse_hwmon_temp(probe.read_text(encoding="utf-8"))
            if temp > 0:
                vals.append(temp)
                sources.append(str(probe))
    return (
        max(vals) if vals else 0.0,
        ", ".join(sources) if sources else "nessun sensore coretemp disponibile",
    )


def read_pwm(base: Path = Path("/sys")) -> list[dict]:
    """Stato PWM grezzo dei sysfs disponibili (non è un RPM: solo indizio)."""
    out = []
    for hwmon in sorted(base.glob("class/hwmon/hwmon*")):
        for pwm in sorted(hwmon.glob("pwm[0-9]*")):
            if pwm.name.endswith("_enable"):
                continue
            entry = {"path": str(pwm), "raw": None, "enable": None}
            try:
                entry["raw"] = pwm.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            enable = pwm.with_name(pwm.name + "_enable")
            if enable.exists():
                try:
                    entry["enable"] = enable.read_text(encoding="utf-8").strip()
                except OSError:
                    pass
            out.append(entry)
    return out


def nbfc_probe() -> dict:
    """Stato reale del servizio nbfc (nessun root, nessun pkexec)."""
    state = _cmd(["systemctl", "is-active", "nbfc_service"]).strip().splitlines()
    status = _cmd(["nbfc", "status"], timeout=6)
    detail = ""
    for line in status.splitlines():
        if line.strip():
            detail = ANSI_RE.sub("", line).strip()[:160]
            break
    unit_state = state[-1].strip() if state else "sconosciuto"
    daemon_ok = "Current Fan Speed" in status
    if daemon_ok:
        rpm_source = "nbfc status (Current Fan Speed)" if SPEED_RE.search(status) \
            else "nbfc status (RPM)" if RPM_RE.search(status) else None
    else:
        rpm_source = None
    return {
        "service_state": "daemon attivo" if daemon_ok else unit_state,
        "unit_state": unit_state,
        "daemon_running": daemon_ok,
        "rpm": parse_nbfc_rpm(status),
        "fan_duty_pct": parse_nbfc_duty(status),
        "detail": detail,
        "rpm_source": rpm_source,
    }


def fan_snapshot(base: Path = Path("/sys")) -> dict:
    """Snapshot di sola lettura con verdetto esplicito del gate termico."""
    temp_c, source = read_cpu_temp_c(base)
    nbfc = nbfc_probe()
    rpm = int(nbfc["rpm"])
    temp_ok = 0.0 < temp_c <= MAX_TEMP_C
    rpm_ok = rpm > 0
    return {
        "cpu_temp_c": round(temp_c, 1),
        "temp_source": source,
        "fan_rpm": rpm,
        "fan_duty_pct": nbfc.get("fan_duty_pct"),
        "rpm_source": nbfc["rpm_source"],
        "nbfc_service_state": nbfc["service_state"],
        "nbfc_unit_state": nbfc.get("unit_state"),
        "nbfc_detail": nbfc["detail"],
        "pwm": read_pwm(base),
        "gate": {
            "fan_rpm_positivo": rpm_ok,
            "temp_entro_60c": temp_ok,
            "verified": bool(rpm_ok and temp_ok),
        },
        "misure_inventate": False,
    }


def write_fan_verification(snapshot: dict, out: Path = FAN_FILE) -> Path:
    """Scrive il gate SOLO se lo snapshot contiene misure reali sufficienti."""
    if not snapshot.get("gate", {}).get("verified", False):
        raise ValueError(
            "Rifiutato: servono fan_rpm > 0 e 0 < temp_c <= 60 misurati ora. "
            "Nessun valore viene inventato o accettato da riga di comando.")
    payload = {
        "fan_rpm": int(snapshot["fan_rpm"]),
        "temp_c": float(snapshot["cpu_temp_c"]),
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {
            "temperature": snapshot["temp_source"],
            "fan_rpm": snapshot["rpm_source"],
            "nbfc_service_state": snapshot["nbfc_service_state"],
        },
        "method": "tools/blocker_probe.py --write-fan (lettura sysfs + nbfc)",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    out.chmod(0o600)
    return out


def read_stored_fan(path: Path = FAN_FILE) -> dict:
    """Valida un gate già scritto: valori + provenienza, non solo esistenza."""
    if not path.is_file():
        return {"present": False, "valid": False, "reason": "file assente"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"present": True, "valid": False, "reason": f"JSON non valido: {exc}"}
    checks = {
        "fan_rpm>0": isinstance(data.get("fan_rpm"), (int, float))
        and data["fan_rpm"] > 0,
        "temp_c<=60": isinstance(data.get("temp_c"), (int, float))
        and 0 < data["temp_c"] <= MAX_TEMP_C,
        "provenienza": bool(data.get("sources") and data.get("measured_at")),
    }
    return {
        "present": True,
        "valid": all(checks.values()),
        "checks": checks,
        "fan_rpm": data.get("fan_rpm"),
        "temp_c": data.get("temp_c"),
        "measured_at": data.get("measured_at"),
    }


def hardening_probe(repo: Path = ROOT) -> dict:
    """Diagnostica hardening senza root (non modifica nulla)."""
    script = repo / "scripts" / "setup" / "hardening.sh"
    out = ANSI_RE.sub("", _cmd(["bash", str(script), "--check"], timeout=25))
    user_exists = "NON esiste" not in out
    slice_ok = "slice cgroup assente" not in out
    evidence = [line.strip() for line in out.splitlines()
                if "NON esiste" in line or "assente" in line][:4]
    return {
        "script": "scripts/setup/hardening.sh",
        "user_exists": user_exists,
        "cgroup_slice_present": slice_ok,
        "needs_root": not (user_exists and slice_ok),
        "command": "sudo scripts/setup/hardening.sh --all",
        "evidence": evidence,
    }


def gh_health(exe: str | None = None) -> dict:
    """Distingue la GitHub CLI ufficiale da altri eseguibili chiamati `gh`.

    Su questa macchina `~/.local/bin/gh` è uno script di 3,6 KB che apre il
    progetto nel browser: segnalarlo come 'CLI da riparare' sarebbe un falso
    positivo, perché non supporta `auth` né `workflow`.
    """
    exe = exe or shutil.which("gh")
    if not exe:
        return {
            "ok": False, "path": None, "kind": "assente",
            "reason": "GitHub CLI non installato",
            "install_hint": "sudo apt install gh",
        }
    try:
        with open(exe, "rb") as handle:
            head = handle.read(4096).decode("utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "path": exe, "kind": "illeggibile",
                "reason": f"gh non leggibile: {exc}", "install_hint": None}
    if GH_BROWSER_MARKER in head:
        return {
            "ok": False, "path": exe, "kind": "script-browser",
            "reason": "`gh` trovato ma NON è GitHub CLI: apre solo il browser",
            "install_hint": "sudo apt install gh",
        }
    first = head.splitlines()[0] if head.splitlines() else ""
    if first.startswith("#!"):
        interpreter = first[2:].strip().split()
        if interpreter and not Path(interpreter[0]).exists():
            return {
                "ok": False, "path": exe, "kind": "shebang-rotto",
                "reason": f"interprete shebang assente: {interpreter[0]}",
                "install_hint": "sudo apt install gh",
            }
    version = _cmd([exe, "--version"], timeout=6)
    if not re.search(r"gh version\s+\d", version, re.IGNORECASE):
        return {
            "ok": False, "path": exe, "kind": "sconosciuto",
            "reason": "eseguibile gh non riconosciuto come GitHub CLI",
            "install_hint": "sudo apt install gh",
        }
    return {"ok": True, "path": exe, "kind": "ufficiale",
            "reason": None, "install_hint": None,
            "version": version.strip().splitlines()[0][:60]}


def mask_remote(url: str) -> str:
    """Nasconde un eventuale token in URL https con userinfo."""
    return TOKEN_URL_RE.sub(r"\1***@", url or "")


def remote_token_free(url: str) -> bool:
    return not TOKEN_URL_RE.search(url or "")


def file_mode(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "mode": None, "ok_600": False}
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return {"exists": True, "mode": None, "ok_600": False}
    return {"exists": True, "mode": f"{mode:04o}", "ok_600": mode == 0o600}


def credentials_probe(repo: Path = ROOT) -> dict:
    """Stato credenziali: nessun segreto viene letto o stampato."""
    health = gh_health()
    auth_ok = False
    auth_hint = "GitHub CLI assente: installarla prima di autenticarsi"
    if health["ok"]:
        out = _cmd([health["path"], "auth", "status", "--hostname", "github.com"])
        auth_ok = "logged in" in out.lower()
        auth_hint = "gh autenticato" if auth_ok else "servono gh auth login e una PAT nuova"
    url = _cmd(["git", "-C", str(repo), "remote", "get-url", "origin"]).strip()
    return {
        "gh": health,
        "gh_auth_ok": auth_ok,
        "auth_hint": auth_hint,
        "remote_url": mask_remote(url),
        "remote_token_free": remote_token_free(url),
        "cloud_api_json": file_mode(repo / "state" / "cloud_api.json"),
        "git_credentials": file_mode(Path.home() / ".git-credentials"),
        "rotation_confirmed": False,
        "rotation_note": "La revoca della PAT va verificata su GitHub, non deducibile dal FS",
    }


def ci_probe(repo: Path = ROOT, health: dict | None = None) -> dict:
    """Workflow di profiling: trigger manuale, senza chiamate API."""
    health = health if health is not None else gh_health()
    workflow = repo / ".github" / "workflows" / "profile.yml"
    return {
        "workflow": ".github/workflows/profile.yml",
        "present": workflow.is_file(),
        "failed_step": "Profilazione completa (--durations=0) — run #2",
        "trigger_available_locally": bool(health["ok"]),
        "command": "gh workflow run profile.yml -R wildlux/byte-swarmy",
        "blocker": health["reason"] if not health["ok"] else
                   "richiede autenticazione gh + trigger manuale UI/CLI",
    }


def collect(base: Path = Path("/sys"), repo: Path = ROOT) -> dict:
    """Raccoglie tutte le sonde in un unico risultato serializzabile."""
    creds = credentials_probe(repo)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fan": fan_snapshot(base),
        "fan_stored": read_stored_fan(repo / "data" / "state" / "fan_verified.json"),
        "hardening": hardening_probe(repo),
        "credentials": creds,
        "ci": ci_probe(repo, creds["gh"]),
        "suite": {
            "last_green": "888 passed, 1 xfailed, 0 warnings (2026-11-19)",
            "local_full_run": "VIETATA dalla regola termica 2026-11-20",
            "remote_command": "pytest --ignore=project -q -p no:cacheprovider --durations=0",
        },
    }


def _yes_no(value: bool) -> str:
    return "✅" if value else "❌"


def markdown(result: dict) -> str:
    """Report deterministico: verdetto + evidenza + azione esatta."""
    fan = result["fan"]
    gate = fan["gate"]
    hard = result["hardening"]
    creds = result["credentials"]
    ci = result["ci"]
    stored = result["fan_stored"]
    suite = result["suite"]
    lines = [
        "# 🔍 Sonde di sblocco — M2…M6",
        "",
        f"Generato (UTC): `{result.get('generated_at', '—')}`",
        "",
        "> Solo dati letti ora da file/sysfs/comandi locali. Nessun valore",
        "> inventato, nessuna chiamata API, nessun LLM. I blocchi restano aperti",
        "> finché l'azione esterna non è stata eseguita e riverificata.",
        "",
        "| ID | Stato | Evidenza | Azione richiesta |",
        "|---|---|---|---|",
        f"| M2 suite completa | 🔒 | {suite['local_full_run']} | "
        f"trigger CI: `{ci['command']}` |",
        f"| M3 ventole | {'✅' if gate['verified'] else '🔒'} | "
        f"CPU {fan['cpu_temp_c']} °C, RPM {fan['fan_rpm']}, "
        f"nbfc `{fan['nbfc_service_state']}` | "
        f"misurare RPM con strumento esterno (nbfc già attivo non basta), "
        f"poi `tools/blocker_probe.py --write-fan` |",
        f"| M4 credenziali | {'✅' if creds['gh_auth_ok'] else '🔒'} | "
        f"gh: {creds['gh']['reason'] or 'ok'}; remote token-free: "
        f"{_yes_no(creds['remote_token_free'])} | "
        "installare la CLI (`sudo apt install gh`), `gh auth login`, revocare la PAT |",
        f"| M5 hardening | {'✅' if not hard['needs_root'] else '🔒'} | "
        f"utente {_yes_no(hard['user_exists'])}, slice {_yes_no(hard['cgroup_slice_present'])} | "
        f"`{hard['command']}` |",
        f"| M6 profiling CI | 🔒 | run #2 fallito: {ci['failed_step']} | "
        f"{ci['blocker']}; poi `{ci['command']}` |",
        "",
        "## Dettaglio termico (M3)",
        "",
        "| Misura | Valore |",
        "|---|---|",
        f"| Temperatura CPU (coretemp) | {fan['cpu_temp_c']} °C |",
        f"| Sorgente temperatura | `{fan['temp_source']}` |",
        f"| RPM ventola | {fan['fan_rpm']} ({fan['rpm_source'] or 'nessuna sorgente'}) |",
        f"| Duty richiesto | {fan.get('fan_duty_pct')} % (Target Fan Speed) |",
        f"| Unità systemd | `{fan.get('nbfc_unit_state')}` |",
        f"| Dettaglio nbfc | {fan['nbfc_detail'] or 'nessuna risposta'} |",
        f"| PWM sysfs | {len(fan['pwm'])} nodi (indizio, non RPM) |",
        f"| `fan_rpm > 0` | {_yes_no(gate['fan_rpm_positivo'])} |",
        f"| `temp_c <= 60` | {_yes_no(gate['temp_entro_60c'])} |",
        f"| Gate verificabile | {_yes_no(gate['verified'])} |",
        f"| `fan_verified.json` salvato | {_yes_no(stored['valid'])} |",
        "",
        "Il file di gate non viene mai scritto con valori passati a mano:",
        "`--write-fan` rilegge i sensori e rifiuta se il gate non è verificato.",
        "",
        "Su questa macchina il daemon nbfc è stato avviato via pkexec, ma",
        "`Current Fan Speed` resta 0.00 anche con duty al 100% e non esiste",
        "alcun `fan*_input` in sysfs: il tachimetro non è leggibile. Pertanto",
        "`fan_rpm > 0` NON è dimostrabile con i sensori disponibili: il gate",
        "resta chiuso **per decisione esplicita del 2026-11-22** (gate stretto",
        "mantenuto): nessun duty cycle o altra misura sostituisce i RPM.",
        "",
        "## Dettaglio credenziali (M4)",
        "",
        "| Controllo | Valore |",
        "|---|---|",
        f"| Eseguibile gh | `{creds['gh']['path'] or 'assente'}` — "
        f"{creds['gh']['reason'] or 'ok'} |",
        f"| GitHub CLI ufficiale | {_yes_no(creds['gh']['ok'])} "
        f"({creds['gh']['kind']}) |",
        f"| Installazione suggerita | `{creds['gh'].get('install_hint') or '—'}` |",
        f"| Autenticazione gh | {_yes_no(creds['gh_auth_ok'])} |",
        f"| Remote origin | `{creds['remote_url']}` |",
        f"| Token nel remote | {_yes_no(not creds['remote_token_free'])} |",
        f"| `state/cloud_api.json` 0600 | {_yes_no(creds['cloud_api_json']['ok_600'])} |",
        f"| `~/.git-credentials` 0600 | {_yes_no(creds['git_credentials']['ok_600'])} |",
        f"| Rotazione PAT confermata | {_yes_no(creds['rotation_confirmed'])} — "
        f"{creds['rotation_note']} |",
        "",
        "## Regole di onestà",
        "",
        "- Nessun asse del radar viene alzato da questa sonda.",
        "- Nessuna suite completa locale viene lanciata per aggirare il gate termico.",
        "- M2 resta non misurato finché il workflow CI non produce un artifact.",
        "- Il 0600 dei file locali NON dimostra che un token esposto sia stato revocato.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sonde deterministiche di sblocco")
    parser.add_argument("--json", action="store_true", help="output JSON")
    parser.add_argument("--out", type=Path, help="scrive il report Markdown")
    parser.add_argument("--check-fan", action="store_true",
                        help="exit 0 solo se il gate salvato è valido")
    parser.add_argument("--write-fan", action="store_true",
                        help="scrive il gate SOLO da misure live verifiche")
    args = parser.parse_args(argv)

    if args.check_fan:
        valid = read_stored_fan()["valid"]
        print("fan_verified.json: VALIDO" if valid else "fan_verified.json: NON VALIDO")
        return 0 if valid else 1

    if args.write_fan:
        snap = fan_snapshot()  # rilettura live, nessun valore accettato a mano
        try:
            path = write_fan_verification(snap)
        except ValueError as exc:
            print(f"RIFIUTO: {exc}")
            return 1
        print(f"Gate scritto: {path} (RPM {snap['fan_rpm']}, "
              f"{snap['cpu_temp_c']} °C)")

    result = collect()
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n" if args.json \
        else markdown(result)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Report scritto: {args.out}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
