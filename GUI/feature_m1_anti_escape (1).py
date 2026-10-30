#!/usr/bin/env python3
"""
feature_m1_anti_escape.py — Guardrail anti-escape in write_file/patch_code.

Cosa fa:
1. Aggiunge detect_escape_artifacts() a CORE/ast_scanner.py
   - Per .py: ast.parse() + check pattern sospetti
   - Per .json: json.loads()
   - Per altri: regex check leggero
2. Patcha CORE/tools.py per chiamare il check in write_file e patch_code
3. Aggiunge test in tests/test_security.py

Artefatti rilevati:
- \\" letterale fuori da stringhe (broken escape)
- \\n letterale in codice Python (should be real newline)
- // in Python fuori da commenti (C-style comment injection)
- \\ a fine riga non da continuazione legittima
- Stringhe non bilanciate (odd quote count)
- Blocchi duplicati (same line appears 3+ times consecutively)
"""
import re
import shutil
from pathlib import Path

SCANNER_FILE = Path("CORE/ast_scanner.py")
SCANNER_BACKUP = Path("CORE/ast_scanner.py.bak.anti_escape")
TOOLS_FILE = Path("CORE/tools.py")
TOOLS_BACKUP = Path("CORE/tools.py.bak.anti_escape")
TEST_FILE = Path("tests/test_security.py")
TEST_BACKUP = Path("tests/test_security.py.bak.anti_escape")


# ====================================================================
# Codice da aggiungere a CORE/ast_scanner.py
# ====================================================================

ANTI_ESCAPE_CODE = '''

# ====================================================================
# Anti-escape artifact detection (M1)
# ====================================================================

# Pattern di artefatti di escape generati dall'AI
_ESCAPE_PATTERNS = [
    # \\" letterale fuori da stringhe Python (broken escape)
    # Matcha \\" ma non dentro stringhe già valide
    (re.compile(r'\\\\"'), 'literal \\\\" escape artifact (broken string)'),
    
    # \\n letterale in codice Python (should be real newline)
    # Solo se la riga sembra codice Python (non una stringa doc)
    (re.compile(r'(?<!["\\'])\\\\n(?!["\\'])'), 'literal \\\\n in code (should be newline)'),
    
    # \\t letterale in codice Python
    (re.compile(r'(?<!["\\'])\\\\t(?!["\\'])'), 'literal \\\\t in code (should be tab)'),
    
    # // in Python fuori da commenti/stringhe (C-style comment injection)
    # Matcha // ma non dopo # (commento Python) e non in stringhe
    (re.compile(r'(?<!["\\\'#])//(?!=)'), 'C-style // comment in Python code'),
    
    # Sequenza sospetta: backslash seguito da carattere non standard
    # (es. \\x, \\z — non escape Python validi come \\n, \\t, \\\\, \\')
    (re.compile(r'\\\\[xyzXYZ]'), 'suspicious backslash escape (\\\\x/\\\\z)'),
]


def detect_escape_artifacts(content: str, filename: str = "") -> list:
    """Rileva artefatti di escape nel contenuto di un file.
    
    Args:
        content: il testo del file da controllare
        filename: nome del file (per scegliere la strategia di check)
    
    Returns:
        Lista di dict con {line, pattern, description} per ogni artefatto trovato.
        Lista vuota = nessun artefatto, file OK.
    """
    if not content:
        return []
    
    artifacts = []
    ext = Path(filename).suffix.lower() if filename else ""
    
    # === Per file Python: check AST + pattern ===
    if ext == ".py":
        # 1. Try AST parse — se fallisce, è corrotto
        try:
            ast.parse(content)
        except SyntaxError as e:
            artifacts.append({
                "line": e.lineno or 0,
                "pattern": "syntax_error",
                "description": f"Python syntax error: {e.msg}",
            })
            # Se c'è syntax error, continua comunque con i pattern check
        
        # 2. Check pattern sospetti
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Skip commenti e stringhe doc
            stripped = line.lstrip()
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            
            for pattern, description in _ESCAPE_PATTERNS:
                if pattern.search(line):
                    artifacts.append({
                        "line": i,
                        "pattern": pattern.pattern,
                        "description": description,
                        "context": line.strip()[:100],
                    })
        
        # 3. Check stringhe non bilanciate (odd quote count per riga)
        for i, line in enumerate(lines, 1):
            # Count quotes non escaped
            clean = re.sub(r'\\.', '', line)  # remove escaped chars
            # Count " not part of """ or """""
            double_quotes = len(re.findall(r'(?<!")"(?!")', clean))
            if double_quotes % 2 != 0:
                # Could be legit (multiline string), but flag if not starting/ending with """
                if not (stripped.startswith('"""') or stripped.endswith('"""')):
                    artifacts.append({
                        "line": i,
                        "pattern": "unbalanced_quotes",
                        "description": "odd number of unescaped quotes (broken string)",
                        "context": line.strip()[:100],
                    })
        
        # 4. Check blocchi duplicati (3+ righe identiche consecutive)
        consecutive_count = 1
        for i in range(1, len(lines)):
            if lines[i].strip() and lines[i] == lines[i-1]:
                consecutive_count += 1
                if consecutive_count >= 3:
                    artifacts.append({
                        "line": i + 1,
                        "pattern": "duplicated_block",
                        "description": f"line duplicated {consecutive_count} times consecutively",
                        "context": lines[i].strip()[:100],
                    })
            else:
                consecutive_count = 1
    
    # === Per file JSON: check parse ===
    elif ext == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            artifacts.append({
                "line": e.lineno or 0,
                "pattern": "json_error",
                "description": f"JSON parse error: {e.msg}",
            })
    
    # === Per altri file: check leggero ===
    else:
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Check solo \\" letterale (il bug più comune)
            if '\\"' in line and ext not in ('.md', '.txt', '.rst'):
                # In file non-text, \\" è sospetto
                artifacts.append({
                    "line": i,
                    "pattern": "literal_backslash_quote",
                    "description": 'literal \\" in non-text file',
                    "context": line.strip()[:100],
                })
    
    return artifacts


def check_no_escape_artifacts(content: str, filename: str = "") -> tuple:
    """Check che ritorna (ok, error_msg).
    
    Usage:
        ok, msg = check_no_escape_artifacts(content, "main.py")
        if not ok:
            return f"ERROR: {msg}"
    """
    artifacts = detect_escape_artifacts(content, filename)
    if not artifacts:
        return (True, "")
    
    # Formatta errore
    lines = [f"Anti-escape guardrail: {len(artifacts)} artifact(s) detected in {filename}:"]
    for a in artifacts[:5]:  # max 5 nel messaggio
        ctx = a.get("context", "")
        lines.append(f"  line {a['line']}: {a['description']}" + (f" | {ctx}" if ctx else ""))
    if len(artifacts) > 5:
        lines.append(f"  ... and {len(artifacts) - 5} more")
    lines.append("Fix the escape artifacts before writing the file.")
    
    return (False, "\n".join(lines))
'''


