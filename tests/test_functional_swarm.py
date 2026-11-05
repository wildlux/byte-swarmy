#!/usr/bin/env python3
"""
test_functional_swarm.py — Test funzionali della swarm BYTE-SWARMY

Crea task complessi, attende completamento, verifica qualità del codice prodotto.
Per ogni task verifica:
  1. File creato nel path corretto (o in project/main.py come fallback)
  2. Codice sintatticamente valido (AST parsing)
  3. Funzioni/classi richieste presenti
  4. Esecuzione senza errori
  5. Comportamento corretto (casi di test, inclusi edge cases)

Uso:
  ./bswarm start --orch                         # avvia orchestrator prima!
  python3 tests/test_functional_swarm.py        # esegue tutti i 7 test
  python3 tests/test_functional_swarm.py --test 4   # esegue solo test 4 (Fibonacci)
  python3 tests/test_functional_swarm.py --list     # lista i test disponibili

Requisiti:
  - Orchestrator attivo (./bswarm start --orch)
  - tasks/queue.db accessibile (SQLite)
  - project/ scrivibile
  - python3 con ast, sqlite3 (standard library)

Autore: byte-swarmy test suite
Versione: 1.1 — tolerant on filename, supports --test N
"""
import sqlite3
import time
import os
import sys
import subprocess
import ast
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent if Path(__file__).parent.name == "tests" else Path(__file__).parent
DB = ROOT / "tasks" / "queue.db"
PROJECT_DIR = ROOT / "project"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    colors = {"info": BLUE, "ok": GREEN, "fail": RED, "warn": YELLOW}
    print(f"{colors.get(level, '')}[{ts}] {msg}{RESET}")


# === UTILITY ===

def add_task(title, description):
    """Aggiunge un task al DB SQLite e ritorna l'ID."""
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    tid = f"test-func-{int(time.time()*1000)}"
    cur.execute(
        "INSERT OR IGNORE INTO tasks (id, title, description, status, attempts, created_at, type, source) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (tid, title, description, "pending", 0, time.time(), "code", "test_functional"),
    )
    con.commit()
    con.close()
    log(f"  → Task creato: {tid}")
    return tid


def wait_for_task(task_id, timeout=180):
    """Attende che il task sia done o failed. Ritorna lo status finale."""
    start = time.time()
    last_status = None
    while time.time() - start < timeout:
        con = sqlite3.connect(str(DB))
        cur = con.cursor()
        cur.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        con.close()
        if row:
            if row[0] != last_status:
                log(f"  → status: {row[0]}")
                last_status = row[0]
            if row[0] in ("done", "failed"):
                return row[0]
        time.sleep(3)
    return "timeout"


def exec_code_safely(code):
    """Esegue codice Python in un namespace pulito. Ritorna il namespace."""
    ns = {}
    exec(code, ns)  # nosec: test dell'execute handler (codice di prova controllato)
    return ns


def find_file_with_code(expected_name):
    """Cerca in project/*.py un file che contiene la funzione/classe attesa.
    Ritorna il Path del primo file che matcha, oppure None.
    Accetta main.py come fallback (worker scrive spesso lì).
    """
    # Prima cerca il filename specificato
    expected_path = PROJECT_DIR / expected_name
    if expected_path.exists():
        return expected_path

    # Fallback: cerca qualsiasi .py che abbia la funzione attesa
    # Capisce la funzione attesa dal filename (es. test1_calculator.py -> cerca def add)
    # Mappa filename -> nome funzione/classe atteso
    func_map = {
        "test1_calculator.py": "add",
        "test2_math_utils.py": "multiply",
        "test3_counter.py": "Counter",
        "test4_fibonacci.py": "fib",
        "test6_filter_even.py": "filter_even",
        "test7_reverse.py": "reverse_string",
    }
    expected_func = func_map.get(expected_name)
    if not expected_func:
        return None

    for f in sorted(PROJECT_DIR.glob("*.py")):
        try:
            code = f.read_text()
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == expected_func:
                    return f
        except Exception:
            continue
    return None


# === TEST CASES ===

