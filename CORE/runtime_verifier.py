"""Runtime verification harness (Cycle 56).

Smoke test sui file scritti dal worker e sul boot del sistema.

- `verify_python(path)`: py_compile sul file (bloccante).
- `verify_tests(path)`: se il file e' un test, lo esegue via pytest.
- `verify_task_files(paths)`: pipeline su lista di file (usata da write_file).
- `verify_boot(module, args, timeout)`: boot smoke headless del modulo.

Su fallimento il verifier restituisce una stringa `ERROR: ...` — il caller
(feed orchestrator/correction loop) propaga il feedback specifico al task.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


class RuntimeVerifier:
    def __init__(self, project_root, logger,
                 timeout_bash: int = 30, timeout_py: int = 60,
                 timeout_test: int = 180, timeout_boot: int = 15):
        self.project_root = Path(project_root).resolve()
        self.log = logger
        self.timeout_bash = int(timeout_bash)
        self.timeout_py = int(timeout_py)
        self.timeout_test = int(timeout_test)
        self.timeout_boot = int(timeout_boot)

    # ------------------------------------------------------------------
    def _rel(self, path: Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.project_root))
        except Exception:
            return str(path)

    # ------------------------------------------------------------------
    def verify_python(self, path) -> str:
        """Sintassi + compilazione via py_compile (gate bloccante)."""
        p = Path(path)
        if not p.exists():
            return f"ERROR: runtime verify failed for {self._rel(p)}: file not found"
        try:
            import py_compile
            py_compile.compile(str(p), doraise=True)
            return f"OK: runtime verify {self._rel(p)}: py_compile OK"
        except Exception as e:
            return (f"ERROR: runtime verify failed for {self._rel(p)}: "
                    f"SYNTAX ERROR: {e}")

    # ------------------------------------------------------------------
    def verify_tests(self, path) -> str:
        """Se il file e' un test, lo esegue (pytest) e verifica il risultato."""
        p = Path(path)
        name = p.name.lower()
        is_test = (name.startswith("test") or name.endswith("_test.py")
                   or "_test." in name)
        if not is_test:
            return f"SKIP: {self._rel(p)} not a test file"
        cmd = [sys.executable, "-m", "pytest", str(p), "-q", "--no-header",
               "-p", "no:cacheprovider"]
        try:
            proc = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True,
                text=True, timeout=self.timeout_test,
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "")[-800:]
                return (f"ERROR: runtime verify failed for {self._rel(p)}: "
                        f"TEST FAILED rc={proc.returncode}: {err}")
            return f"OK: runtime verify {self._rel(p)}: tests passed"
        except Exception as e:
            return (f"ERROR: runtime verify failed for {self._rel(p)}: "
                    f"TEST RUN ERROR: {e}")

    # ------------------------------------------------------------------
    def verify_task_files(self, paths) -> str:
        """Pipeline smoke test su una lista di path (write_file integration)."""
        results = []
        for raw in (paths or []):
            p = Path(raw)
            if not p.exists():
                results.append(f"ERROR: runtime verify failed for {self._rel(p)}: file not found")
                continue
            if p.suffix == ".py":
                r = self.verify_python(p)
            elif self._is_test_name(p):
                r = self.verify_tests(p)
            else:
                r = f"OK: runtime verify {self._rel(p)}: no check needed"
            results.append(r)
        if any(r.startswith("ERROR") for r in results):
            return "; ".join(r for r in results if r.startswith("ERROR"))
        return "OK: runtime verify all files passed"

    @staticmethod
    def _is_test_name(path: Path) -> bool:
        name = path.name.lower()
        return (name.startswith("test") or name.endswith("_test.py")
                or "_test." in name)

    # ------------------------------------------------------------------
    def verify_boot(self, module: str = "CORE.orchestrator",
                    args: Optional[Sequence[str]] = None,
                    timeout: int = 15) -> str:
        """Boot smoke headless: avvia il modulo con timeout e verifica che
        non crashi immediatamente."""
        cmd = [sys.executable, "-m", module] + list(args or [])
        try:
            proc = subprocess.run(
                cmd, cwd=self.project_root, capture_output=True,
                text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "")[-600:]
                return (f"ERROR: runtime verify failed for boot:{module} "
                        f"rc={proc.returncode}: {err}")
            return f"OK: runtime verify boot:{module} clean"
        except Exception as e:
            return f"ERROR: runtime verify failed for boot:{module}: {e}"
