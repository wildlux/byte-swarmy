"""
ast_scanner.py — Deterministic Security Validator
Analizza il codice Python prima dell'esecuzione utilizzando l'Abstract Syntax Tree (AST).
Blocca l'uso di funzioni pericolose indipendentemente dall'offuscamento del codice.
"""

from __future__ import annotations
import ast
import re
from typing import Tuple, List, Set

# Firma degli artefatti di escape la causa i crash loops del 27/10/2026:
# riga che INIZIA con un backslash-virgoetta (\\" o \\') fuori da qualunque
# stringa. In Python valido questo non e mai possibile al inizio riga.
_ARTIFACT_RE = re.compile(r"(?m)^[ \t]*\\[\"']")

_ARTIFACT_HINT = (
    "The text contains escape artifacts (e.g. \\\" or \\\\n written as "
        "literal characters at line start). Do NOT use backslashes to quote "
        "strings: use plain `\\\"`. Do NOT use patch_code to fix it: rewrite "
        "the whole clean file with write_file."
)

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
            if _ARTIFACT_RE.search(code):
                return False, (
                    f"Syntax error at line {e.lineno}. {_ARTIFACT_HINT}"
                )
            return False, f"Syntax error in code: {e}"

        # Mappa alias per battere l'offuscamento degli import:
        #   import os as o            → "o" → "os"
        #   from subprocess import Popen as P → "P" → "subprocess.Popen"
        aliases: dict = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias_spec in node.names:
                    if alias_spec.asname:
                        head = alias_spec.name.split(".")[0]
                        aliases[alias_spec.asname] = head
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias_spec in node.names:
                    if getattr(alias_spec, "name", None) == "*":
                        continue
                    # from subprocess import Popen → "Popen" → "subprocess.Popen"
                    full = f"{node.module}.{alias_spec.name}"
                    key = alias_spec.asname or alias_spec.name
                    banned = self._resolve_banned_suffix(full)
                    if banned:
                        aliases[key] = full

        for node in ast.walk(tree):
            # 1. Controllo chiamate a funzioni (Call nodes)
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node.func, aliases)
                if (func_name in self.BANNED_FUNCTIONS
                        or func_name.split(".")[-1] in self.BANNED_FUNCTIONS):
                    self.violations.append(f"Forbidden call to {func_name}")

            # 2. Controllo import (Import & ImportFrom nodes)
            if isinstance(node, ast.Import):
                for alias_spec in node.names:
                    if alias_spec.name.split('.')[0] in self.BANNED_MODULES:
                        self.violations.append(f"Forbidden import of module {alias_spec.name}")

            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in self.BANNED_MODULES:
                    self.violations.append(f"Forbidden import from module {node.module}")

        if self.violations:
            return False, "; ".join(self.violations)

        return True, ""

    def _resolve_banned_suffix(self, dotted: str) -> str:
        """Se 'dotted' termina su una firma vietata, ritorna la firma vietata
        canonica. Es: 'from subprocess import call' → 'subprocess.call'.
        Serve a mappare i from-import delle funzioni vietate."""
        parts = dotted.split(".")
        for i in range(len(parts)):
            tail = ".".join(parts[i:])
            if tail in self.BANNED_FUNCTIONS:
                return tail
        return ""

    def _get_func_name(self, node, aliases: dict = None) -> str:
        """Estrae il nome della funzione da un nodo AST (gestisce chiamate
        dirette e attribute). Risolve gli alias import via alias map."""
        if aliases is None:
            aliases = {}
        if isinstance(node, ast.Name):
            name = node.id
            return aliases.get(name, name)
        elif isinstance(node, ast.Attribute):
            # Gestisce casi come os.system o subprocess.run
            if isinstance(node.value, ast.Name):
                base = aliases.get(node.value.id, node.value.id)
                return f"{base}.{node.attr}"
            # Gestisce chiamate annidate (es. a.b.c())
            return f"{self._get_func_name(node.value, aliases)}.{node.attr}"
        return "unknown"

# Singleton per l'uso globale
scanner = ASTSecurityScanner()

def detect_artifacts(code: str) -> bool:
    """True se il testo contiene artefatti di escape fuori da contesto valido."""
    return bool(_ARTIFACT_RE.search(code))
