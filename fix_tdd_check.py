#!/usr/bin/env python3
"""
fix_tdd_check.py — Disabilita TDD check obbligatorio + semplifica quality check.

Il TDD check richiede che il worker scriva PRIMA un test che fallisce, POI
implementi. Per modelli piccoli (phi3:mini 3.8B) questo è troppo complesso.
Rendiamo il check opzionale (solo warning, non blocca done=true).
"""
import shutil
from pathlib import Path

ORCH_FILE = Path("orchestrator.py")
BACKUP = Path("orchestrator.py.bak.tdd")


def main():
    if not ORCH_FILE.exists():
        return 1

    content = ORCH_FILE.read_text()

    if "TDD check disabilitato (opzionale)" in content:
        print("✓ Fix già applicato, skip")
        return 0

    shutil.copy2(ORCH_FILE, BACKUP)
    modified = False

    # === Fix 1: Disabilita TDD check (lo rende un warning, non blocca) ===
    OLD_TDD = '''            if action.get("done"):
                # --- TDD VERIFICATION ---
                if is_tdd_required and not tdd_verified:
                    history = self.memory.get_history()
                    has_test_file = any("write_file" in e.get("content", "") and "test_" in e.get("content", "") for e in history)
                    has_failed_run = any("run_test_suite" in e.get("content", "") and "FAILED" in e.get("content", "") for e in history)

                    if not (has_test_file and has_failed_run):
                        self.log.warn(f"[{self.agent_id}] TDD Violation: No failing test found before completion.")
                        prompt = (
                            "ERRORE: Violazione TDD. Prima di implementare la soluzione, "
                            "DEVI: 1) Scrivere un test che fallisca, 2) Eseguirlo con `run_test_suite` "
                            "per confermare il fallimento. Solo allora puoi implementare e risolvere.\\n\\n"
                            "Riprova ora:"
                        )
                        continue'''

    NEW_TDD = '''            if action.get("done"):
                # --- TDD VERIFICATION (disabilitato per modelli piccoli) ---
                # TDD check disabilitato (opzionale): era troppo restrittivo per phi3:mini.
                # Il worker può dichiarare done=true senza dover prima scrivere test falliti.
                # L'auditor comunque verificherà la qualità.
                if False:  # was: is_tdd_required and not tdd_verified
                    pass  # no-op'''

    if OLD_TDD in content:
        content = content.replace(OLD_TDD, NEW_TDD, 1)
        modified = True
        print("✓ TDD check disabilitato (era troppo restrittivo per phi3:mini)")
    else:
        print("⚠  Pattern TDD non trovato esattamente, skip")

    # === Fix 2: Rendi il quality check meno severo (solo warning se test non passati) ===
    OLD_QC = '''                if test_passed is False:
                    self.log.warn(f"[{self.agent_id}] task marked done without passing tests. Rejecting.")
                    prompt = (
                        "ERRORE: Non puoi dichiarare il task come 'done' senza aver "
                        "dimostrato che il codice funziona. DEVI eseguire `run_test_suite` "
                        "e assicurarti che tutti i test passino prima di terminare.\\n\\n"
                        "Riprova ora:"
                    )
                    continue'''

    NEW_QC = '''                if test_passed is False:
                    # Quality check rilassato: solo warning, non blocca done=true.
                    # L'auditor verificherà comunque la qualità del codice.
                    self.log.info(f"[{self.agent_id}] task marked done without passing tests (warning only).")'''

    if OLD_QC in content:
        content = content.replace(OLD_QC, NEW_QC, 1)
        modified = True
        print("✓ Quality check rilassato (warning only, non blocca)")
    else:
        print("⚠  Pattern quality check non trovato, skip")

    if modified:
        ORCH_FILE.write_text(content)
        print(f"\n✓ Fix applicato a {ORCH_FILE}")
        print("\nOra riavvia:")
        print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2 && ./avvia.sh")
    else:
        print("\n⚠  Nessuna modifica applicata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
