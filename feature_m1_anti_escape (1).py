#!/usr/bin/env python3
"""M1: Guardrail anti-escape in write_file/patch_code."""
import shutil
from pathlib import Path

SCANNER_FILE = Path("CORE/ast_scanner.py")
SCANNER_BACKUP = Path("CORE/ast_scanner.py.bak.m1")
TOOLS_FILE = Path("CORE/tools.py")
TOOLS_BACKUP = Path("CORE/tools.py.bak.m1")
TEST_FILE = Path("tests/test_security.py")
TEST_BACKUP = Path("tests/test_security.py.bak.m1")


ANTI_ESCAPE_CODE = '''

# ====================================================================
# Anti-escape artifact detection (M1)
# ====================================================================

def detect_escape_artifacts(content, filename=""):
    """Detect AI-generated escape artifacts. Returns list of dicts."""
    if not content:
        return []
    artifacts = []
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    if ext == "py":
        # 1. AST parse
        try:
            ast.parse(content)
        except SyntaxError as e:
            artifacts.append({
                "line": e.lineno or 0,
                "description": "Python syntax error: " + str(e.msg),
            })
        
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            _TSQ = chr(39) * 3  # triple single quote
            if stripped.startswith(chr(34)*3) or stripped.startswith(_TSQ):
                continue
            # 2. C-style // comment outside strings
            if "//" in line:
                in_str = False
                qch = None
                for ch in line:
                    if ch in ('"', "'") and not in_str:
                        in_str = True
                        qch = ch
                    elif ch == qch and in_str:
                        in_str = False
                if not in_str:
                    idx = line.find("//")
                    if idx > 0 and line[idx-1] not in (":", "/"):
                        artifacts.append({
                            "line": i,
                            "description": "C-style // comment in Python code",
                            "context": line.strip()[:100],
                        })
        
        # 3. Duplicated lines (3+ consecutive)
        consec = 1
        for i in range(1, len(lines)):
            if lines[i].strip() and lines[i] == lines[i-1]:
                consec += 1
                if consec >= 3:
                    artifacts.append({
                        "line": i + 1,
                        "description": "line duplicated " + str(consec) + " times",
                        "context": lines[i].strip()[:100],
                    })
            else:
                consec = 1
    
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
    """Returns (ok, error_msg)."""
    artifacts = detect_escape_artifacts(content, filename)
    if not artifacts:
        return (True, "")
    msg = ["Anti-escape guardrail: " + str(len(artifacts)) + " artifact(s) in " + filename + ":"]
    for a in artifacts[:5]:
        ctx = a.get("context", "")
        line_str = "  line " + str(a["line"]) + ": " + a["description"]
        if ctx:
            line_str += " | " + ctx
        msg.append(line_str)
    if len(artifacts) > 5:
        msg.append("  ... and " + str(len(artifacts) - 5) + " more")
    msg.append("Fix the escape artifacts before writing the file.")
    return (False, "\n".join(msg))
'''


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


