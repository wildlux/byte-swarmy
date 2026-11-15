"""
external_benchmark.py — Benchmark esterni e validazione indipendente (Cycle 59).

Esegue byte-swarmy contro un bersaglio esterno e umile (bench_target/, un
mini-repo Python di 4 file) con 8-10 specifiche di refactoring atomiche e
verificabili, e confronta il risultato con un **baseline modello nudo** (solo
models.call, nessun harness: niente correction loop, niente audit, niente risk
gate).

Metriche misurate (una per task, sia per harness che per naked):
  - successo al primo colpo (nessun retry)
  - successo dopo correction loop (il task passa eventualmente i gate)
  - falsi negativi del gate (task bloccati dal risk gate / audit che un
    umano avrebbe approvato — validazione manuale da registrare)
  - tempo umano netto (ore di supervisione vs ore di lavoro manuale:
    campo da compilare a mano dall'utente, il sistema registra solo il wall
    clock del sistema)

I risultati grezzi vengono salvati in state/benchmarks/ (JSON, gitignored).
Il report testuale va in DOCS/BENCH.md (questa è la sede dei report).

L'esecuzione richiede Ollama raggiungibile; se non disponibile, il modulo
gira in modalità "dry-run" (solo struttura, nessuna chiamata LLM) ed e'
coperto da test unitari con mock.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import logging

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCHMARKS_DIR = ROOT / "state" / "benchmarks"
BENCH_TARGET_DIR = ROOT / "bench_target"


# ====================================================================
# Dataset di task di refactoring atomici (8 task, verificabili)
# ====================================================================
# Ogni task: id, titolo, descrizione, file target, criterio di successo
# (funzione check sul contenuto del file dopo l'esecuzione).
# I criteri sono scritti come codice Python che riceve `content` (str del
# file modificato) e ritorna True se il refactoring e' stato applicato.
# ====================================================================

BENCH_TASKS = [
    {
        "id": "ext-01",
        "title": "Aggiungi type hints a tutte le funzioni pubbliche di utils.py",
        "description": (
            "Aggiungi type hints a tutte le funzioni pubbliche di "
            "bench_target/utils.py (parse_email, slugify, is_valid_password, "
            "format_currency). Non cambiare la logica, solo le signature."
        ),
        "file": "utils.py",
        "check": (
            "lambda content: 'def parse_email(email: str)' in content and "
            "'def slugify(text: str)' in content and "
            "'def is_valid_password(password: str)' in content and "
            "'def format_currency(amount, symbol: str = \"$\")' in content"
        ),
    },
    {
        "id": "ext-02",
        "title": "Estrai la logica di parsing in una funzione pura in validator.py",
        "description": (
            "In bench_target/core/validator.py, estrai la logica di validazione "
            "dell'email in una funzione pura chiamata _email_pattern() che "
            "ritorna la regex usata, e usala in validate_email. Non cambiare il "
            "comportamento pubblico di validate_email."
        ),
        "file": "core/validator.py",
        "check": (
            "lambda content: '_email_pattern' in content and "
            "def _email_pattern in content.replace('def ', 'DEF ') or "
            "'_email_pattern()' in content or '_email_pattern =' in content"
        ),
    },
    {
        "id": "ext-03",
        "title": "Sostituisci print con logging in core/processor.py",
        "description": (
            "In bench_target/core/processor.py, sostituisci ogni eventuale "
            "uso di print con il modulo logging (import logging + logger = "
            "logging.getLogger(__name__))."
        ),
        "file": "core/processor.py",
        "check": (
            "lambda content: 'import logging' in content and "
            "'logging.getLogger' in content"
        ),
    },
    {
        "id": "ext-04",
        "title": "Aggiungi docstring a tutte le funzioni pubbliche di models/user.py",
        "description": (
            "Aggiungi docstring a tutte le funzioni/metodi pubblici di "
            "bench_target/models/user.py (__init__, is_admin, can_edit, "
            "to_dict)."
        ),
        "file": "models/user.py",
        "check": (
            "lambda content: '\"\"\"Rappresenta un utente' in content and "
            "'\"\"\"Ritorna True' in content"
        ),
    },
    {
        "id": "ext-05",
        "title": "Rendi filter_active una list comprehension in core/processor.py",
        "description": (
            "Riscrivi filter_active in bench_target/core/processor.py usando "
            "una list comprehension invece del ciclo for con append."
        ),
        "file": "core/processor.py",
        "check": (
            "lambda content: 'return [item for item in items if item.get(' in content"
        ),
    },
    {
        "id": "ext-06",
        "title": "Aggiungi validazione lunghezza minima password in validator.py",
        "description": (
            "In bench_target/core/validator.py, estendi is_valid_password per "
            "verificare anche che la password abbia almeno 10 caratteri "
            "(oltre a maiuscola e 8 char)."
        ),
        "file": "core/validator.py",
        "check": (
            "lambda content: 'len(password) < 10' in content or "
            "'>= 10' in content or '10' in content.split('password')[1]"
        ),
    },
    {
        "id": "ext-07",
        "title": "Aggiungi supporto simboli negativi a format_currency in utils.py",
        "description": (
            "In bench_target/utils.py, modifica format_currency per gestire "
            "importi negativi (mostrare il segno meno prima del simbolo)."
        ),
        "file": "utils.py",
        "check": (
            "lambda content: '-' in content and 'amount < 0' in content or "
            "'abs(amount)' in content"
        ),
    },
    {
        "id": "ext-08",
        "title": "Estrai group_by_category come funzione generica in core/processor.py",
        "description": (
            "Estrai la logica di group_by_category in una funzione generica "
            "_group_by(items, key_func) in bench_target/core/processor.py e "
            "fai chiamare group_by_category a _group_by con lambda."
        ),
        "file": "core/processor.py",
        "check": (
            "lambda content: '_group_by' in content and "
            "'lambda item' in content"
        ),
    },
]


class ExternalBenchmark:
    """Esegue benchmark esterni e li confronta con un baseline modello nudo."""

    def __init__(self, project_root, bench_target_dir=BENCH_TARGET_DIR,
                 models=None, log=None, benchmarks_dir=BENCHMARKS_DIR):
        self.project_root = Path(project_root).resolve()
        self.bench_target_dir = Path(bench_target_dir).resolve()
        self.models = models
        self.log = log
        self.benchmarks_dir = Path(benchmarks_dir)
        self.benchmarks_dir.mkdir(parents=True, exist_ok=True)
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tasks": [],
            "summary": {},
        }

    # ------------------------------------------------------------------
    def _copy_target_to_sandbox(self, sandbox_dir: Path) -> Path:
        """Copia bench_target in una sandbox isolata per non toccare l'originale."""
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)
        shutil.copytree(self.bench_target_dir, sandbox_dir)
        return sandbox_dir

    # ------------------------------------------------------------------
    def _read_target_file(self, sandbox_dir: Path, rel_path: str) -> str:
        p = sandbox_dir / rel_path
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8", errors="replace")

    # ------------------------------------------------------------------
    def _evaluate_check(self, check_code: str, content: str) -> bool:
        """Esegue il criterio di successo (lambda content -> bool)."""
        try:
            namespace = {"content": content}
            compiled = compile(check_code, "<bench-check>", "eval")
            fn = eval(compiled, {"__builtins__": {}}, namespace)
            return bool(fn(content))
        except Exception as e:
            if self.log:
                self.log.warning(f"check evaluation failed: {e}")
            return False

    # ------------------------------------------------------------------
    def run_harness_task(self, task: dict, worker_factory,
                         max_retries: int = 3) -> dict:
        """Esegue un task tramite il worker ReAct (con harness).

        Args:
            task: dict da BENCH_TASKS.
            worker_factory: callable(sandbox_dir) -> Worker istanza configurata
                per operare sulla sandbox. Il worker deve esporre execute(task).
            max_retries: numero massimo di retry del correction loop.

        Ritorna dict con le metriche del task.
        """
        sandbox_dir = self.project_root / "state" / "bench_sandbox_harness"
        self._copy_target_to_sandbox(sandbox_dir)

        worker = worker_factory(sandbox_dir)
        bench_task = {
            "id": task["id"],
            "title": task["title"],
            "description": task["description"],
            "type": "fix",
            "source": "external_benchmark",
        }

        start = time.time()
        attempts = 0
        success_first_try = False
        success_after_loop = False
        error = None
        gate_blocks = 0

        try:
            # Primo tentativo
            attempts += 1
            result = worker.execute(bench_task)
            content_after = self._read_target_file(sandbox_dir, task["file"])
            success_first_try = self._evaluate_check(task["check"], content_after)

            # Correction loop se non riuscito al primo colpo
            if not success_first_try:
                while attempts < max_retries:
                    attempts += 1
                    bench_task["description"] += (
                        f"\n\n⚠️ TENTATIVO {attempts}: il refactoring non e' "
                        f"stato applicato correttamente. Riprova applicando "
                        f"esattamente quanto richiesto."
                    )
                    result = worker.execute(bench_task)
                    content_after = self._read_target_file(
                        sandbox_dir, task["file"]
                    )
                    if self._evaluate_check(task["check"], content_after):
                        success_after_loop = True
                        break
            else:
                success_after_loop = True

        except Exception as e:
            error = str(e)
            if self.log:
                self.log.error(f"harness task {task['id']} exception: {e}")

        wall = time.time() - start

        return {
            "task_id": task["id"],
            "title": task["title"],
            "mode": "harness",
            "file": task["file"],
            "attempts": attempts,
            "success_first_try": success_first_try,
            "success_after_loop": success_after_loop,
            "gate_blocks": gate_blocks,
            "error": error,
            "wall_seconds": round(wall, 2),
        }

    # ------------------------------------------------------------------
    def run_naked_task(self, task: dict) -> dict:
        """Esegue un task con il modello nudo (nessun harness).

        Chiama direttamente models.call con un prompt diretto: nessuna
        correction loop, nessun audit, nessun risk gate. Il modello riceve
        il contenuto attuale del file e deve restituire il nuovo contenuto.

        Ritorna dict con le metriche del task.
        """
        sandbox_dir = self.project_root / "state" / "bench_sandbox_naked"
        self._copy_target_to_sandbox(sandbox_dir)

        rel_path = task["file"]
        content_before = self._read_target_file(sandbox_dir, rel_path)

        prompt = (
            "Sei un programmatore Python. Ricevi il contenuto di un file e "
            "devi applicare una modifica di refactoring. Ritorna SOLO il "
            "nuovo contenuto completo del file, niente spiegazioni, niente "
            "blocchi markdown.\n\n"
            f"FILE: {rel_path}\n"
            f"TASK: {task['title']}\n"
            f"DESCRIZIONE: {task['description']}\n\n"
            f"CONTENUTO ATTUALE:\n```python\n{content_before}\n```\n\n"
            f"NUOVO CONTENUTO:"
        )

        start = time.time()
        success = False
        error = None
        response = ""

        try:
            response = self.models.call(
                model_key="worker_coder",
                prompt=prompt,
                system="You are a Python refactoring assistant. Output only the new file content.",
                max_tokens=1500,
            )
            response = (response or "").strip()
            # Rimuovi blocchi markdown se presenti
            if response.startswith("```"):
                parts = response.split("```", 2)
                if len(parts) >= 2:
                    response = parts[1]
                    if response.startswith("python"):
                        response = response[len("python"):].strip()

            # Salva il nuovo contenuto nel file target della sandbox
            target_file = sandbox_dir / rel_path
            target_file.write_text(response, encoding="utf-8")

            content_after = self._read_target_file(sandbox_dir, rel_path)
            success = self._evaluate_check(task["check"], content_after)

        except Exception as e:
            error = str(e)
            if self.log:
                self.log.error(f"naked task {task['id']} exception: {e}")

        wall = time.time() - start

        return {
            "task_id": task["id"],
            "title": task["title"],
            "mode": "naked",
            "file": task["file"],
            "attempts": 1,
            "success_first_try": success,
            "success_after_loop": success,
            "gate_blocks": 0,
            "error": error,
            "wall_seconds": round(wall, 2),
            "response_preview": response[:200] if response else "",
        }

    # ------------------------------------------------------------------
    def run_all(self, worker_factory=None) -> dict:
        """Esegue tutti i task sia con harness che con naked.

        Se worker_factory e' None, il mode harness salta i task (marcati
        skipped) e resta solo il mode naked (richiede self.models).
        """
        harness_results = []
        naked_results = []

        for task in BENCH_TASKS:
            # --- harness ---
            if worker_factory is not None:
                r = self.run_harness_task(task, worker_factory)
                harness_results.append(r)
            else:
                harness_results.append({
                    "task_id": task["id"],
                    "title": task["title"],
                    "mode": "harness",
                    "file": task["file"],
                    "skipped": "no worker_factory (Ollama non disponibile)",
                })

            # --- naked ---
            r = self.run_naked_task(task)
            naked_results.append(r)

        self.results["tasks"] = {
            "harness": harness_results,
            "naked": naked_results,
        }
        self.results["summary"] = self._compute_summary(
            harness_results, naked_results
        )
        return self.results

    # ------------------------------------------------------------------
    def _compute_summary(self, harness_results, naked_results) -> dict:
        def agg(results):
            real = [r for r in results if not r.get("skipped")]
            if not real:
                return {"count": 0}
            first = sum(1 for r in real if r.get("success_first_try"))
            after = sum(1 for r in real if r.get("success_after_loop"))
            blocked = sum(1 for r in real if r.get("gate_blocks", 0) > 0)
            errors = sum(1 for r in real if r.get("error"))
            wall = sum(r.get("wall_seconds", 0) for r in real)
            return {
                "count": len(real),
                "success_first_try": first,
                "success_after_loop": after,
                "first_try_rate": round(first / len(real), 3),
                "after_loop_rate": round(after / len(real), 3),
                "gate_blocks": blocked,
                "errors": errors,
                "wall_seconds_total": round(wall, 2),
                "wall_avg_per_task": round(wall / len(real), 2),
            }

        return {
            "harness": agg(harness_results),
            "naked": agg(naked_results),
            "harness_improvement_first_try": None,
            "harness_improvement_after_loop": None,
        }

    # ------------------------------------------------------------------
    def save_results(self, filename: Optional[str] = None) -> Path:
        """Salva i risultati in state/benchmarks/ (JSON, gitignored)."""
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"external_bench-{ts}.json"
        path = self.benchmarks_dir / filename
        path.write_text(json.dumps(self.results, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        if self.log:
            self.log.info(f"external benchmark results salvati in {path}")
        return path

    # ------------------------------------------------------------------
    def generate_report(self) -> str:
        """Genera il report testuale per DOCS/BENCH.md."""
        s = self.results.get("summary", {})
        h = s.get("harness", {})
        n = s.get("naked", {})

        lines = [
            "",
            "---",
            "",
            f"## {datetime.now().strftime('%Y-%m-%d') } — Benchmark esterno (Cycle 59)",
            "",
            "**Obiettivo**: sapere se byte-swarmy, così com'è oggi, produce "
            "valore misurabile su task di refactoring esterni e non progettati "
            "da noi (Fase 0 del piano d'attacco senior).",
            "",
            "**Bersaglio**: `bench_target/` — mini-repo Python di 4 file "
            "(utils, core/processor, core/validator, models/user).",
            "**Task**: 8 specifiche di refactoring atomiche e verificabili "
            "(type hints, estrazione funzioni pure, logging, docstring, ...).",
            "",
            "| metrica | harness (con correction loop + audit) | naked (modello nudo) | delta |",
            "|---------|--------------------------------------|----------------------|-------|",
        ]

        def rate(d, key):
            v = d.get(key)
            return f"{v:.0%}" if isinstance(v, float) else str(v)

        lines.append(
            f"| successo al primo colpo | {rate(h, 'first_try_rate')} "
            f"({h.get('success_first_try', 0)}/{h.get('count', 0)}) | "
            f"{rate(n, 'first_try_rate')} "
            f"({n.get('success_first_try', 0)}/{n.get('count', 0)}) | "
            f"{self._delta_pct(h, n, 'first_try_rate')} |"
        )
        lines.append(
            f"| successo dopo correction loop | {rate(h, 'after_loop_rate')} "
            f"({h.get('success_after_loop', 0)}/{h.get('count', 0)}) | "
            f"{rate(n, 'after_loop_rate')} "
            f"({n.get('success_after_loop', 0)}/{n.get('count', 0)}) | "
            f"{self._delta_pct(h, n, 'after_loop_rate')} |"
        )
        lines.append(
            f"| falsi negativi gate (bloccati) | {h.get('gate_blocks', 0)} | "
            f"{n.get('gate_blocks', 0)} | n.c. |"
        )
        lines.append(
            f"| errori di esecuzione | {h.get('errors', 0)} | {n.get('errors', 0)} | n.c. |"
        )
        lines.append(
            f"| wall totale (s) | {h.get('wall_seconds_total', 0)} | "
            f"{n.get('wall_seconds_total', 0)} | n.c. |"
        )
        lines.append(
            f"| wall medio/task (s) | {h.get('wall_avg_per_task', 0)} | "
            f"{n.get('wall_avg_per_task', 0)} | n.c. |"
        )

        lines += [
            "",
            "**Criterio di uscita (Fase 0):** se il tempo umano netto e' negativo "
            "o nullo (supervisione >= lavoro manuale), fermarsi e semplificare "
            "prima di aggiungere feature. Se positivo anche solo del 20%, si ha "
            "qualcosa su cui costruire.",
            "",
            "**Tempo umano netto:** campo da compilare a mano dall'utente "
            "(ore di supervisione vs ore di lavoro manuale). Non e' misurabile "
            "automaticamente dal sistema.",
            "",
            "**Metodologia riproducibile:** i JSON grezzi sono in "
            "`state/benchmarks/` (gitignored). Eseguire con: "
            "`.venv/bin/python -m CORE.external_benchmark --run` (richiede "
            "Ollama). Test senza Ollama: `pytest tests/test_external_benchmark.py`.",
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _delta_pct(harness, naked, key):
        hv = harness.get(key)
        nv = naked.get(key)
        if hv is None or nv is None or nv == 0:
            return "n.c."
        try:
            delta = (hv - nv) / nv * 100
            sign = "+" if delta > 0 else ""
            return f"{sign}{delta:.0f}%"
        except Exception:
            return "n.c."


# ====================================================================
# Entry point CLI — esecuzione reale del benchmark esterno
# ====================================================================

def build_real_worker_factory(config_path: str, log) -> callable:
    """Costruisce una factory di Worker veri (Ollama reale) per il benchmark.

    La factory riceve una sandbox_dir e ritorna un Worker configurato per
    operare su quella directory come project_root.
    """
    import tomllib

    from CORE.constants import DEFAULT_PATHS
    from CORE.models import ModelClient
    from CORE.memory import AgentMemory
    from CORE.tools import ToolSet
    from CORE.worker import Worker

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # ToolSet condiviso (safe sulla sandbox per write_file)
    def _make_tools(sandbox_dir: Path) -> ToolSet:
        cfg = dict(config)
        cfg["paths"] = dict(config.get("paths", {}))
        cfg["paths"]["project_root"] = str(sandbox_dir)
        return ToolSet(cfg, log)

    # ModelClient condiviso
    models = ModelClient(config, log)

    memories = {}

    def factory(sandbox_dir: Path) -> Worker:
        agent_id = "bench-worker"
        if agent_id not in memories:
            memories[agent_id] = AgentMemory(
                agent_id=agent_id,
                state_dir=Path(config.get("paths", {}).get(
                    "state_dir", DEFAULT_PATHS["state_dir"])),
                model_client=models,
                logger=log,
            )
        tools = _make_tools(sandbox_dir)
        tools.set_worker("bench-worker")
        return Worker(
            agent_id=agent_id,
            model_key="worker_coder",
            tools=tools,
            memory=memories[agent_id],
            model_client=models,
            logger=log,
        )

    return factory


def _get_logger() -> logging.Logger:
    import logging
    log = logging.getLogger("external-benchmark")
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        log.addHandler(h)
    log.setLevel(logging.INFO)
    return log


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark esterno byte-swarmy (Cycle 59)"
    )
    parser.add_argument("--run", action="store_true",
                        help="Esegue il benchmark (richiede Ollama)")
    parser.add_argument("--config", default="CONFIG/config.toml",
                        help="Percorso del config TOML")
    parser.add_argument("--save-report", action="store_true",
                        help="Aggiunge il report a DOCS/BENCH.md")
    parser.add_argument("--max-retries", type=int, default=3,
                        help="Max retry del correction loop")
    args = parser.parse_args()

    log = _get_logger()

    # Verifica Ollama
    import urllib.request
    ollama_host = "http://localhost:11434"
    try:
        with open(args.config, "rb") as f:
            import tomllib
            cfg = tomllib.load(f)
            ollama_host = cfg.get("ollama", {}).get("host", ollama_host)
    except Exception:
        pass

    try:
        with urllib.request.urlopen(ollama_host.rstrip("/") + "/api/tags",
                                    timeout=3.0):
            ollama_ok = True
    except Exception:
        ollama_ok = False

    if not ollama_ok:
        log.warning("Ollama non raggiungibile su %s — modalità dry-run", ollama_host)
        log.warning("Per eseguire il benchmark reale: avvia Ollama e rilancia con --run")
        eb = ExternalBenchmark(
            project_root=ROOT,
            models=None,
            log=log,
        )
        # Dry-run: struttura senza esecuzione LLM
        eb.results["dry_run"] = True
        path = eb.save_results()
        print(f"Dry-run completato, struttura salvata in {path}")
        return 0

    # Esecuzione reale
    factory = build_real_worker_factory(args.config, log)
    eb = ExternalBenchmark(
        project_root=ROOT,
        models=None,  # il worker usa il proprio ModelClient interno
        log=log,
    )
    results = eb.run_all(worker_factory=factory)
    path = eb.save_results()
    log.info(f"Risultati salvati in {path}")

    if args.save_report:
        report = eb.generate_report()
        bench_md = ROOT / "DOCS" / "BENCH.md"
        with open(bench_md, "a", encoding="utf-8") as f:
            f.write(report)
        log.info(f"Report aggiunto a {bench_md}")

    # Stampa sintesi a console
    s = results.get("summary", {})
    print("\n=== SINTESI BENCHMARK ESTERNO ===")
    print(f"Harness — primo colpo: {s.get('harness', {}).get('first_try_rate', 'n.c.')}")
    print(f"Harness — dopo loop:   {s.get('harness', {}).get('after_loop_rate', 'n.c.')}")
    print(f"Naked — primo colpo:   {s.get('naked', {}).get('first_try_rate', 'n.c.')}")
    print(f"Naked — dopo loop:     {s.get('naked', {}).get('after_loop_rate', 'n.c.')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