# ====================================================================
# Patch CORE/tools.py: chiama il check in write_file e patch_code
# ====================================================================

# In write_file: dopo il check AST esistente, aggiungi il check anti-escape
TOOLS_WRITE_OLD = '''            # AST security scan on Python files
            if path.endswith(".py"):
                from CORE.ast_scanner import scan_code
                issues = scan_code(content)
                if issues:
                    self._audit("blocked_ast", f'op=write_file path="{self._q(path)}" issues="{len(issues)}"',
                                "WARNING")
                    return f"ERROR: AST scan blocked write: {'; '.join(issues[:3])}"'''

TOOLS_WRITE_NEW = '''            # AST security scan on Python files
            if path.endswith(".py"):
                from CORE.ast_scanner import scan_code
                issues = scan_code(content)
                if issues:
                    self._audit("blocked_ast", f'op=write_file path="{self._q(path)}" issues="{len(issues)}"',
                                "WARNING")
                    return f"ERROR: AST scan blocked write: {'; '.join(issues[:3])}"
            
            # 🆕 M1: Anti-escape artifact check
            from CORE.ast_scanner import check_no_escape_artifacts
            ok, msg = check_no_escape_artifacts(content, path)
            if not ok:
                self._audit("blocked_escape", f'op=write_file path="{self._q(path)}"',
                            "WARNING")
                return f"ERROR: {msg}"'''


# In patch_code: check il nuovo contenuto prima di applicare
TOOLS_PATCH_OLD = '''    def patch_code(self, path: str, old_text: str, new_text: str) -> str:
        """Sostituisce una porzione di testo in un file con validazione AST."""
        try:
            full = safe_project_path(path, self.project_root)
        except SecurityError as exc:
            return f"ERROR: {exc}"'''