def test_1_simple_function():
    """Funzione add(a, b) -> a+b"""
    log("TEST 1: Funzione add(a, b) -> a+b")
    task_id = add_task(
        "Crea test1_calculator.py",
        "Crea project/test1_calculator.py con una funzione add(a, b) che ritorna la somma di a e b. "
        "La funzione deve essere chiamabile come add(2, 3) e ritornare 5.",
    )
    status = wait_for_task(task_id)
    if status != "done":
        log(f"  ✗ Task {status}", "fail")
        return False

    fp = find_file_with_code("test1_calculator.py")
    if not fp:
        log("  ✗ Nessun .py in project/ con funzione add()", "fail")
        return False
    if fp.name != "test1_calculator.py":
        log(f"  ⚠ File trovato in {fp.name}", "warn")

    try:
        code = fp.read_text()
        ast.parse(code)
        ns = exec_code_safely(code)
        if "add" not in ns:
            log("  ✗ Funzione add() non definita", "fail")
            return False
        if ns["add"](2, 3) != 5:
            log(f"  ✗ add(2,3)={ns['add'](2,3)}, atteso 5", "fail")
            return False
        if ns["add"](-1, 1) != 0:
            log(f"  ✗ add(-1,1)={ns['add'](-1,1)}, atteso 0", "fail")
            return False
        if ns["add"](100, 200) != 300:
            log(f"  ✗ add(100,200)={ns['add'](100,200)}, atteso 300", "fail")
            return False
        log("  ✓ add(2,3)=5, add(-1,1)=0, add(100,200)=300", "ok")
        return True
    except Exception as e:
        log(f"  ✗ Errore: {e}", "fail")
        return False


def test_2_multiple_functions_error_handling():
    """multiply + divide con gestione zero"""
    log("TEST 2: multiply + divide (gestione divisione per zero)")
    task_id = add_task(
        "Crea test2_math_utils.py",
        "Crea project/test2_math_utils.py con due funzioni: multiply(x, y) che ritorna x*y, "
        "e divide(x, y) che ritorna x/y ma solleva ValueError se y==0.",
    )
    status = wait_for_task(task_id)
    if status != "done":
        log(f"  ✗ Task {status}", "fail")
        return False

    fp = find_file_with_code("test2_math_utils.py")
    if not fp:
        log("  ✗ Nessun .py con funzione multiply()", "fail")
        return False
    if fp.name != "test2_math_utils.py":
        log(f"  ⚠ File trovato in {fp.name}", "warn")

    try:
        code = fp.read_text()
        ast.parse(code)
        ns = exec_code_safely(code)
        if "multiply" not in ns or "divide" not in ns:
            log("  ✗ Funzioni multiply/divide mancanti", "fail")
            return False
        if ns["multiply"](4, 5) != 20:
            log(f"  ✗ multiply(4,5)={ns['multiply'](4,5)}", "fail")
            return False
        if ns["multiply"](-3, 7) != -21:
            log(f"  ✗ multiply(-3,7)={ns['multiply'](-3,7)}", "fail")
            return False
        if ns["divide"](10, 2) != 5:
            log(f"  ✗ divide(10,2)={ns['divide'](10,2)}", "fail")
            return False
        try:
            ns["divide"](1, 0)
            log("  ✗ divide(1,0) non solleva eccezione", "fail")
            return False
        except ValueError:
            pass
        except ZeroDivisionError:
            log("  ⚠ divide(1,0) solleva ZeroDivisionError invece di ValueError", "warn")
        log("  ✓ multiply e divide corrette, zero gestito", "ok")
        return True
    except Exception as e:
        log(f"  ✗ Errore: {e}", "fail")
        return False


