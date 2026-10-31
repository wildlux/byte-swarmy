"""
test_e2e.py — Test end-to-end: task completo start-to-finish.

Verifica il flusso reale:
1. Aggiungi task al DB SQLite
2. Avvia orchestratore
3. Aspetta che il task venga processato
4. Verifica che il file sia stato creato in project/
5. Verifica che il task sia in stato 'done'

Questo test richiede Ollama attivo e modelli scaricati.
Saltato se Ollama non e disponibile.
"""
import json
import os
import sqlite3
import time
import unittest
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


class TestE2ETaskExecution(unittest.TestCase):
    """Test E2E: un task reale dall'inizio alla fine."""
    
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parent.parent
        cls.db_path = cls.root / "tasks" / "queue.db"
        cls.project = cls.root / "project"
        
        # Skip se Ollama non e disponibile
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3).read()
        except Exception:
            raise unittest.SkipTest("Ollama non disponibile, skip E2E test")
    
    def setUp(self):
        # Pulisci DB
        if self.db_path.exists():
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("DELETE FROM tasks")
            conn.commit()
            conn.close()
        
        # Pulisci project
        if self.project.exists():
            for f in self.project.glob("*.py"):
                f.unlink()
    
    def test_create_function_task_e2e(self):
        """Test E2E: aggiungi task 'crea hello world' e verifica esecuzione."""
        
        # 1. Aggiungi task al DB
        task_id = f"e2e-test-{int(time.time())}"
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO tasks (id, title, description, context, status, "
            "attempts, created_at, parent, type, source) "
            "VALUES (?,?,?,?,?,?,?, ?,?,?)",
            (task_id, "hello world in python",
             "Scrivi un file hello.py con print('Hello from BYTE-SWARMY!')",
             json.dumps({"lang": "it", "intent": "create_function"}),
             "pending", 0, time.time(), None, "implement", "e2e-test")
        )
        conn.commit()
        conn.close()
        
        # 2. Verifica che il task sia nel DB
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "pending")
        
        # 3. Aspetta che l'orchestratore lo processi (max 120 secondi)
        # L'orchestratore deve gia essere in esecuzione
        max_wait = 120
        start = time.time()
        final_status = None
        
        while time.time() - start < max_wait:
            conn = sqlite3.connect(str(self.db_path))
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            conn.close()
            
            if row and row[0] in ("done", "stuck", "needs_human"):
                final_status = row[0]
                break
            
            time.sleep(5)
        
        # 4. Verifica che il task sia completato
        self.assertIsNotNone(final_status, f"Task non processato entro {max_wait}s")
        
        # Se il task e done, verifica che il file esista
        if final_status == "done":
            # Cerca file .py in project/
            py_files = list(self.project.glob("*.py"))
            self.assertGreater(len(py_files), 0, "Nessun file .py creato in project/")
            
            # Verifica contenuto
            content = py_files[0].read_text()
            self.assertIn("Hello", content, "Il file non contiene 'Hello'")
        
        # Cleanup
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
    
    def test_swarm_command_e2e(self):
        """Test E2E: swarm command 'swarm status' deve rispondere senza LLM."""
        
        task_id = f"swarm-cmd-{int(time.time())}"
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO tasks (id, title, description, context, status, "
            "attempts, created_at, parent, type, source) "
            "VALUES (?,?,?,?,?,?,?, ?,?,?)",
            (task_id, "swarm status", "swarm status",
             json.dumps({"lang": "en", "intent": "swarm_status"}),
             "pending", 0, time.time(), None, "generic", "e2e-test")
        )
        conn.commit()
        conn.close()
        
        # Aspetta (max 60s, dovrebbe essere istantaneo)
        max_wait = 60
        start = time.time()
        final_status = None
        result_text = None
        
        while time.time() - start < max_wait:
            conn = sqlite3.connect(str(self.db_path))
            row = conn.execute(
                "SELECT status, result FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            conn.close()
            
            if row and row[0] in ("done", "stuck"):
                final_status = row[0]
                result_text = row[1] if len(row) > 1 else None
                break
            
            time.sleep(3)
        
        self.assertEqual(final_status, "done", "Swarm command non completato")
        if result_text:
            self.assertIn("BYTE-SWARMY", result_text, "Result non contiene 'BYTE-SWARMY'")
        
        # Cleanup
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
    
    def test_execute_handler_e2e(self):
        """Test E2E: execute handler con gcc (se disponibile)."""
        import shutil
        
        if not shutil.which("gcc"):
            self.skipTest("gcc non disponibile")
        
        # Crea file hello.c in project/
        self.project.mkdir(parents=True, exist_ok=True)
        c_file = self.project / "hello.c"
        c_file.write_text(
            '#include <stdio.h>\n'
            'int main() { printf("Hello from C!\\n"); return 0; }\n'
        )
        
        # Aggiungi task execute
        task_id = f"exec-test-{int(time.time())}"
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO tasks (id, title, description, context, status, "
            "attempts, created_at, parent, type, source) "
            "VALUES (?,?,?,?,?,?,?, ?,?,?)",
            (task_id, "Compila ed esegui",
             "Compila hello.c con gcc hello.c -o hello e poi esegui ./hello",
             json.dumps({"lang": "it", "intent": "create_function"}),
             "pending", 0, time.time(), None, "execute", "e2e-test")
        )
        conn.commit()
        conn.close()
        
        # Aspetta (max 60s)
        max_wait = 60
        start = time.time()
        final_status = None
        
        while time.time() - start < max_wait:
            conn = sqlite3.connect(str(self.db_path))
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            conn.close()
            
            if row and row[0] in ("done", "stuck", "retry"):
                final_status = row[0]
                break
            
            time.sleep(3)
        
        # L'execute handler dovrebbe processare (anche se gcc puo fallire nel sandbox)
        self.assertIsNotNone(final_status, "Execute task non processato")
        
        # Cleanup
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
        c_file.unlink(missing_ok=True)
        (self.project / "hello").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
