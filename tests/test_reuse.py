"""Test per i moduli di riuso/manutenibilità (offline, nessuna rete/GUI/Ollama).

Copre:
- CORE/regex_controller.py
- CORE/state_repository.py
- CORE/config_model.py
- CORE/path_utils.py
- CORE/tools.py (tool registry)
- CORE/gui_worker.py (logica astratta, senza avvio thread reale)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Assicura che la root del progetto sia in sys.path
sys.path.insert(0, ".")

from CORE.regex_controller import (  # noqa: E402
    RegexController, compile_cached, number_after_label, last_number,
    json_block, fenced_code, sanitize_name, validate_chars, escape_literal,
    DEFAULT_PATTERNS,
)
from CORE.state_repository import (  # noqa: E402
    StateRepository, load_json, save_json, default_repo,
)
from CORE.config_model import (  # noqa: E402
    load_typed_config, AppConfig, OllamaConfig, ModelsConfig,
)
from CORE.constants import OLLAMA_HOST
from CORE.path_utils import (  # noqa: E402
    is_relative_safe, has_traversal, sanitize_filename, join_safe,
    normalize_separators, path_depth, split_safe, is_within_project,
    safe_project_path, is_sensitive_path,
)
from CORE.tools import (  # noqa: E402
    register_tool, get_tool, list_tools, TOOL_REGISTRY,
)
from CORE.gui_worker import BaseWorker  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# regex_controller
# ═══════════════════════════════════════════════════════════════════

class TestRegexController:
    def test_add_search_findall(self):
        rc = RegexController()
        rc.add("num", r"(\d+)")
        assert rc.search("num", "a=1 b=2").group(1) == "1"
        assert rc.findall("num", "a=1 b=2") == ["1", "2"]

    def test_keyerror_unknown(self):
        rc = RegexController()
        with pytest.raises(KeyError):
            rc.search("inesistente", "x")

    def test_invalid_pattern_not_fatal(self):
        rc = RegexController()
        assert rc.add("pessimo", r"([(") is False
        assert rc.has("pessimo") is False
        assert rc.get("pessimo") is None

    def test_default_patterns_present(self):
        assert "json_object" in DEFAULT_PATTERNS
        assert "py_def" in DEFAULT_PATTERNS

    def test_helpers(self):
        assert number_after_label("RISULTATO: 5050", "RISULTATO") == 5050
        assert number_after_label("RISULTATO: 5049", "RISULTATO") == 5049
        assert number_after_label("niente qui", "RISULTATO") is None
        assert last_number("a=1 b=2 c=42") == 42
        assert last_number("niente") is None
        assert json_block('testo {"a":1} altro') == '{"a":1}'
        assert json_block('lista [1, 2] fine') == '[1, 2]'
        assert json_block('niente qui') is None
        assert fenced_code('ecco ```python\nprint(1)\n``` dopo', 'python') == "print(1)\n"
        assert fenced_code('nessun blocco') is None
        assert sanitize_name("Qwen3.5!") == "qwen3.5-"
        assert sanitize_name("") == "x"
        assert validate_chars("prova_1", "ref") is True
        assert validate_chars("../etc", "ref") is False
        assert validate_chars("file*.txt", "glob") is True
        assert escape_literal("a.b[c") == r"a\.b\[c"


# ═══════════════════════════════════════════════════════════════════
# state_repository
# ═══════════════════════════════════════════════════════════════════

class TestStateRepository:
    def test_save_load_json(self, tmp_path):
        repo = StateRepository(base_dir=tmp_path)
        assert repo.save_json("sub/test.json", {"a": 1}) is True
        assert repo.load_json("sub/test.json") == {"a": 1}
        assert repo.exists("sub/test.json") is True
        assert repo.remove("sub/test.json") is True
        assert repo.exists("sub/test.json") is False

    def test_missing_file_returns_default(self, tmp_path):
        repo = StateRepository(base_dir=tmp_path)
        assert repo.load_json("nessun_file.json", {"default": True}) == {"default": True}

    def test_corrupt_json_returns_default(self, tmp_path):
        repo = StateRepository(base_dir=tmp_path)
        (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")
        assert repo.load_json("bad.json", {"default": True}) == {"default": True}

    def test_module_wrappers(self, tmp_path, monkeypatch):
        # default_repo usa BASE_DIR del progetto; invece testiamo che i wrapper esistano
        assert callable(load_json)
        assert callable(save_json)


# ═══════════════════════════════════════════════════════════════════
# config_model
# ═══════════════════════════════════════════════════════════════════

class TestConfigModel:
    def test_defaults(self):
        c = AppConfig()
        assert c.ollama.host == OLLAMA_HOST
        assert c.security.enabled is True
        assert c.paths.project_root == "./project"

    def test_load_typed_config_real_file(self):
        c = load_typed_config("CONFIG/config.toml")
        assert c.ollama.host == OLLAMA_HOST
        assert c.ollama.request_timeout == 300
        assert c.models.orchestrator.name == "qwen2.5:1.5b"
        assert c.models.planner.num_ctx == 3072
        assert c.security.enabled is True
        assert c.security.max_output_chars == 10000
        assert c.routing.confidence_threshold == 0.65
        assert c.decision_models.active == "qwen2_5"
        assert c.generic_task_planner.enabled is True
        assert c.hardware.mode == "auto"
        assert c.audit_gates.mode == "advisory"
        assert "ollama" in c.raw

    def test_missing_file_returns_defaults(self, tmp_path):
        c = load_typed_config(str(tmp_path / "nessun_file.toml"))
        assert isinstance(c, AppConfig)
        assert c.ollama.host == OLLAMA_HOST


# ═══════════════════════════════════════════════════════════════════
# path_utils
# ═══════════════════════════════════════════════════════════════════

class TestPathUtils:
    def test_is_relative_safe(self):
        assert is_relative_safe("a/b/c") is True
        assert is_relative_safe("../etc") is False
        assert is_relative_safe("/etc/passwd") is False
        assert is_relative_safe("~/x") is False
        assert is_relative_safe("a") is True

    def test_has_traversal(self):
        assert has_traversal("../etc") is True
        assert has_traversal("a/b") is False
        assert has_traversal("a\\..\\b") is True

    def test_sanitize_filename(self):
        assert sanitize_filename("a<>b:c|d?.txt") == "a__b_c_d_.txt"
        assert sanitize_filename("CON.txt") == "CON__.txt"
        assert sanitize_filename("") == "file"
        assert len(sanitize_filename("a" * 300)) <= 255

    def test_join_safe(self):
        with pytest.raises(ValueError):
            join_safe("project", "..", "etc")
        p = join_safe("project", "sub", "file.txt")
        assert str(p).endswith("project/sub/file.txt")

    def test_normalize_separators(self):
        assert normalize_separators("a\\b\\c") == "a/b/c"

    def test_path_depth_split(self):
        assert path_depth("a/b/c") == 3
        assert split_safe("a/b/c") == ["a", "b", "c"]

    def test_is_within_project(self, tmp_path):
        assert is_within_project("sub/file.txt", tmp_path) is True
        assert is_within_project("../x", tmp_path) is False

    def test_reexport_security(self):
        assert callable(safe_project_path)
        assert callable(is_sensitive_path)


# ═══════════════════════════════════════════════════════════════════
# tools tool registry
# ═══════════════════════════════════════════════════════════════════

class TestToolRegistry:
    def teardown_method(self):
        TOOL_REGISTRY.clear()

    def test_register_get_list(self):
        @register_tool("saluto")
        def mio_tool(ctx, nome: str) -> str:
            return f"Ciao {nome}"

        assert get_tool("saluto") is mio_tool
        assert "saluto" in list_tools()
        assert get_tool("inesistente") is None


# ═══════════════════════════════════════════════════════════════════
# gui_worker (logica astratta, nessun thread avviato)
# ═══════════════════════════════════════════════════════════════════

class TestGuiWorkerLogic:
    def test_base_has_signals_and_methods(self):
        w = BaseWorker()
        assert hasattr(w, "progress")
        assert hasattr(w, "finished_ok")
        assert hasattr(w, "failed")
        assert hasattr(w, "cancel")
        assert hasattr(w, "is_cancelled")
        assert w.is_cancelled() is False
        w.cancel()
        assert w.is_cancelled() is True

    def _execute_raises_not_implemented(self):
        w = BaseWorker()
        with pytest.raises(NotImplementedError):
            w._execute()
