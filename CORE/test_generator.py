"""Test generation per nuovi percorsi di esecuzione (Cycle 57).

Dopo ogni `write_file` riuscita su un modulo Python, il worker genera
automaticamente un test di regressione che esercita le funzioni pubbliche
del file, lo esegue con pytest e, se fallisce, restituisce l'errore come
tool_result → entra nel correction loop con feedback specifico (non un
generico "syntax error").

🆕 Cycle 65 — Regola termica dei test: generazione STADIALE. Nessuna
generazione LLM lunga e monolitica (surriscalda il portatile): prima lo
SCHELETRO del test (import + funzioni test_* vuote) verificato con
`pytest --collect-only` (scova subito gli errori di import/struttura,
il guasto più comune su modelli 3B, senza pagare la generazione dei
corpi), poi SOLO i corpi. Mai l'implementazione completa in una sola
generazione.

Nessuna ricorsione: i file dentro `tests/` e i file `test_*.py` vengono
saltati; ogni file sorgente viene testato una sola volta per task.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

_FUN_DEF = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)


class TestGenerator:
    """Genera ed esegue test di regressione per i nuovi percorsi scritti."""

    __test__ = False  # classe di supporto (non un test pytest)

    def __init__(self, project_root, models, log):
        self.project_root = Path(project_root).resolve()
        self.models = models
        self.log = log

    # ------------------------------------------------------------------
    def generate_and_verify(self, file_path: str, code: str) -> str:
        """Genera + esegue un test di regressione per il file scritto.

        Ritorna ``"OK: ..."`` se passa, ``"ERROR: ..."`` altrimenti.
        """
        p = Path(file_path)
        if p.suffix != ".py":
            return "OK: non è un modulo Python, skip"
        name = p.name
        if name.startswith("test_") or name.endswith("_test.py"):
            return "OK: è un file di test, skip"
        try:
            rel = p.relative_to(self.project_root)
            if "tests" in rel.parts:
                return "OK: dentro tests/, skip"
        except ValueError:
            pass

        funcs = self._extract_public_functions(code)
        if not funcs:
            return "OK: nessuna funzione pubblica, skip"

        test_content = self._generate_test(p, funcs)
        if not test_content or test_content.startswith("ERROR"):
            return test_content or "ERROR: test generation failed"

        test_path = self._write_test_file(p, test_content)
        if test_path is None:
            return "ERROR: impossibile scrivere il file di test"

        return self._run_pytest(test_path)

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_public_functions(code: str) -> list[str]:
        """Estrae i nomi delle funzioni pubbliche definite nel codice."""
        funcs = _FUN_DEF.findall(code)
        public = [f for f in funcs if not f.startswith("_")]
        seen = set()
        out = []
        for f in public:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out

    # ------------------------------------------------------------------
    def _generate_test(self, file_path: Path, funcs: list[str]) -> str:
        """Generazione STADIALE (🆕 Cycle 65: regola termica dei test).

        Generazioni LLM BREVI con verifica host-side tra una e l'altra,
        invece di chiedere il file completo in un colpo solo:
          Stadio 1 — SCHELETRO: import + funzioni test_* vuote (`pass`).
                     Verifica con `pytest --collect-only`: se import o
                     struttura sono rotti, ci si ferma qui senza pagare
                     la generazione dei corpi.
          Stadio 2 — CORPI: stesso scheletro, si riempiono SOLO i corpi
                     con assert minimi (nomi e import intatti).
        Mai l'implementazione completa in una sola generazione.
        """
        try:
            rel = file_path.relative_to(self.project_root)
        except ValueError:
            rel = file_path

        # ── Stadio 1: SCHELETRO (classe/funzioni vuote) ──
        skeleton_prompt = (
            "Genera SOLO lo SCHELETRO di un file di test pytest per il "
            f"modulo {rel}.\n"
            "NIENTE corpi: per ogni funzione elencata crea una funzione "
            "test_<nome>() vuota con solo `pass`.\n"
            "Importa le funzioni dal modulo con import relativo corretto.\n"
            "Rispondi SOLO con il codice Python dello scheletro, niente altro.\n\n"
            f"Funzioni pubbliche da testare: {', '.join(funcs)}\n"
            f"Modulo: {rel}\n"
        )
        skeleton = self._call_model(skeleton_prompt, max_tokens=250)
        if not skeleton or skeleton.startswith("ERROR"):
            return skeleton or "ERROR: test generation failed (scheletro vuoto)"

        test_path = self._write_test_file(file_path, skeleton)
        if test_path is None:
            return "ERROR: impossibile scrivere il file di test"

        collect_err = self._collect_check(test_path)
        if collect_err:
            try:
                test_path.unlink(missing_ok=True)
            except Exception:
                pass
            return (f"ERROR: scheletro test non valido "
                    f"(import/struttura): {collect_err}")

        # ── Stadio 2: CORPI (solo assert, struttura intatta) ──
        bodies_prompt = (
            "Ecco lo scheletro VERIFICATO di un file di test pytest per il "
            f"modulo {rel}. Riempi SOLO i corpi delle funzioni test_* con "
            "assert minimi e significativi. NON cambiare gli import né i "
            "nomi delle funzioni. Rispondi SOLO con il codice Python "
            "completo del file di test, niente altro.\n\n"
            f"SCHELETRO:\n{skeleton}\n"
            f"Modulo: {rel}\n"
        )
        full = self._call_model(bodies_prompt, max_tokens=500)
        if not full or full.startswith("ERROR"):
            try:
                test_path.unlink(missing_ok=True)
            except Exception:
                pass
            return (f"ERROR: stadio 2 (corpi) fallito: "
                    f"{full or 'risposta vuota'}")

        # Il modello non deve alterare la struttura verificata:
        # stessi nomi di test, stesso ordine.
        if self._test_func_names(full) != self._test_func_names(skeleton):
            try:
                test_path.unlink(missing_ok=True)
            except Exception:
                pass
            return ("ERROR: stadio 2 ha alterato la struttura dello "
                    "scheletro (nomi test cambiati)")
        return full

    # ------------------------------------------------------------------
    def _call_model(self, prompt: str, max_tokens: int) -> str:
        """Chiamata LLM breve + estrazione dal blocco markdown."""
        try:
            res = self.models.call(
                model_key="worker_coder",
                prompt=prompt,
                system="You write minimal pytest regression tests. Output only Python code.",
                max_tokens=max_tokens,
            )
            res = (res or "").strip()
            # Rimuovi eventuali blocchi markdown
            if res.startswith("```"):
                parts = res.split("```", 2)
                if len(parts) >= 2:
                    res = parts[1]
                    if res.startswith("python"):
                        res = res[len("python"):].strip()
            return res
        except Exception as e:
            return f"ERROR: test generation failed: {e}"

    # ------------------------------------------------------------------
    @staticmethod
    def _test_func_names(code: str) -> list[str]:
        """Nomi delle funzioni test_* nell'ordine di definizione."""
        return re.findall(r"^\s*def\s+(test_\w*)\s*\(", code, re.MULTILINE)

    # ------------------------------------------------------------------
    def _collect_check(self, test_path: Path) -> Optional[str]:
        """Verifica host-side dello scheletro con pytest --collect-only.

        Importa il file di test (che importa il modulo sotto test) SENZA
        eseguire i test: scova subito errori di import e di struttura.
        None = OK, altrimenti estratto dell'errore. Costo: ~1s host-side,
        zero LLM (la regola termica: la verifica tra gli stadi è gratis).
        """
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_path), "-q",
                 "--collect-only", "--no-header", "-p", "no:cacheprovider"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                out = (proc.stdout or "")[-400:]
                err = (proc.stderr or "")[-400:]
                return out or err or f"exit={proc.returncode}"
            return None
        except Exception as e:
            return str(e)

    # ------------------------------------------------------------------
    def _write_test_file(self, source_path: Path, test_content: str) -> Optional[Path]:
        """Scrive il file di test in tests/test_<nome>_regression.py."""
        try:
            tests_dir = self.project_root / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            stem = source_path.stem
            test_path = tests_dir / f"test_{stem}_regression.py"
            test_path.write_text(test_content, encoding="utf-8")
            return test_path
        except Exception as e:
            self.log.error(f"test generation: write test file failed: {e}")
            return None

    # ------------------------------------------------------------------
    def _run_pytest(self, test_path: Path) -> str:
        """Esegue pytest sul singolo file di test."""
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_path), "-q", "--no-header",
                 "-p", "no:cacheprovider"],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=180,
            )
            if proc.returncode != 0:
                out = (proc.stdout or "")[-600:]
                err = (proc.stderr or "")[-600:]
                return (
                    f"ERROR: regression test failed for {test_path.name}:\n{out}\n{err}"
                )
            return f"OK: regression test {test_path.name} passed"
        except Exception as e:
            return f"ERROR: regression test run failed for {test_path.name}: {e}"
