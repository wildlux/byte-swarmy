"""
ast_scanner.py — Deterministic Security Validator
Analizza il codice Python prima dell'esecuzione utilizzando l'Abstract Syntax Tree (AST).
Blocca l'uso di funzioni pericolose indipendentemente dall'offuscamento del codice.
"""

from __future__ import annotations
import ast
from typing import Tuple, List, Set

class ASTSecurityScanner:
    """
    Scanner di sicurezza deterministico. 
    Analizza il codice sorgente per identificare chiamate a funzioni vietate.
    """

    # Funzioni assolutamente vietate
    BANNED_FUNCTIONS = {
        "eval", "exec", "compile", "getattr", "setattr", 
        "__import__", "importlib.import_module", "os.system", 
        "os.popen", "subprocess.Popen", "subprocess.call", 
        "subprocess.run", "subprocess.check_output", "subprocess.check_call",
        "shutil.rmtree", "os.remove", "os.unlink", "os.rmdir"
    }

    # Moduli che richiedono particolare attenzione o sono vietati
    BANNED_MODULES = {
        "ctypes", "pickle", "shelve", "marshal", "socket"
    }

    def __init__(self):
        self.violations: List[str] = []

    def scan(self, code: str) -> Tuple[bool, str]:
        """
        Analizza il codice e ritorna (True, "") se sicuro, 
        oppure (False, "motivo") se viene rilevata una violazione.
        """
        self.violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Errore di sintassi nel codice: {e}"

        for node in ast.walk(tree):
            # 1. Controllo chiamate a funzioni (Call nodes)
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node.func)
                if func_name in self.BANNED_FUNCTIONS:
                    self.violations.append(f"Chiamata vietata a {func_name}")

            # 2. Controllo import (Import & ImportFrom nodes)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in self.BANNED_MODULES:
                        self.violations.append(f"Importazione vietata del modulo {alias.name}")

            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in self.BANNED_MODULES:
                    self.violations.append(f"Importazione vietata dal modulo {node.module}")

        if self.violations:
            return False, "; ".join(self.violations)
        
        return True, ""

    def _get_func_name(self, node) -> str:
        """Estrae il nome della funzione da un nodo AST (gestisce chiamate dirette e attribute)."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Gestisce casi come os.system o subprocess.run
            if isinstance(node.value, ast.Name):
                return f"{node.value.id}.{node.attr}"
            # Gestisce chiamate annidate (es. a.b.c())
            return f"{self._get_func_name(node.value)}.{node.attr}"
        return "unknown"

# Singleton per l'uso globale
scanner = ASTSecurityScanner()