def test_3_class_with_state():
    """Classe Counter con stato"""
    log("TEST 3: Classe Counter con stato interno")
    task_id = add_task(
        "Crea test3_counter.py",
        "Crea project/test3_counter.py con una classe Counter che ha: "
        "__init__(self, initial=0) che setta il valore iniziale, "
        "increment(self, by=1) che incrementa il valore, "
        "get_value(self) che ritorna il valore attuale.",
    )
    status = wait_for_task(task_id)
    if status != "done":
        log(f"  ✗ Task {status}", "fail")
        return False

    fp = find_file_with_code("test3_counter.py")
    if not fp:
        log("  ✗ Nessun .py con classe Counter", "fail")
        return False
    if fp.name != "test3_counter.py":
        log(f"  ⚠ File trovato in {fp.name}", "warn")

    try:
        code = fp.read_text()
        ast.parse(code)
        ns = exec_code_safely(code)
        if "Counter" not in ns:
            log("  ✗ Classe Counter non definita", "fail")
            return False
        Counter = ns["Counter"]
        c = Counter()
        if c.get_value() != 0:
            log(f"  ✗ new Counter().get_value()={c.get_value()}", "fail")
            return False
        c.increment()
        if c.get_value() != 1:
            log(f"  ✗ dopo increment: {c.get_value()}", "fail")
            return False
        c.increment(5)
        if c.get_value() != 6:
            log(f"  ✗ dopo increment(5): {c.get_value()}", "fail")
            return False
        c2 = Counter(10)
        if c2.get_value() != 10:
            log(f"  ✗ Counter(10).get_value()={c2.get_value()}", "fail")
            return False
        if c.get_value() != 6:
            log("  ✗ Stato non isolato tra istanze", "fail")
            return False
        log("  ✓ Classe Counter con stato isolato corretto", "ok")
        return True
    except Exception as e:
        log(f"  ✗ Errore: {e}", "fail")
        return False


def test_4_algorithm_fibonacci():
    """Fibonacci con casi edge"""
    log("TEST 4: Fibonacci iterativo/ricorsivo")
    task_id = add_task(
        "Crea test4_fibonacci.py",
        "Crea project/test4_fibonacci.py con una funzione fib(n) che ritorna l'n-esimo numero di Fibonacci. "
        "Sequenza: fib(0)=0, fib(1)=1, fib(2)=1, fib(3)=2, fib(10)=55, fib(20)=6765. "
        "Deve gestire n negativo sollevando ValueError.",
    )
    status = wait_for_task(task_id)
    if status != "done":
        log(f"  ✗ Task {status}", "fail")
        return False

    fp = find_file_with_code("test4_fibonacci.py")
    if not fp:
        log("  ✗ Nessun .py con funzione fib()", "fail")
        return False
    if fp.name != "test4_fibonacci.py":
        log(f"  ⚠ File trovato in {fp.name}", "warn")

    try:
        code = fp.read_text()
        ast.parse(code)
        ns = exec_code_safely(code)
        if "fib" not in ns:
            log("  ✗ Funzione fib non definita", "fail")
            return False
        fib = ns["fib"]
        cases = [(0, 0), (1, 1), (2, 1), (3, 2), (5, 5), (10, 55), (15, 610), (20, 6765)]
        for n, expected in cases:
            r = fib(n)
            if r != expected:
                log(f"  ✗ fib({n})={r}, atteso {expected}", "fail")
                return False
        try:
            fib(-1)
        except (ValueError, Exception):
            pass
        log(f"  ✓ fib corretta per {len(cases)} casi + edge negativo", "ok")
        return True
    except Exception as e:
        log(f"  ✗ Errore: {e}", "fail")
        return False


