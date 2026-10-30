#!/usr/bin/env python3
"""feature_m1_anti_escape.py — Guardrail anti-escape in write_file/patch_code."""
import re
import shutil
from pathlib import Path

SCANNER_FILE = Path("CORE/ast_scanner.py")
SCANNER_BACKUP = Path("CORE/ast_scanner.py.bak.anti_escape")
TOOLS_FILE = Path("CORE/tools.py")
TOOLS_BACKUP = Path("CORE/tools.py.bak.anti_escape")
TEST_FILE = Path("tests/test_security.py")
TEST_BACKUP = Path("tests/test_security.py.bak.anti_escape")


# Codice da aggiungere a CORE/ast_scanner.py
# Usiamo marker unici invece di triple-quote per evitare conflitti
ANTI_ESCAPE_CODE = r'''

# ====================================================================
# Anti-escape artifact detection (M1)
# ====================================================================

def detect_escape_artifacts(content, filename=""):
    """Rileva artefatti di escape nel contenuto di un file.
    Returns: lista di dict con {line, description, context}. Vuota = OK.
    """
    if not content:
        return []
    
    artifacts = []
    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    
    if ext == "py":
        # 1. AST parse - se fallisce, e' corrotto
        try:
            ast.parse(content)
        except SyntaxError as e:
            artifacts.append({
                "line": e.lineno or 0,
                "description": "Python syntax error: " + str(e.msg),
            })
        
        # 2. Pattern check su ogni riga
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            # Skip commenti e docstring Python
            _TQ = chr(34) * 3
            _TSQ = chr(39) * 3
            if stripped.startswith(_TQ) or stripped.startswith(_TSQ):
                continue
            
            # Check // C-style comment (non in stringa)
            if "//" in line:
                # Verifica se // e' fuori da stringhe
                in_string = False
                quote_char = None
                for ch in line:
                    if ch in ('"', "'") and not in_string:
                        in_string = True
                        quote_char = ch
                    elif ch == quote_char and in_string:
                        in_string = False
                if not in_string:
                    idx = line.find("//")
                    # Verifica che non sia // in un URL o divisione
                    if idx > 0 and line[idx-1] not in (":", "/"):
                        artifacts.append({
                            "line": i,
                            "description": "C-style // comment in Python code",
                            "context": line.strip()[:100],
                        })
        
        # 3. Check righe duplicate (3+ identiche consecutive)
        consecutive = 1
        for i in range(1, len(lines)):
            if lines[i].strip() and lines[i] == lines[i-1]:
                consecutive += 1
                if consecutive >= 3:
                    artifacts.append({
                        "line": i + 1,
                        "description": "line duplicated " + str(consecutive) + " times consecutively",
                        "context": lines[i].strip()[:100],
                    })
            else:
                consecutive = 1
    
    elif ext == "json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            artifacts.append({
                "line": e.lineno or 0,
                "description": "JSON parse error: " + str(e.msg),
            })
    
    return artifacts


def check_no_escape_artifacts(content, filename=""):
    """Check che ritorna (ok, error_msg)."""
    artifacts = detect_escape_artifacts(content, filename)
    if not artifacts:
        return (True, "")
    
    lines_msg = ["Anti-escape guardrail: " + str(len(artifacts)) + " artifact(s) detected in " + filename + ":"]
    for a in artifacts[:5]:
        ctx = a.get("context", "")
        line_str = "  line " + str(a["line"]) + ": " + a["description"]
        if ctx:
            line_str += " | " + ctx
        lines_msg.append(line_str)
    if len(artifacts) > 5:
        lines_msg.append("  ... and " + str(len(artifacts) - 5) + " more")
    lines_msg.append("Fix the escape artifacts before writing the file.")
    
    return (False, "\n".join(lines_msg))
'''


# Patch CORE/tools.py
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
            
            # M1: Anti-escape artifact check
            from CORE.ast_scanner import check_no_escape_artifacts
            ok_esc, msg_esc = check_no_escape_artifacts(content, path)
            if not ok_esc:
                self._audit("blocked_escape", f'op=write_file path="{self._q(path)}"',
                            "WARNING")
                return f"ERROR: {msg_esc}"'''

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
        
        # M1: Anti-escape artifact check on new_text
        from CORE.ast_scanner import check_no_escape_artifacts
        ok_esc, msg_esc = check_no_escape_artifacts(new_text, path)
        if not ok_esc:
            self._audit("blocked_escape", f'op=patch_code path="{self._q(path)}"',
                        "WARNING")
            return f"ERROR: {msg_esc}"'''