TEST_CODE = '''

class TestAntiEscapeGuardrail(unittest.TestCase):
    """M1: Anti-escape artifact detection."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-esc-"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        (self.tmp / "state").mkdir()
        self.cfg = {
            "paths": {"project_root": str(self.project), "state_dir": str(self.tmp / "state")},
            "routing": {"max_file_size_readable": 50_000, "timeout_bash": 2},
            "security": {"enabled": True, "max_output_chars": 500,
                         "max_file_size_write": 10_000, "max_file_size_bytes": 1_000_000,
                         "max_memory_mb": 512},
        }
        logger = logging.getLogger("esc-" + str(id(self)))
        logger.addHandler(logging.NullHandler())
        self.tools = ToolSet(self.cfg, logger)
        self.tools.set_worker("esc-test")
    
    def test_clean_python_passes(self):
        result = self.tools.write_file("clean.py", "def hello():\n    print('hi')\n")
        self.assertTrue(result.startswith("OK:"), result)
    
    def test_syntax_error_blocked(self):
        result = self.tools.write_file("bad.py", "def broken(:\n    pass\n")
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("syntax", result.lower())
    
    def test_c_style_comment_blocked(self):
        result = self.tools.write_file("bad2.py", "x = 1\n// C comment\nprint(x)\n")
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_duplicated_lines_blocked(self):
        result = self.tools.write_file("dup.py", "x = 1\nx = 1\nx = 1\nprint(x)\n")
        self.assertTrue(result.startswith("ERROR:"), result)
        self.assertIn("duplicat", result.lower())
    
    def test_json_error_blocked(self):
        result = self.tools.write_file("bad.json", '{"key": \\"value"}\n')
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_patch_with_syntax_error_blocked(self):
        self.tools.write_file("t.py", "x = 1\n")
        result = self.tools.patch_code("t.py", "x = 1", "def broken(:\n    pass\n")
        self.assertTrue(result.startswith("ERROR:"), result)
    
    def test_markdown_passes(self):
        result = self.tools.write_file("doc.md", "# Title\n\nSome text.\n")
        self.assertTrue(result.startswith("OK:"), result)
'''


def main():
    print("=" * 60)
    print("M1: ANTI-ESCAPE GUARDRAIL")
    print("=" * 60)
    
    # 1. ast_scanner.py
    print("\n[1/3] Patch CORE/ast_scanner.py")
    if not SCANNER_FILE.exists():
        print("  ERROR: not found"); return 1
    content = SCANNER_FILE.read_text()
    if "detect_escape_artifacts" in content:
        print("  already present")
    else:
        shutil.copy2(SCANNER_FILE, SCANNER_BACKUP)
        if "import ast" not in content:
            content = "import ast\n" + content
        if "import json" not in content:
            content = "import json\n" + content
        content = content.rstrip() + "\n" + ANTI_ESCAPE_CODE
        SCANNER_FILE.write_text(content)
        try:
            compile(content, "ast_scanner.py", "exec")
            print("  OK: added detect_escape_artifacts()")
        except SyntaxError as e:
            print("  SYNTAX ERROR:", e)
            shutil.copy2(SCANNER_BACKUP, SCANNER_FILE)
            return 1
    
    # 2. tools.py
    print("\n[2/3] Patch CORE/tools.py")
    if not TOOLS_FILE.exists():
        print("  ERROR: not found"); return 1
    content = TOOLS_FILE.read_text()
    if "blocked_escape" in content:
        print("  already patched")
    else:
        shutil.copy2(TOOLS_FILE, TOOLS_BACKUP)
        modified = False
        if TOOLS_WRITE_OLD in content:
            content = content.replace(TOOLS_WRITE_OLD, TOOLS_WRITE_NEW, 1)
            modified = True
            print("  OK: write_file patched")
        else:
            print("  WARN: write_file pattern not found")
        if TOOLS_PATCH_OLD in content:
            content = content.replace(TOOLS_PATCH_OLD, TOOLS_PATCH_NEW, 1)
            modified = True
            print("  OK: patch_code patched")
        else:
            print("  WARN: patch_code pattern not found")
        if modified:
            TOOLS_FILE.write_text(content)
            try:
                compile(content, "tools.py", "exec")
                print("  OK: syntax check passed")
            except SyntaxError as e:
                print("  SYNTAX ERROR:", e)
                shutil.copy2(TOOLS_BACKUP, TOOLS_FILE)
                return 1
    
    # 3. tests
    print("\n[3/3] Patch tests/test_security.py")
    if not TEST_FILE.exists():
        print("  ERROR: not found")
    else:
        content = TEST_FILE.read_text()
        if "TestAntiEscapeGuardrail" in content:
            print("  already present")
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
                print("  OK: added 7 tests")
            except SyntaxError as e:
                print("  SYNTAX ERROR:", e)
                shutil.copy2(TEST_BACKUP, TEST_FILE)
    
    print("\n" + "=" * 60)
    print("M1 DONE - Test with:")
    print("  python -m pytest tests/test_security.py::TestAntiEscapeGuardrail -v")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