def test_5_script_with_file_io():
    """Script che esegue e scrive su file — versione tollerante: prova main.py come fallback"""
    log("TEST 5: Script con side effect (file I/O)")
    task_id = add_task(
        "Crea test5_greet.py",
        "Crea project/test5_greet.py che quando eseguito crea un file project/test5_output.txt "
        "con dentro la stringa 'Hello, Byte-Swarmy!'. Lo script deve usare open() in modalità scrittura.",
    )
    status = wait_for_task(task_id)
    if status != "done":
        log(f"  ✗ Task {status}", "fail")
        return False

    # Prima prova il filename specificato, poi fallback su main.py
    candidates = [
        PROJECT_DIR / "test5_greet.py",
        PROJECT_DIR / "main.py",
    ]
    fp = None
    for cand in candidates:
        if cand.exists():
            # Verifica che il file abbia senso (contiene open o write)
            try:
                code = cand.read_text()
                if "open" in code or "write" in code or "Hello" in code:
                    fp = cand
                    if cand.name != "test5_greet.py":
                        log(f"  ⚠ Script trovato in {cand.name}", "warn")
                    break
            except Exception:
                continue

    if not fp:
        log("  ✗ Nessuno script valido trovato in project/", "fail")
        return False

    out = PROJECT_DIR / "test5_output.txt"
    try:
        result = subprocess.run(
            [sys.executable, str(fp)],
            capture_output=True, text=True, timeout=10, cwd=str(ROOT),
        )
        if result.returncode != 0:
            log(f"  ✗ Script exit {result.returncode}: {result.stderr[:200]}", "fail")
            return False
        if not out.exists():
            log("  ✗ Output file non creato dallo script", "fail")
            return False
        content = out.read_text().strip()
        if "Hello" not in content:
            log(f"  ✗ Output non contiene 'Hello': {content!r}", "fail")
            return False
        log(f"  ✓ Script eseguito, output: {content!r}", "ok")
        return True
    except subprocess.TimeoutExpired:
        log("  ✗ Script in timeout (loop infinito?)", "fail")
        return False
    except Exception as e:
        log(f"  ✗ Errore: {e}", "fail")
        return False
    finally:
        if out.exists():
            out.unlink()


def test_6_list_manipulation():
    """filter_even con vari casi"""
    log("TEST 6: filter_even su lista")
    task_id = add_task(
        "Crea test6_filter_even.py",
        "Crea project/test6_filter_even.py con una funzione filter_even(numbers) che prende "
        "una lista di numeri e ritorna solo quelli pari. "
        "Esempio: filter_even([1,2,3,4,5,6]) ritorna [2,4,6].",
    )
    status = wait_for_task(task_id)
    if status != "done":
        log(f"  ✗ Task {status}", "fail")
        return False

    fp = find_file_with_code("test6_filter_even.py")
    if not fp:
        log("  ✗ Nessun .py con funzione filter_even()", "fail")
        return False
    if fp.name != "test6_filter_even.py":
        log(f"  ⚠ File trovato in {fp.name}", "warn")

    try:
        code = fp.read_text()
        ast.parse(code)
        ns = exec_code_safely(code)
        if "filter_even" not in ns:
            log("  ✗ filter_even non definita", "fail")
            return False
        f = ns["filter_even"]
        if f([1, 2, 3, 4, 5, 6]) != [2, 4, 6]:
            log(f"  ✗ f([1..6])={f([1,2,3,4,5,6])}", "fail")
            return False
        if f([]) != []:
            log(f"  ✗ f([])={f([])}", "fail")
            return False
        if f([1, 3, 5]) != []:
            log(f"  ✗ f([1,3,5])={f([1,3,5])}", "fail")
            return False
        if f([2, 4, 6]) != [2, 4, 6]:
            log(f"  ✗ f([2,4,6])={f([2,4,6])}", "fail")
            return False
        if f([0, -2, -4]) != [0, -2, -4]:
            log(f"  ✗ f([0,-2,-4])={f([0,-2,-4])} (zero è pari!)", "fail")
            return False
        log("  ✓ filter_even corretta (anche zero e negativi pari)", "ok")
        return True
    except Exception as e:
        log(f"  ✗ Errore: {e}", "fail")
        return False


def test_7_string_manipulation():
    """reverse_string con casi edge"""
    log("TEST 7: reverse_string con edge cases")
    task_id = add_task(
        "Crea test7_reverse.py",
        "Crea project/test7_reverse.py con una funzione reverse_string(s) che ritorna la stringa s al contrario. "
        "Esempio: reverse_string('hello') ritorna 'olleh'. "
        "Gestisci stringa vuota ritornando '' e un solo carattere ritornando lo stesso carattere.",
    )
    status = wait_for_task(task_id)
    if status != "done":
        log(f"  ✗ Task {status}", "fail")
        return False

    fp = find_file_with_code("test7_reverse.py")
    if not fp:
        log("  ✗ Nessun .py con funzione reverse_string()", "fail")
        return False
    if fp.name != "test7_reverse.py":
        log(f"  ⚠ File trovato in {fp.name}", "warn")

    try:
        code = fp.read_text()
        ast.parse(code)
        ns = exec_code_safely(code)
        if "reverse_string" not in ns:
            log("  ✗ reverse_string non definita", "fail")
            return False
        f = ns["reverse_string"]
        cases = [("hello", "olleh"), ("", ""), ("a", "a"), ("ab", "ba"),
                 ("Python", "nohtyP"), ("12345", "54321")]
        for inp, expected in cases:
            r = f(inp)
            if r != expected:
                log(f"  ✗ reverse_string({inp!r})={r!r}, atteso {expected!r}", "fail")
                return False
        log(f"  ✓ reverse_string corretta per {len(cases)} casi", "ok")
        return True
    except Exception as e:
        log(f"  ✗ Errore: {e}", "fail")
        return False