# Test da aggiungere
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
        logger = logging.getLogger("escape-" + str(id(self)))
        logger.addHandler(logging.NullHandler())
        self.tools = ToolSet(self.cfg, logger)
        self.tools.set_worker("escape-test")
    
    def test_clean_python_passes(self):
        result = self.tools.write_file("clean.py", "def hello():\n    print('hi')\n")
        self.assertTrue(result.startswith("OK:"), result)
    
    def test_syntax_error_blocked(self):
        bad_code = "def broken(:\n    pass\n"
        result = self.tools.write_file("broken.py", bad_code)
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("syntax", result.lower())
    
    def test_c_style_comment_blocked(self):
        bad_code = "x = 1\n// this is a C comment\nprint(x)\n"
        result = self.tools.write_file("bad2.py", bad_code)
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_duplicated_lines_blocked(self):
        bad_code = "x = 1\nx = 1\nx = 1\nprint(x)\n"
        result = self.tools.write_file("dup.py", bad_code)
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("duplicat", result.lower())
    
    def test_json_error_blocked(self):
        bad_json = '{"key": \\"value"}\n'
        result = self.tools.write_file("bad.json", bad_json)
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_patch_code_with_syntax_error_blocked(self):
        self.tools.write_file("target.py", "x = 1\n")
        result = self.tools.patch_code("target.py", "x = 1", "def broken(:\n    pass\n")
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_markdown_passes(self):
        md = "# Title\n\nSome text here.\n"
        result = self.tools.write_file("doc.md", md)
        self.assertTrue(result.startswith("OK:"), result)
'''


def main():
    print("=" * 60)
    print("M1: ANTI-ESCAPE GUARDRAIL")
    print("=" * 60)
    
    # 1. Patch ast_scanner.py
    print("\n-> Patch CORE/ast_scanner.py")
    if not SCANNER_FILE.exists():
        print("  ERROR: file not found")
        return 1
    
    content = SCANNER_FILE.read_text()
    if "detect_escape_artifacts" in content:
        print("  already present, skip")
    else:
        shutil.copy2(SCANNER_FILE, SCANNER_BACKUP)
        # Inserisci import DOPO from __future__ (che deve essere primo)
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("from __future__"):
                insert_idx = i + 1
                break
            elif line.startswith("import ") or line.startswith("from "):
                insert_idx = i
                break
        # Aggiungi import se mancanti
        new_imports = []
        if "import ast" not in content:
            new_imports.append("import ast")
        if "import json" not in content:
            new_imports.append("import json")
        if new_imports:
            lines.insert(insert_idx, "\n".join(new_imports))
        content = "\n".join(lines)
        content = content.rstrip() + "\n" + ANTI_ESCAPE_CODE
        SCANNER_FILE.write_text(content)
        try:
            compile(content, "ast_scanner.py", "exec")
            print("  OK: added detect_escape_artifacts() and check_no_escape_artifacts()")
        except SyntaxError as e:
            print("  SYNTAX ERROR:", e)
            shutil.copy2(SCANNER_BACKUP, SCANNER_FILE)
            return 1
    
    # 2. Patch tools.py
    print("\n-> Patch CORE/tools.py")
    if not TOOLS_FILE.exists():
        print("  ERROR: file not found")
        return 1
    
    content = TOOLS_FILE.read_text()
    if "blocked_escape" in content:
        print("  already patched, skip")
    else:
        shutil.copy2(TOOLS_FILE, TOOLS_BACKUP)
        modified = False
        
        if TOOLS_WRITE_OLD in content:
            content = content.replace(TOOLS_WRITE_OLD, TOOLS_WRITE_NEW, 1)
            modified = True
            print("  OK: write_file calls check_no_escape_artifacts()")
        else:
            print("  WARN: write_file pattern not found exactly")
        
        if TOOLS_PATCH_OLD in content:
            content = content.replace(TOOLS_PATCH_OLD, TOOLS_PATCH_NEW, 1)
            modified = True
            print("  OK: patch_code calls check_no_escape_artifacts()")
        else:
            print("  WARN: patch_code pattern not found exactly")
        
        if modified:
            TOOLS_FILE.write_text(content)
            try:
                compile(content, "tools.py", "exec")
                print("  OK: syntax check passed")
            except SyntaxError as e:
                print("  SYNTAX ERROR:", e)
                shutil.copy2(TOOLS_BACKUP, TOOLS_FILE)
                return 1
    
    # 3. Add tests
    print("\n-> Patch tests/test_security.py")
    if not TEST_FILE.exists():
        print("  ERROR: file not found")
    else:
        content = TEST_FILE.read_text()
        if "TestAntiEscapeGuardrail" in content:
            print("  already present, skip")
        else:
            shutil.copy2(TEST_FILE, TEST_BACKUP)
            insert_point = 'if __name__ == "__main__":'
            if insert_point in content:
                content = content.replace(insert_point, TEST_CODE + "\n\n" + insert_point, 1)
            else:
                content = content.rstrip() + "\n" + TEST_CODE
            
            TEST_FILE.write_text(content)
            try:
                compile(content, "test_security.py", "exec")
                print("  OK: added 7 anti-escape tests")
            except SyntaxError as e:
                print("  SYNTAX ERROR:", e)
                shutil.copy2(TEST_BACKUP, TEST_FILE)
    
    print("\n" + "=" * 60)
    print("M1 COMPLETED")
    print("=" * 60)
    print("\nTest with:")
    print("  python -m pytest tests/test_security.py::TestAntiEscapeGuardrail -v")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
