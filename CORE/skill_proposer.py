"""
CORE/skill_proposer.py — M8: memoria dei fallimenti → skill suggerite.

Idea: il correction loop sa *cosa* è andato male (prosa senza fence,
placeholder copiato, try senza except, input() interattivo, marker
mancante, classe senza istanza, NameError…). Se una stessa "firma" di
fallimento si ripete N volte, il sistema genera una BOZZA di skill
basata sul skill più vicino e la mette in `state/skill_proposals/`
per approvazione umana — la libreria cresce sui TUOI errori ricorrenti.

Storage:
  - state/skill_proposals/failures.json  → contatori per firma
  - state/skill_proposals/<sig>_<n>.md   → bozze in attesa
Approvazione: `python -m CORE.skill_proposer --approve <id>` sposta
la bozza in `SKILLS/<name>.md` (dove il matcher la carica). Rifiuto:
`--reject <id>` la cancella. `--gate <id>` stampa il report gate.
Fail-open ovunque: un errore qui non blocca mai un task.

Soglia: 3 occorrenze (stessa del correction loop).

B2 (2026-11-22): l'auto-approvazione dopo 3 successi NON è più cieca.
Prima di scrivere in SKILLS/ il candidato passa un gate deterministico
(sezioni, regola non vuota, fence Python compilabile, nessuna chiamata
pericolosa). Gate rosso = bozza intatta + report in `failures.json`;
gate verde = approvazione con backup `.backup.md` e report salvato.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "SKILLS"
PROPOSALS_DIR = ROOT / "state" / "skill_proposals"
FAILURES_FILE = PROPOSALS_DIR / "failures.json"
THRESHOLD = 3

# B2 (2026-11-22): gate deterministico per l'auto-approvazione.
MAX_PROPOSAL_CHARS = 20000
REQUIRED_SECTIONS = ("# REGOLA APPRESA", "## Regola", "## Template concreto")
MIN_RULE_CHARS = 40
# Chiamate vietate nei template delle bozze (rilevate via AST, non per testo:
# un commento che dice "MAI usare input()" non deve bloccare la bozza).
_FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__", "input"})
_FORBIDDEN_ATTRS = frozenset({
    "system", "popen", "Popen", "run", "call", "check_output",
})


@dataclass(frozen=True)
class GateCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class GateReport:
    """Report del gate sul candidato: mai una valutazione LLM."""
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
        lines = [f"### Gate skill `{self.proposal_id}` — "
                 f"{'✅ VERDE' if self.ok else '🔴 ROSSO'}", "",
                 "| Check | Esito | Dettaglio |", "|---|---|---|"]
        for c in self.checks:
            lines.append(f"| {c.name} | {'OK' if c.ok else 'FAIL'} | "
                         f"{c.detail or '-'} |")
        if self.reasons():
            lines += ["", "Motivi:", ""]
            lines += [f"- {r}" for r in self.reasons()]
        return "\n".join(lines)


# Firma → (etichetta, skill base da cui partire, regola appresa)
SIGNATURES: dict[str, dict] = {
    "prosa_senza_fence": {
        "label": "Prosa prima del codice (niente fence ```python)",
        "base": "py-cli-script.md",
        "rule": ("Il modello apre con testo libero ('Okay, let's tackle…') "
                 "senza il fence ```python in prima riga. La risposta DEVE "
                 "iniziare direttamente con ```python e contenere solo codice."),
    },
    "placeholder_copiato": {
        "label": "Placeholder {{...}} copiato letteralmente",
        "base": "py-text-analyze.md",
        "rule": ("Un segnaposto {{...}} è rimasto nel codice → errore di "
                 "sintassi. Sostituire TUTTI i placeholder con codice reale; "
                 "i commenti `# HINT` sono solo suggerimenti, vanno attivati "
                 "se il task lo richiede."),
    },
    "try_senza_except": {
        "label": "try: senza except/finally",
        "base": "py-class-module.md",
        "rule": ("Ogni `try:` aperto DEVE avere il suo `except` (o "
                 "`finally`). Mai cancellare un blocco except. Per eccezioni "
                 "personalizzate: `class NomeError(Exception)`."),
    },
    "input_interattivo": {
        "label": "Uso di input()/stdin (script non interattivo)",
        "base": "py-cli-script.md",
        "rule": ("Lo script gira non-interattivamente (stdin vuoto). MAI "
                 "usare input(): hard-codificare i valori d'esempio del "
                 "task e stampare il risultato."),
    },
    "marker_mancante": {
        "label": "Marker atteso non stampato (LEN=, SOMMA=, …)",
        "base": "py-class-module.md",
        "rule": ("Stampare TUTTI i marker che il task richiede, con il "
                 "valore LETTERALE scritto nel task (ok, True, 42…), mai il "
                 "messaggio dell'eccezione. Leggere il task riga per riga."),
    },
    "classe_senza_istanza": {
        "label": "Metodo chiamato sulla classe invece che su un'istanza",
        "base": "py-class-module.md",
        "rule": ("Se il PROJECT MAP mostra una classe, usare un'ISTANZA: "
                 "`obj = Class(); obj.method()`. Mai `Class.method()`."),
    },
    "nome_inedito": {
        "label": "NameError: nome usato ma mai definito/importato",
        "base": "py-cli-script.md",
        "rule": ("Ogni nome usato deve essere definito o importato. "
                 "Riutilizzare i simboli del PROJECT MAP invece di "
                 "allucinare API."),
    },
    "loop_infinito": {
        "label": "Loop infinito (iteratore ricreato nel while)",
        "base": "py-class-module.md",
        "rule": ("Drain: creare l'iteratore UNA SOLA VOLTA fuori dal "
                 "loop (`it = iter(coll)`), poi `next(it)` dentro; "
                 "`next(iter(x))` nel loop crea un iteratore fresco a "
                 "ogni giro → mai StopIteration. Il drain più sicuro è "
                 "`for item in coll: print(item)`."),
    },
    "generico": {
        "label": "Fallimento generico (nessuna firma riconosciuta)",
        "base": "py-cli-script.md",
        "rule": ("Verificare che il codice compili, giri e stampi i "
                 "marker attesi prima di dichiarare ok."),
    },
}


def classify_failure(error: str, code: str = "") -> str:
    """Classifica un errore di run_direct in una firma riconosciuta."""
    e = (error or "").lower()
    c = (code or "").lower()
    if "eoferror" in e or "input(" in c:
        return "input_interattivo"
    if "placeholder" in e or "{{" in c:
        return "placeholder_copiato"
    if "expected 'except' or 'finally'" in e or "expected \"except\"" in e:
        return "try_senza_except"
    if "output atteso mancante" in e:
        return "marker_mancante"
    if "no attribute" in e or "function' object" in e or "has no attribute" in e:
        return "classe_senza_istanza"
    if "nameerror" in e or "name '" in e:
        return "nome_inedito"
    if "timeout" in e and ("loop" in e or "input" in e):
        return "loop_infinito"
    if "pycompileerror" in e and "the output should" in e:
        return "prosa_senza_fence"
    if "pycompileerror" in e or "syntaxerror" in e:
        return "prosa_senza_fence" if "okay" in c or "let's" in c else "generico"
    return "generico"


def _load_failures() -> dict:
    try:
        if FAILURES_FILE.exists():
            return json.loads(FAILURES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"counts": {}, "last_seen": {}, "proposals": {}}


def _save_failures(data: dict) -> None:
    try:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        FAILURES_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


def _fence_errors(text: str) -> list[str]:
    """Valida i blocchi ```python del candidato (sintassi + chiamate vietate)."""
    errors: list[str] = []
    fences = re.findall(r"```python[ \t]*\n(.*?)```", text,
                        flags=re.DOTALL | re.IGNORECASE)
    if not fences:
        return ["nessun blocco python concreto"]
    for idx, code in enumerate(fences, 1):
        # I segnaposto {{ ... }} sono template, non codice: sostituirli
        # con None rende il blocco analizzabile senza cambiare la semantica.
        src = re.sub(r"\{\{[^}]*\}\}", "None", code)
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            errors.append(f"blocco {idx}: sintassi non valida "
                          f"({e.msg}, riga {e.lineno})")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _FORBIDDEN_CALLS:
                errors.append(f"blocco {idx}: chiamata vietata {fn.id}()")
            if isinstance(fn, ast.Attribute) and fn.attr in _FORBIDDEN_ATTRS:
                errors.append(f"blocco {idx}: chiamata vietata .{fn.attr}()")
    return errors


def gate_proposal(proposal_path: str, signature: str = "",
                  proposal_id: str = "") -> GateReport:
    """B2: gate deterministico sul candidato — zero LLM, zero rete.

    Controlli: file presente, dimensione, sezioni obbligatorie, regola non
    vuota, fence Python compilabile e senza chiamate pericolose. Il report
    è sempre restituito (fail-open: un errore diventa gate rosso, non un
    dump di eccezioni).
    """
    prop_id = proposal_id or Path(proposal_path).stem
    checks: list[GateCheck] = []
    path = Path(proposal_path)

    if not path.is_file():
        return GateReport(prop_id, (GateCheck("file", False, "mancante"),))

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return GateReport(prop_id, (GateCheck("file", False, str(e)[:120]),))

    checks.append(GateCheck(
        "dimensione", 0 < len(text) <= MAX_PROPOSAL_CHARS,
        f"{len(text)} caratteri (max {MAX_PROPOSAL_CHARS})"))

    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    checks.append(GateCheck("sezioni", not missing,
                            "mancano: " + ", ".join(missing) if missing else
                            "tutte presenti"))

    rule = ""
    if "## Regola" in text:
        tail = text.split("## Regola", 1)[1]
        rule = tail.split("## Template concreto", 1)[0].strip()
    checks.append(GateCheck("regola", len(rule) >= MIN_RULE_CHARS,
                            f"{len(rule)} caratteri (min {MIN_RULE_CHARS})"))

    errors = _fence_errors(text)
    checks.append(GateCheck("template_python", not errors,
                            "; ".join(errors[:3]) if errors else "valido"))

    return GateReport(prop_id, tuple(checks))


def _record_gate_report(prop_id: str, report: GateReport) -> None:
    """Persiste l'ultimo report gate (anche se rosso) per la review."""
    try:
        data = _load_failures()
        data.setdefault("gate_reports", {})[prop_id] = {
            **report.to_dict(), "at": time.time()}
        _save_failures(data)
    except Exception:
        pass


def gate_report(prop_id: str) -> Optional[GateReport]:
    """Report gate salvato per una proposta (None se mai valutata)."""
    try:
        raw = _load_failures().get("gate_reports", {}).get(prop_id)
        if not raw:
            return None
        return GateReport(
            raw["proposal_id"],
            tuple(GateCheck(c["name"], c["ok"], c.get("detail", ""))
                  for c in raw["checks"]))
    except Exception:
        return None


def record_failure(signature: str, task_title: str = "",
                   error: str = "") -> Optional[str]:
    """Registra un fallimento. Se la firma raggiunge THRESHOLD e non c'è
    già una bozza pendente, crea la bozza e ne restituisce l'id.

    Ritorna l'id della bozza creata (o None se nessuna creata).
    Fail-open: mai solleva.
    """
    try:
        if signature not in SIGNATURES:
            signature = "generico"
        data = _load_failures()
        counts = data.setdefault("counts", {})
        counts[signature] = counts.get(signature, 0) + 1
        data.setdefault("last_seen", {})[signature] = time.time()
        data.setdefault("proposals", {})
        _save_failures(data)

        if counts[signature] >= THRESHOLD and signature not in data["proposals"]:
            return _create_proposal(signature, task_title, error, counts[signature])
        return None
    except Exception:
        return None


def _create_proposal(signature: str, task_title: str, error: str,
                     count: int) -> Optional[str]:
    """Genera la bozza di skill in state/skill_proposals/."""
    try:
        info = SIGNATURES[signature]
        base_path = SKILLS_DIR / info["base"]
        base_content = ""
        if base_path.exists():
            base_content = base_path.read_text(encoding="utf-8")

        prop_id = f"{signature}_{int(time.time())}"
        draft_path = PROPOSALS_DIR / f"{prop_id}.md"
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

        # G1: Bozza con template CONCRETO (non solo la regola).
        # Il template è basato sulla firma: include un esempio di codice
        # corretto che il modello può copiare e adattare.
        templates = {
            "input_interattivo": (
                "import sys\n\n"
                "# MAI usare input(): hard-codifica i valori del task\n"
                "valori = [25]  # esempio dal task\n"
                "for v in valori:\n"
                "    risultato = v * 9 / 5 + 32\n"
                "    print(f\"RISULTATO={risultato}\")\n"),
            "marker_mancante": (
                "# Stampa TUTTI i marker richiesti dal task\n"
                "print(f\"MARKER={valore}\")  # adatta nome e valore\n"),
            "try_senza_except": (
                "try:\n"
                "    {{ FILL IT }}\n"
                "except Exception as e:\n"
                "    print(e)\n"),
            "loop_infinito": (
                "it = iter(coll)\n"
                "while True:\n"
                "    try:\n"
                "        print(next(it))\n"
                "    except StopIteration:\n"
                "        break\n"),
        }
        template = templates.get(signature, "# {{ IMPLEMENTAZIONE }}\n")

        learned = (
            "\n\n---\n# REGOLA APPRESA (bozza — da approvare)\n\n"
            f"Firma fallimento: `{signature}` ({info['label']})\n"
            f"Occorrenze osservate: {count}\n"
            f"Ultimo task: {task_title[:120]}\n"
            f"Ultimo errore: {error[:200]}\n\n"
            "## Regola\n"
            f"{info['rule']}\n\n"
            "## Template concreto\n"
            f"```python\n{template}```\n\n"
            "## Azione richiesta\n"
            "Rivedi questa bozza, modificala se necessario, poi approva con:\n"
            f"  python -m CORE.skill_proposer --approve {prop_id}\n"
            "oppure rifiuta con:\n"
            f"  python -m CORE.skill_proposer --reject {prop_id}\n"
        )
        draft_path.write_text(base_content + learned, encoding="utf-8")

        # Registra la proposta
        data = _load_failures()
        data.setdefault("proposals", {})[signature] = {
            "id": prop_id,
            "path": str(draft_path),
            "count": count,
            "created_at": time.time(),
            "status": "pending",
        }
        _save_failures(data)
        return prop_id
    except Exception:
        return None


def pending_proposals() -> list[dict]:
    """Lista delle bozze in attesa di approvazione."""
    try:
        data = _load_failures()
        out = []
        for sig, info in data.get("proposals", {}).items():
            p = Path(info["path"])
            if info.get("status") == "pending" and p.exists():
                out.append({
                    "id": info["id"],
                    "signature": sig,
                    "label": SIGNATURES.get(sig, {}).get("label", sig),
                    "count": info.get("count", 0),
                    "path": str(p),
                    "preview": p.read_text(encoding="utf-8")[:400],
                })
        return out
    except Exception:
        return []


def approve_proposal(prop_id: str,
                     report: Optional[GateReport] = None) -> bool:
    """Approva una bozza: la sposta in SKILLS/ (dove il matcher la carica).

    Chiamata manuale (CLI) = approvazione umana esplicita. Quella automatica
    passa da `auto_approve_ready`, che richiede un GateReport verde. In ogni
    caso la sovrascrittura NON è silenziosa: backup `.backup.md` + report
    salvato nei metadati della proposta.
    """
    try:
        data = _load_failures()
        for sig, info in data.get("proposals", {}).items():
            if info.get("id") == prop_id and info.get("status") == "pending":
                src = Path(info["path"])
                if not src.exists():
                    return False
                # nome skill dal filename della base (stesso id della base)
                base = SIGNATURES[sig]["base"]
                skill_name = base  # sovrascrive la skill base con la versione appresa
                dst = SKILLS_DIR / skill_name
                # Backup della skill base prima di sovrascrivere
                backup_path = None
                if dst.exists():
                    backup = SKILLS_DIR / f"{dst.stem}.backup.md"
                    shutil.copy2(dst, backup)
                    backup_path = str(backup)
                shutil.move(str(src), str(dst))
                info["status"] = "approved"
                info["approved_at"] = time.time()
                info["backup"] = backup_path
                info["mode"] = "auto" if report is not None else "manual"
                if report is not None:
                    info["gate_report"] = report.to_dict()
                _save_failures(data)
                return True
        return False
    except Exception:
        return False


def reject_proposal(prop_id: str) -> bool:
    """Rifiuta una bozza: la cancella e resetta il contatore della firma."""
    try:
        data = _load_failures()
        for sig, info in data.get("proposals", {}).items():
            if info.get("id") == prop_id and info.get("status") == "pending":
                p = Path(info["path"])
                if p.exists():
                    p.unlink()
                info["status"] = "rejected"
                info["rejected_at"] = time.time()
                # resetta il contatore: l'utente ha detto "non è un problema"
                data.setdefault("counts", {})[sig] = 0
                _save_failures(data)
                return True
        return False
    except Exception:
        return False


# ── B2: auto-approvazione SOLO con gate verde ──────────────────────────
def auto_approve_ready(skill_id: str) -> tuple[Optional[str], Optional[GateReport]]:
    """Dopo 3 successi senza fallimenti valuta il candidato col gate.

    - gate verde → approvazione con backup e report salvato;
    - gate rosso → bozza INTATTA in `state/skill_proposals/`, report rosso
      persistito per la review (nessuna sovrascrittura silenziosa).

    Ritorna `(id_approvato, report)`. Fail-open: errori → (None, None).
    """
    try:
        data = _load_failures()
        u = data.get("usage", {}).get(skill_id, {})
        if u.get("success", 0) < 3 or u.get("fail", 0) != 0:
            return None, None
        for sig, info in data.get("proposals", {}).items():
            if info.get("status") == "pending" and sig in skill_id:
                report = gate_proposal(info.get("path", ""), sig,
                                       info.get("id", ""))
                _record_gate_report(info["id"], report)
                if not report.ok:
                    return None, report
                approved = approve_proposal(info["id"], report=report)
                return (info["id"] if approved else None), report
        return None, None
    except Exception:
        return None, None


def record_skill_usage(skill_id: str, success: bool) -> Optional[str]:
    """Traccia l'uso di una skill suggerita. Dopo 3 successi senza
    fallimenti prova l'auto-approvazione, ma solo se il gate è verde.
    Ritorna l'id approvato o None. Fail-open.
    """
    try:
        data = _load_failures()
        usage = data.setdefault("usage", {})
        u = usage.setdefault(skill_id, {"success": 0, "fail": 0})
        if success:
            u["success"] = u.get("success", 0) + 1
        else:
            u["fail"] = u.get("fail", 0) + 1
        _save_failures(data)

        approved, _report = auto_approve_ready(skill_id)
        return approved
    except Exception:
        return None


def _emit(text: str) -> None:
    """Output della CLI (sys.stdout: nessun print() in CORE/, regola W005)."""
    sys.stdout.write(text + "\n")


def _cli() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m CORE.skill_proposer",
        description="M8: bozze di skill generate dai fallimenti ricorrenti.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true",
                   help="Lista le bozze in attesa di approvazione.")
    g.add_argument("--approve", metavar="ID",
                   help="Approva una bozza (la sposta in SKILLS/).")
    g.add_argument("--reject", metavar="ID",
                   help="Rifiuta una bozza (la cancella).")
    g.add_argument("--gate", metavar="ID",
                   help="Mostra il report gate deterministico della bozza.")
    args = parser.parse_args()

    if args.list:
        props = pending_proposals()
        if not props:
            _emit("Nessuna bozza in attesa.")
            return 0
        for p in props:
            _emit(f"\n[{p['id']}] {p['label']} (occorrenze: {p['count']})")
            _emit(f"  file: {p['path']}")
            _emit(f"  preview: {p['preview'][:200].replace(chr(10), ' | ')}")
        return 0
    if args.approve:
        ok = approve_proposal(args.approve)
        _emit("APPROVATA" if ok else "NON TROVATA / già gestita")
        return 0 if ok else 1
    if args.reject:
        ok = reject_proposal(args.reject)
        _emit("RIFIUTATA" if ok else "NON TROVATA / già gestita")
        return 0 if ok else 1
    if args.gate:
        report = gate_report(args.gate)
        if report is None:
            _emit("Nessun report gate per questa bozza "
                  "(usare 3 successi per triggerare la valutazione).")
            return 1
        _emit(report.markdown())
        return 0 if report.ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
