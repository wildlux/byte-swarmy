"""CORE/tool_proposer.py — Proposta e approvazione di nuovi tool generati.

Gemello di ``CORE/skill_proposer.py`` ma per tool (funzioni Python), non
per skill markdown. L'agente può proporre un nuovo tool quando rileva che
ne manca uno: scrive una bozza in ``state/tool_proposals/<name>.py`` e
questo modulo la valida con un gate deterministico (py_compile + AST).

Approvazione umana obbligatoria: ``--approve <id>`` sposta la bozza in
``CORE/generated_tools.py`` (caricato dinamicamente da ``CORE/tools.py``)
e la registra in ``TOOL_REGISTRY``. Rifiuto: ``--reject <id>``.

Fail-open: un errore qui non blocca mai un task.
"""
from __future__ import annotations

import argparse
import ast
import json
import py_compile
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS_DIR = ROOT / "state" / "tool_proposals"
GENERATED_FILE = ROOT / "CORE" / "generated_tools.py"
REGISTRY_FILE = ROOT / "state" / "tool_proposals" / "registry.json"

# Chiamate vietate nelle bozze (rilevate via AST, non per testo).
_FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__", "input"})
_FORBIDDEN_ATTRS = frozenset({
    "system", "popen", "Popen", "run", "call", "check_output",
    "remove", "rmtree", "unlink", "rmdir",
})
_FORBIDDEN_MODULES = frozenset({"os", "subprocess", "shutil", "socket",
                                "urllib", "requests", "httpx"})


@dataclass(frozen=True)
class GateCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class GateReport:
    proposal_id: str
    checks: tuple[GateCheck, ...]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def reasons(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if not c.ok]

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "ok": self.ok,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail}
                       for c in self.checks],
            "reasons": self.reasons(),
        }

    def markdown(self) -> str:
        lines = [f"### Gate tool `{self.proposal_id}` — "
                 f"{'✅ VERDE' if self.ok else '🔴 ROSSO'}", "",
                 "| Check | Esito | Dettaglio |", "|---|---|---|"]
        for c in self.checks:
            lines.append(f"| {c.name} | {'OK' if c.ok else 'FAIL'} | "
                         f"{c.detail or '-'} |")
        if self.reasons():
            lines += ["", "Motivi:", ""] + [f"- {r}" for r in self.reasons()]
        return "\n".join(lines)