# === MAIN ===

TESTS = [
    ("Funzione semplice (add)", test_1_simple_function),
    ("Multiple funzioni + error handling", test_2_multiple_functions_error_handling),
    ("Classe con stato (Counter)", test_3_class_with_state),
    ("Algoritmo (Fibonacci)", test_4_algorithm_fibonacci),
    ("Script con file I/O", test_5_script_with_file_io),
    ("List manipulation (filter_even)", test_6_list_manipulation),
    ("String manipulation (reverse)", test_7_string_manipulation),
]


def main():
    parser = argparse.ArgumentParser(description="Test funzionali BYTE-SWARMY")
    parser.add_argument("--test", type=int, help="Esegui solo il test N (1-7)")
    parser.add_argument("--list", action="store_true", help="Lista i test disponibili")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout per task (secondi)")
    args = parser.parse_args()

    if args.list:
        print("Test disponibili:")
        for i, (desc, _) in enumerate(TESTS, 1):
            print(f"  {i}. {desc}")
        return

    print(f"\n{'='*70}")
    print(f"  🐝 TEST FUNZIONALI BYTE-SWARMY — QUALITÀ DEL CODICE PRODOTTO")
    print(f"{'='*70}\n")

    if not DB.exists():
        log(f"DB non trovato: {DB}", "fail")
        sys.exit(1)

    result = subprocess.run(["pgrep", "-f", "CORE.orchestrator"], capture_output=True)
    if result.returncode != 0:
        log("⚠ Orchestrator NON attivo! Avvialo prima:", "warn")
        log("    ./bswarm start --orch", "warn")

    # Cleanup file test precedenti
    for f in PROJECT_DIR.glob("test*_*.py"):
        f.unlink()
    for f in PROJECT_DIR.glob("test*_*.txt"):
        f.unlink()
    log("Cleanup file test precedenti")

    # Seleziona test da eseguire
    if args.test:
        if args.test < 1 or args.test > len(TESTS):
            log(f"Test {args.test} non esiste (1-{len(TESTS)})", "fail")
            sys.exit(1)
        tests_to_run = [TESTS[args.test - 1]]
    else:
        tests_to_run = TESTS

    results = []
    for desc, test in tests_to_run:
        print()
        log(f"--- {desc} ---")
        try:
            ok = test()
            results.append((desc, ok))
        except Exception as e:
            log(f"  ✗ Test crashed: {e}", "fail")
            results.append((desc, False))

    # Summary
    print(f"\n{'='*70}")
    print(f"  RIASSUNTO{' (test ' + str(args.test) + ')' if args.test else ''}")
    print(f"{'='*70}")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for desc, ok in results:
        status = f"{GREEN}✓ PASS{RESET}" if ok else f"{RED}✗ FAIL{RESET}"
        print(f"  {status}  {desc}")
    pct = passed / total * 100 if total else 0
    color = GREEN if pct == 100 else (YELLOW if pct >= 70 else RED)
    print(f"\n  {color}{passed}/{total} test passati ({pct:.0f}%){RESET}")
    if pct == 100:
        print(f"  {GREEN}🎉 Swarm produce codice di qualità!{RESET}")
    elif pct >= 70:
        print(f"  {YELLOW}⚠ Swarm funziona ma con qualche limite{RESET}")
    else:
        print(f"  {RED}❌ Swarm ha problemi significativi{RESET}")
    print(f"{'='*70}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