TOOLS_PATCH_NEW = '''    def patch_code(self, path: str, old_text: str, new_text: str) -> str:
        """Sostituisce una porzione di testo in un file con validazione AST."""
        try:
            full = safe_project_path(path, self.project_root)
        except SecurityError as exc:
            return f"ERROR: {exc}"
        
        # 🆕 M1: Anti-escape artifact check on new_text
        from CORE.ast_scanner import check_no_escape_artifacts
        ok, msg = check_no_escape_artifacts(new_text, path)
        if not ok:
            self._audit("blocked_escape", f'op=patch_code path="{self._q(path)}"',
                        "WARNING")
            return f"ERROR: {msg}"'''


# ====================================================================
# Test da aggiungere a tests/test_security.py
# ====================================================================

TEST_CODE = '''

class TestAntiEscapeGuardrail(unittest.TestCase):
    """M1: Anti-escape artifact detection in write_file/patch_code."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-escape-"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        (self.tmp / "state").mkdir()
        self.cfg = {
            "paths": {
                "project_root": str(self.project),
                "state_dir": str(self.tmp / "state"),
            },
            "routing": {
                "max_file_size_readable": 50_000,
                "timeout_bash": 2,
            },
            "security": {
                "enabled": True,
                "max_output_chars": 500,
                "max_file_size_write": 10_000,
                "max_file_size_bytes": 1_000_000,
                "max_memory_mb": 512,
            },
        }
        logger = logging.getLogger(f"escape-{id(self)}")
        logger.addHandler(logging.NullHandler())
        self.tools = ToolSet(self.cfg, logger)
        self.tools.set_worker("escape-test")
    
    def test_clean_python_passes(self):
        """Codice Python pulito passa senza errori."""
        result = self.tools.write_file("clean.py", "def hello():\n    print('hi')\n")
        self.assertTrue(result.startswith("OK:"), result)
    
    def test_literal_backslash_quote_blocked(self):
        """\\" letterale in Python viene bloccato."""
        # Questo è l'artefatto più comune generato dall'AI
        bad_code = 'x = \\"hello\\"\nprint(x)\n'
        result = self.tools.write_file("bad.py", bad_code)
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("escape", result.lower())
    
    def test_c_style_comment_in_python_blocked(self):
        """// comment in Python viene bloccato."""
        bad_code = "x = 1\n// this is a C comment\nprint(x)\n"
        result = self.tools.write_file("bad2.py", bad_code)
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_syntax_error_blocked(self):
        """Python con syntax error viene bloccato."""
        bad_code = "def broken(:\n    pass\n"
        result = self.tools.write_file("broken.py", bad_code)
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("syntax", result.lower())
    
    def test_duplicated_lines_blocked(self):
        """3+ righe identiche consecutive vengono bloccate."""
        bad_code = "x = 1\nx = 1\nx = 1\nx = 1\nprint(x)\n"
        result = self.tools.write_file("dup.py", bad_code)
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("duplicat", result.lower())
    
    def test_patch_code_with_escape_blocked(self):
        """patch_code con new_text contenente escape viene bloccato."""
        # Prima scrivi un file pulito
        self.tools.write_file("target.py", "x = 1\n")
        # Ora prova a patchare con escape artifact
        result = self.tools.patch_code("target.py", "x = 1", 'x = \\"bad\\"\n')
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("escape", result.lower())
    
    def test_json_with_escape_blocked(self):
        """JSON malformato viene bloccato."""
        bad_json = '{"key": \\"value"}\n'
        result = self.tools.write_file("bad.json", bad_json)
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_markdown_with_backslash_passes(self):
        """Markdown può contenere \\" legitimamente."""
        md = '# Title\n\nHe said \\"hello\\" to her.\n'
        result = self.tools.write_file("doc.md", md)
        self.assertTrue(result.startswith("OK:"), result)
'''