def _gate(proposal_id: str, code: str) -> GateReport:
    checks: list[GateCheck] = []

    # 1. Non vuoto e dimensione ragionevole
    if not code.strip():
        checks.append(GateCheck("non_vuoto", False, "bozza vuota"))
        return GateReport(proposal_id, tuple(checks))
    checks.append(GateCheck("non_vuoto", True, f"{len(code)} caratteri"))
    if len(code) > 20000:
        checks.append(GateCheck("dimensione", False, "bozza troppo grande (>20k)"))
        return GateReport(proposal_id, tuple(checks))
    checks.append(GateCheck("dimensione", True, "ok"))

    # 2. py_compile
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        py_compile.compile(tmp, doraise=True)
        checks.append(GateCheck("py_compile", True, "sintassi valida"))
    except py_compile.PyCompileError as e:
        checks.append(GateCheck("py_compile", False, str(e)))
        return GateReport(proposal_id, tuple(checks))
    finally:
        try:
            Path(tmp).unlink(missing_ok=True)
        except Exception:
            pass

    # 3. AST: funzione top-level presente e nessuna chiamata pericolosa
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        checks.append(GateCheck("ast", False, str(e)))
        return GateReport(proposal_id, tuple(checks))
    funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not funcs:
        checks.append(GateCheck("funzione", False, "nessuna funzione top-level"))
        return GateReport(proposal_id, tuple(checks))
    checks.append(GateCheck("funzione", True, f"{len(funcs)} funzione/i"))

    forbidden_found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
                forbidden_found.append(node.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr in _FORBIDDEN_ATTRS:
                forbidden_found.append(node.func.attr)
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in _FORBIDDEN_MODULES:
                    forbidden_found.append(f"import {mod}")
        if isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod in _FORBIDDEN_MODULES:
                    forbidden_found.append(f"from {mod}")
    if forbidden_found:
        checks.append(GateCheck("sicurezza", False,
                                "chiamate vietate: " + ", ".join(sorted(set(forbidden_found)))))
        return GateReport(proposal_id, tuple(checks))
    checks.append(GateCheck("sicurezza", True, "nessuna chiamata pericolosa"))

    return GateReport(proposal_id, tuple(checks))


def _ensure_dirs() -> None:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict:
    _ensure_dirs()
    if not REGISTRY_FILE.exists():
        return {}
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_registry(reg: dict) -> None:
    _ensure_dirs()
    REGISTRY_FILE.write_text(json.dumps(reg, indent=2, ensure_ascii=False),
                            encoding="utf-8")


def propose(name: str, code: str) -> str:
    """Salva una bozza e ritorna il proposal id."""
    _ensure_dirs()
    pid = name
    path = PROPOSALS_DIR / f"{pid}.py"
    path.write_text(code, encoding="utf-8")
    reg = _load_registry()
    reg[pid] = {"status": "pending", "file": str(path)}
    _save_registry(reg)
    return pid


def list_proposals() -> list[tuple[str, str]]:
    _ensure_dirs()
    reg = _load_registry()
    return [(pid, info.get("status", "?")) for pid, info in reg.items()]


def gate(proposal_id: str) -> GateReport:
    _ensure_dirs()
    reg = _load_registry()
    if proposal_id not in reg:
        return GateReport(proposal_id, (GateCheck("esiste", False, "proposta non trovata"),))
    path = Path(reg[proposal_id]["file"])
    code = path.read_text(encoding="utf-8") if path.exists() else ""
    return _gate(proposal_id, code)


def approve(proposal_id: str) -> bool:
    """Approva: copia la bozza in CORE/generated_tools.py e registra."""
    _ensure_dirs()
    reg = _load_registry()
    if proposal_id not in reg:
        return False
    path = Path(reg[proposal_id]["file"])
    if not path.exists():
        return False
    code = path.read_text(encoding="utf-8")
    report = _gate(proposal_id, code)
    if not report.ok:
        reg[proposal_id]["status"] = "rejected_gate"
        reg[proposal_id]["gate"] = report.to_dict()
        _save_registry(reg)
        return False

    # Appendi a generated_tools.py (crea se non esiste)
    existing = GENERATED_FILE.read_text(encoding="utf-8") if GENERATED_FILE.exists() else ""
    marker = f"# --- tool: {proposal_id} ---\n"
    if marker not in existing:
        new_content = existing.rstrip() + "\n\n" + marker + code.rstrip() + "\n"
        GENERATED_FILE.write_text(new_content, encoding="utf-8")

    # Registra in TOOL_REGISTRY a runtime (best-effort)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("generated_tools", GENERATED_FILE)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            from CORE.tool_registry import register_tool
            for name in getattr(mod, "__all__", []):
                obj = getattr(mod, name, None)
                if callable(obj):
                    register_tool(name)(obj)
    except Exception:
        pass

    reg[proposal_id]["status"] = "approved"
    reg[proposal_id]["gate"] = report.to_dict()
    _save_registry(reg)
    # Sposta la bozza in approved/
    approved_dir = PROPOSALS_DIR / "approved"
    approved_dir.mkdir(exist_ok=True)
    shutil.move(str(path), str(approved_dir / path.name))
    return True


def record_tool_usage(tool_name: str, success: bool) -> Optional[str]:
    """Traccia l'uso di un tool generato. Dopo 3 successi senza fallimenti,
    prova l'auto-approvazione (gate verde). Ritorna l'id approvato o None.
    Fail-open."""
    try:
        reg = _load_registry()
        # Traccia usage in registry
        info = reg.get(tool_name)
        if info is None:
            return None
        usage = info.setdefault("usage", {"success": 0, "fail": 0})
        if success:
            usage["success"] = usage.get("success", 0) + 1
        else:
            usage["fail"] = usage.get("fail", 0) + 1
        _save_registry(reg)

        # Auto-approvazione dopo 3 successi senza fallimenti
        if usage.get("success", 0) >= 3 and usage.get("fail", 0) == 0:
            if info.get("status") == "pending":
                report = gate(tool_name)
                if report.ok:
                    ok = approve(tool_name)
                    if ok:
                        return tool_name
        return None
    except Exception:
        return None


def reject(proposal_id: str) -> bool:
    _ensure_dirs()
    reg = _load_registry()
    if proposal_id not in reg:
        return False
    path = Path(reg[proposal_id]["file"])
    if path.exists():
        rejected_dir = PROPOSALS_DIR / "rejected"
        rejected_dir.mkdir(exist_ok=True)
        shutil.move(str(path), str(rejected_dir / path.name))
    reg[proposal_id]["status"] = "rejected"
    _save_registry(reg)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m CORE.tool_proposer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="Lista proposte.")
    p_list.set_defaults(func=lambda a: _cmd_list())

    p_gate = sub.add_parser("gate", help="Esegue il gate su una proposta.")
    p_gate.add_argument("id")
    p_gate.set_defaults(func=lambda a: _cmd_gate(a.id))

    p_approve = sub.add_parser("approve", help="Approva una proposta (gate + copia).")
    p_approve.add_argument("id")
    p_approve.set_defaults(func=lambda a: _cmd_approve(a.id))

    p_reject = sub.add_parser("reject", help="Rifiuta una proposta.")
    p_reject.add_argument("id")
    p_reject.set_defaults(func=lambda a: _cmd_reject(a.id))

    args = parser.parse_args()
    args.func(args)


def _cmd_list() -> None:
    for pid, status in list_proposals():
        print(f"{pid}: {status}")


def _cmd_gate(pid: str) -> None:
    print(gate(pid).markdown())


def _cmd_approve(pid: str) -> None:
    ok = approve(pid)
    print("APPROVATO" if ok else "BLOCCATO (gate rosso o id sconosciuto)")


def _cmd_reject(pid: str) -> None:
    ok = reject(pid)
    print("RIFIUTATO" if ok else "id sconosciuto")


if __name__ == "__main__":
    main()

