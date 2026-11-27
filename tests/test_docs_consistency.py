"""
test_docs_consistency.py — C1: le regole scritte devono combaciare col codice.

Controlli puramente testuali/filesystem: nessun LLM, rete o scrittura.
Protegge le correzioni del Cycle 91 (MAX_STEPS, baseline security, duplicate
GUI/IMPLEMENTED, symlink state → data/state) e i gate successivi: budget di
AGENT.md, doc estese linkate, conteggi tool/intent allineati al codice,
link locali risolti, markdown non schiacciato.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AGENT = ROOT / "AGENT.md"
SPEC = ROOT / "RAG" / "DOCS" / "SPECIFICATIONS.md"
VERIFY = ROOT / "tools" / "verify_cycle.sh"
GUI_LOG = ROOT / "GUI" / "IMPLEMENTED.md"
CANONICAL_LOG = ROOT / "RAG" / "DOCS" / "IMPLEMENTED.md"


def test_max_steps_allineato_al_worker():
    from CORE.worker import Worker

    assert Worker.MAX_STEPS == 10
    agent = AGENT.read_text(encoding="utf-8")
    spec = SPEC.read_text(encoding="utf-8")
    assert "MAX_STEPS = 10" in agent
    assert "MAX_STEPS = 10" in spec
    assert "MAX_STEPS = 6" not in agent
    assert "MAX_STEPS = 6" not in spec


def test_baseline_security_scan_unica():
    agent = AGENT.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    assert "baseline unica: 7 errori" in verify
    assert "baseline 15 errori" not in verify
    assert "**7 errori**" in agent
    assert "baseline: 7 errori" in verify


def test_log_gui_non_duplica_il_registro_canonico():
    gui = GUI_LOG.read_text(encoding="utf-8")
    canonical = CANONICAL_LOG.read_text(encoding="utf-8")
    assert "Stub di indirizzo" in gui
    # nessuna riga lunga del vecchio duplicato deve essere rimasta
    long_gui = {line for line in gui.splitlines() if len(line) > 80}
    long_canonical = {line for line in canonical.splitlines()
                      if len(line) > 80}
    assert not (long_gui & long_canonical)


def test_symlink_state_dichiarato():
    agent = AGENT.read_text(encoding="utf-8")
    assert "symlink a `data/state/`" in agent
    state = ROOT / "state"
    # il symlink è per-install e gitignored: se c'è, deve puntare a data/state
    if state.is_symlink():
        assert state.readlink().as_posix() == "data/state"


ARCHITECTURE = ROOT / "RAG" / "DOCS" / "ARCHITECTURE.md"
OPERATIONS = ROOT / "RAG" / "DOCS" / "OPERATIONS.md"


def test_agent_md_entro_budget():
    """AGENT.md è il system prompt dei modelli piccoli: max ~3.000 caratteri."""
    size = len(AGENT.read_text(encoding="utf-8"))
    assert size <= 3200, (
        f"AGENT.md troppo lungo: {size} caratteri (budget ~3000). "
        "Sposta il contenuto esteso in RAG/DOCS/."
    )


def test_agent_md_code_fence_bilanciati_e_senza_eof_stray():
    text = AGENT.read_text(encoding="utf-8")
    assert text.count("```") % 2 == 0, "code fence non bilanciati in AGENT.md"
    assert not any(line.strip() == "EOF" for line in text.splitlines()), \
        "EOF stray in AGENT.md (artefatto di heredoc)"


def test_docs_estese_esistono_e_sono_linkate():
    agent = AGENT.read_text(encoding="utf-8")
    for doc in (ARCHITECTURE, OPERATIONS):
        assert doc.exists(), f"documento mancante: {doc.relative_to(ROOT)}"
        assert doc.name in agent, f"{doc.name} non è linkato da AGENT.md"


def _conteggi_codice():
    """Numeri autorevoli: tool signatures e trigger dell'intent router."""
    from CORE.tools import TOOL_SIGNATURES

    data = json.loads((ROOT / "INTENT" / "intents.json").read_text(
        encoding="utf-8"))
    intents = data["intents"]
    triggers = sum(len(v) for item in intents
                   for v in item.get("triggers", {}).values())
    return len(TOOL_SIGNATURES), len(intents), triggers


def test_conteggi_tool_e_intent_allineati_al_codice():
    tools, intents, triggers = _conteggi_codice()
    readme = ROOT / "README.md"
    readme_en = ROOT / "RAG" / "DOCS" / "README_EN.md"

    for doc in (readme, readme_en, ARCHITECTURE):
        text = doc.read_text(encoding="utf-8")
        assert re.search(rf"\b{tools} tools?\b", text), (
            f"{doc.name}: numero tool outdated (atteso {tools})"
        )
        assert not re.search(r"\b21 tools?\b", text)

    for doc in (readme, readme_en, ARCHITECTURE, SPEC):
        text = doc.read_text(encoding="utf-8")
        assert f"{intents} intent" in text, (
            f"{doc.name}: numero intent outdated (atteso {intents})"
        )
        assert f"{triggers} trigger" in text, (
            f"{doc.name}: numero trigger outdated (atteso {triggers})"
        )
        assert not re.search(r"\b28 intents?\b", text)
        assert not re.search(r"\b314 triggers?\b", text)


def test_link_locali_nelle_doc_risolti():
    docs = [ROOT / "README.md", AGENT] + sorted(
        (ROOT / "RAG" / "DOCS").glob("*.md"))
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip().split("#")[0]
            if not target or target.startswith(
                    ("http://", "https://", "mailto:")):
                continue
            resolved = (doc.parent / target).resolve()
            assert resolved.exists(), (
                f"{doc.relative_to(ROOT)}: link rotto → {target}"
            )


def test_markdown_non_schiacciato():
    docs = [ROOT / "README.md", AGENT] + sorted(
        (ROOT / "RAG" / "DOCS").glob("*.md"))
    for doc in docs:
        longest = max((len(line) for line in
                       doc.read_text(encoding="utf-8").splitlines()),
                      default=0)
        assert longest <= 1000, (
            f"{doc.relative_to(ROOT)}: riga da {longest} caratteri "
            "(contenuto schiacciato da una perdita di newlines)"
        )