def main():
    print("=" * 60)
    print("M1: ANTI-ESCAPE GUARDRAIL")
    print("=" * 60)
    print()
    
    # 1. Patch ast_scanner.py
    print("→ Patch CORE/ast_scanner.py")
    if not SCANNER_FILE.exists():
        print(f"  ❌ {SCANNER_FILE} non trovato")
        return 1
    
    content = SCANNER_FILE.read_text()
    if "detect_escape_artifacts" in content:
        print("  ℹ  già presente, skip")
    else:
        shutil.copy2(SCANNER_FILE, SCANNER_BACKUP)
        # Verifica che ast e re siano importati
        if "import ast" not in content:
            content = "import ast\n" + content
        if "import re" not in content:
            content = "import re\n" + content
        if "import json" not in content:
            content = "import json\n" + content
        
        content = content.rstrip() + "\n" + ANTI_ESCAPE_CODE
        SCANNER_FILE.write_text(content)
        
        try:
            compile(content, "ast_scanner.py", "exec")
            print("  ✓ Aggiunte detect_escape_artifacts() e check_no_escape_artifacts()")
        except SyntaxError as e:
            print(f"  ❌ Errore sintassi: {e}")
            shutil.copy2(SCANNER_BACKUP, SCANNER_FILE)
            return 1
    
    # 2. Patch tools.py
    print()
    print("→ Patch CORE/tools.py")
    if not TOOLS_FILE.exists():
        print(f"  ❌ {TOOLS_FILE} non trovato")
        return 1
    
    content = TOOLS_FILE.read_text()
    if "blocked_escape" in content:
        print("  ℹ  già patchato, skip")
    else:
        shutil.copy2(TOOLS_FILE, TOOLS_BACKUP)
        modified = False
        
        if TOOLS_WRITE_OLD in content:
            content = content.replace(TOOLS_WRITE_OLD, TOOLS_WRITE_NEW, 1)
            modified = True
            print("  ✓ write_file chiama check_no_escape_artifacts()")
        else:
            print("  ⚠  Pattern write_file non trovato (potrebbe essere diverso)")
        
        if TOOLS_PATCH_OLD in content:
            content = content.replace(TOOLS_PATCH_OLD, TOOLS_PATCH_NEW, 1)
            modified = True
            print("  ✓ patch_code chiama check_no_escape_artifacts()")
        else:
            print("  ⚠  Pattern patch_code non trovato (potrebbe essere diverso)")
        
        if modified:
            TOOLS_FILE.write_text(content)
            try:
                compile(content, "tools.py", "exec")
                print("  ✓ Verifica sintassi OK")
            except SyntaxError as e:
                print(f"  ❌ Errore sintassi: {e}")
                shutil.copy2(TOOLS_BACKUP, TOOLS_FILE)
                return 1
    
    # 3. Aggiungi test
    print()
    print("→ Patch tests/test_security.py")
    if not TEST_FILE.exists():
        print(f"  ❌ {TEST_FILE} non trovato")
    else:
        content = TEST_FILE.read_text()
        if "TestAntiEscapeGuardrail" in content:
            print("  ℹ  già presente, skip")
        else:
            shutil.copy2(TEST_FILE, TEST_BACKUP)
            # Inserisci prima di "if __name__"
            insert_point = "if __name__ == \"__main__\":"
            if insert_point in content:
                content = content.replace(insert_point, TEST_CODE + "\n\n" + insert_point, 1)
                TEST_FILE.write_text(content)
                try:
                    compile(content, "test_security.py", "exec")
                    print("  ✓ Aggiunti 7 test anti-escape")
                except SyntaxError as e:
                    print(f"  ❌ Errore sintassi: {e}")
                    shutil.copy2(TEST_BACKUP, TEST_FILE)
            else:
                print("  ⚠  Punto inserimento non trovato, aggiungo in fondo")
                content = content.rstrip() + "\n" + TEST_CODE
                TEST_FILE.write_text(content)
    
    print()
    print("=" * 60)
    print("✓ M1 COMPLETATO")
    print("=" * 60)
    print()
    print("Cosa cambia:")
    print("  - write_file: blocca file con artefatti di escape")
    print("  - patch_code: blocca new_text con artefatti di escape")
    print("  - 7 nuovi test verificano il guardrail")
    print()
    print("Artefatti rilevati:")
    print("  - \\\" letterale in Python (broken string)")
    print("  - \\\\n letterale in codice (should be newline)")
    print("  - // C-style comment in Python")
    print("  - Syntax error Python")
    print("  - 3+ righe identiche consecutive (duplicated block)")
    print("  - JSON malformato")
    print("  - Stringhe non bilanciate (odd quote count)")
    print()
    print("Test:")
    print("  python -m pytest tests/test_security.py::TestAntiEscapeGuardrail -v")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
