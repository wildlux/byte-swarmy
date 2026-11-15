"""Test generation per nuovi percorsi di esecuzione (Cycle 57).

Dopo ogni `write_file` riuscita su un modulo Python, il worker genera
automaticamente un test di regressione che esercita le funzioni pubbliche
del file, lo esegue con pytest e, se fallisce, restituisce l'errore come
tool_result → entra nel correction loop con feedback specifico (non un
generico "syntax error").

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
        """Chiede al modello di generare un test per le funzioni pubbliche."""
        try:
            rel = file_path.relative_to(self.project_root)
        except ValueError:
            rel = file_path
        prompt = (
            "Genera un file di test Python per testare le funzioni pubbliche "
            f"del modulo {rel}.\n"
            "Usa SOLO pytest (no unittest), con test minimi ma significativi.\n"
            "Importa le funzioni dal modulo con import relativo corretto.\n"
            "Rispondi SOLO con il codice Python del file di test, niente altro.\n\n"
            f"Funzioni pubbliche da testare: {', '.join(funcs)}\n"
            f"Modulo: {rel}\n"
        )
        try:
            res = self.models.call(
                model_key="worker_coder",
                prompt=prompt,
                system="You write minimal pytest regression tests. Output only Python code.",
                max_tokens=600,
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
