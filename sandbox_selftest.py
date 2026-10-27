#!/usr/bin/env python3
"""
sandbox_selftest.py — verifica dall'interno che il sandbox sia realmente attivo.

Eseguito da `sandbox.run_selftest()` dentro bubblewrap. Non modifica l'host:
scrive solo un file temporaneo in `/workspace` (il progetto montato) e lo
rimuove. Stampa un oggetto JSON con l'esito dei singoli controlli.
"""

from __future__ import annotations

import ctypes
import json
import os
import socket
import sys
from pathlib import Path

CHECKS: list[dict] = []


class SkipCheck(Exception):
    """Controllo non applicabile a questa versione di bubblewrap."""


def check(name: str, fn) -> None:
    try:
        detail = fn()
        CHECKS.append({"name": name, "status": "PASS", "detail": str(detail)[:300]})
    except SkipCheck as exc:
        CHECKS.append({"name": name, "status": "SKIP", "detail": str(exc)[:300]})
    except Exception as exc:
        CHECKS.append({
            "name": name,
            "status": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}"[:300],
        })


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_workspace() -> str:
    cwd = Path.cwd()
    expect(cwd == Path("/workspace"), f"cwd inattesa: {cwd}")
    expect(Path("sandbox_selftest.py").exists() is False, "helper copiato nel progetto")
    return str(cwd)


def check_project_write() -> str:
    target = Path("/workspace/.sandbox-selftest.tmp")
    target.write_text("sandbox-ok", encoding="utf-8")
    try:
        expect(target.read_text(encoding="utf-8") == "sandbox-ok", "contenuto errato")
    finally:
        target.unlink(missing_ok=True)
    return "scrittura/lettura in /workspace OK"


def check_host_home_hidden() -> str:
    host_home = os.environ.get("SANDBOX_HOST_HOME", "")
    expect(host_home != "", "SANDBOX_HOST_HOME assente")
    expect(not Path(host_home).exists(), f"home host visibile: {host_home}")
    expect(not Path(host_home, ".ssh", "id_rsa").exists(), "chiave SSH visibile")
    home_entries = sorted(p.name for p in Path("/home").iterdir())
    expect(home_entries == ["sandbox"], f"/home inattesa: {home_entries}")
    return f"home host {host_home} invisibile"


def check_outside_write_blocked() -> str:
    for path in ("/etc/.sandbox-escape", "/opt/.sandbox-escape", "/usr/.sandbox-escape"):
        try:
            Path(path).write_text("escape", encoding="utf-8")
        except OSError:
            continue
        raise AssertionError(f"scrittura riuscita fuori dal progetto: {path}")
    return "scrittura su /etc, /opt e /usr bloccata"


def check_network_blocked() -> str:
    targets = [("1.1.1.1", 80), ("8.8.8.8", 53), ("127.0.0.1", 11434)]
    for host, port in targets:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        try:
            rc = sock.connect_ex((host, port))
        finally:
            sock.close()
        expect(rc != 0, f"connessione riuscita verso {host}:{port}")
    return "nessuna connessione verso Internet o Ollama host"


def check_host_pid_hidden() -> str:
    host_pid = os.environ.get("SANDBOX_HOST_PID", "")
    expect(host_pid.isdigit(), "SANDBOX_HOST_PID non valido")
    expect(not Path(f"/proc/{host_pid}").exists(),
           f"PID host {host_pid} visibile nel sandbox")
    return f"PID host {host_pid} invisibile"


def check_sensitive_env_absent() -> str:
    forbidden = (
        "GITHUB_TOKEN", "GH_TOKEN", "GIT_TOKEN", "SSH_AUTH_SOCK",
        "SSH_AGENT_PID", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL",
    )
    found = [key for key in forbidden if key in os.environ]
    expect(not found, f"variabili sensibili presenti: {found}")
    expect(os.environ.get("HOME") == "/home/sandbox",
           f"HOME inattesa: {os.environ.get('HOME')}")
    return "ambiente senza token/socket SSH"


def check_capabilities_dropped() -> str:
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    values = {}
    for line in status.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    expect(values.get("CapEff") == "0000000000000000",
           f"CapEff non azzerate: {values.get('CapEff')}")
    expect(values.get("CapBnd") == "0000000000000000",
           f"CapBnd non azzerate: {values.get('CapBnd')}")
    expect(values.get("NoNewPrivs") == "1", "no_new_privs non attivo")
    return "capability azzerate e no_new_privs attivo"


def check_nested_userns_blocked() -> str:
    if os.environ.get("SANDBOX_DISABLE_USERNS") != "1":
        raise SkipCheck(
            "bubblewrap < 0.11: --disable-userns non disponibile"
        )
    libc = ctypes.CDLL(None, use_errno=True)
    clone_newuser = 0x10000000
    result = libc.unshare(clone_newuser)
    errno = ctypes.get_errno()
    expect(result != 0, "creazione di un nuovo user namespace riuscita")
    return f"unshare(CLONE_NEWUSER) bloccato (errno={errno})"


def check_process_isolation() -> str:
    pids = [p.name for p in Path("/proc").iterdir() if p.name.isdigit()]
    expect(len(pids) < 32, f"troppi PID visibili: {len(pids)}")
    expect("1" in pids, "manca PID 1 del namespace")
    return f"{len(pids)} PID visibili nel namespace"


def main() -> int:
    check("sandbox.workspace", check_workspace)
    check("sandbox.project_write", check_project_write)
    check("sandbox.host_home_hidden", check_host_home_hidden)
    check("sandbox.outside_write_blocked", check_outside_write_blocked)
    check("sandbox.network_blocked", check_network_blocked)
    check("sandbox.host_pid_hidden", check_host_pid_hidden)
    check("sandbox.sensitive_env_absent", check_sensitive_env_absent)
    check("sandbox.capabilities_dropped", check_capabilities_dropped)
    check("sandbox.nested_userns_blocked", check_nested_userns_blocked)
    check("sandbox.process_isolation", check_process_isolation)

    ok = all(item["status"] in ("PASS", "SKIP") for item in CHECKS)
    payload = {
        "ok": ok,
        "available": True,
        "backend": "bubblewrap",
        "hardened": os.environ.get("SANDBOX_DISABLE_USERNS") == "1",
        "python": sys.version.split()[0],
        "checks": CHECKS,
    }
    if "--json" in sys.argv:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for item in CHECKS:
            print(f"[{item['status']}] {item['name']}: {item['detail']}")
        print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
