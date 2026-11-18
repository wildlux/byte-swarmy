"""Test Cycle 53 — Tool `diary_llm` (diario di bordo LLM).

Verifica la capability di scrittura del diario di bordo + sanitizzazione
del task_id. Il tool persiste in `<state_dir>/diary/<task_id>.md`.
"""


from CORE.tools import ToolSet


def _make_tools(tmp_path) -> ToolSet:
    cfg = {
        "paths": {
            "project_root": str(tmp_path / "project"),
            "state_dir": str(tmp_path / "state"),
        },
        "security": {
            "enabled": True,
            "max_output_chars": 10_000,
            "max_file_size_write": 2_000_000,
            "max_file_size_bytes": 50_000_000,
            "max_memory_mb": 1536,
            "project_disk_limit_mb": 2048,
        },
        "routing": {"max_file_size_readable": 50_000},
    }

    class _L:
        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

        def debug(self, *a, **k):
            pass

    return ToolSet(cfg, _L())


def test_diary_llm_scrive(tmp_path):
    tools = _make_tools(tmp_path)
    res = tools.diary_llm("task-42", "provo X, fallisco per Y")
    assert res.startswith("OK")
    p = tmp_path / "state" / "diary" / "task-42.md"
    assert p.exists()
    assert "Y" in p.read_text(encoding="utf-8")


def test_diary_llm_task_id_sanitizzato(tmp_path):
    tools = _make_tools(tmp_path)
    res = tools.diary_llm("../evil", "contenuto di prova")
    assert res.startswith("OK")
    # task_id viene sanitizzato (path traversal -> nome semplice)
    p = tmp_path / "state" / "diary" / "evil.md"
    assert p.exists()


def test_diary_llm_content_troppo_lungo(tmp_path):
    tools = _make_tools(tmp_path)
    res = tools.diary_llm("task-x", "x" * 50_000)
    assert res.startswith("ERROR")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
