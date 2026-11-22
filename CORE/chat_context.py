"""
CORE/chat_context.py — Tools e Skill selezionabili nel pannello Chat.

La Chat è un banco di prova: l'utente sceglie quali tool e quali skill
iniettare nel system prompt, per confrontare il modello "nudo" con uno
che ha il contesto del progetto.

La selezione è persistita in ``state/chat_tools_skills.json`` (gitignored).
Nessun tool viene ESEGUITO: il contesto serve a guidare la risposta.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
SKILLS_DIR = BASE_DIR / ".opencode" / "skill"
SELECTION_FILE = BASE_DIR / "state" / "chat_tools_skills.json"

MAX_SKILL_CHARS = 2500
MAX_TOTAL_CHARS = 12000


def list_tool_names() -> list[str]:
    """Nomi dei tool disponibili (dalle firme di CORE.tools)."""
    try:
        from CORE.tools import TOOL_SIGNATURES
        return sorted(TOOL_SIGNATURES)
    except Exception:
        return []


def tool_signature(name: str) -> str:
    try:
        from CORE.tools import TOOL_SIGNATURES
        return TOOL_SIGNATURES.get(name, "")
    except Exception:
        return ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Separa il frontmatter YAML minimale (chiave: valore) dal corpo."""
    meta: dict = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end]
            for line in raw.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip().strip('"').strip("'")
            body = text[end + 4:].lstrip("\n")
    return meta, body


def list_skills() -> list[dict]:
    """Skill del repo: [{name, description, path}] ordinate per nome."""
    out = []
    if not SKILLS_DIR.is_dir():
        return out
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        meta, _body = _parse_frontmatter(text)
        out.append({
            "name": meta.get("name") or path.parent.name,
            "description": meta.get("description", ""),
            "path": str(path),
        })
    return sorted(out, key=lambda s: s["name"].lower())


def skill_body(name: str, max_chars: int = MAX_SKILL_CHARS) -> str:
    """Corpo della skill (senza frontmatter), troncato."""
    entry = next((s for s in list_skills() if s["name"] == name), None)
    if not entry:
        return ""
    try:
        text = Path(entry["path"]).read_text(encoding="utf-8")
    except Exception:
        return ""
    _meta, body = _parse_frontmatter(text)
    body = body.strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "\n…(troncato)"
    return body


def _read_raw() -> dict:
    """Contenuto grezzo della selezione (o {} se assente/rotto)."""
    if not SELECTION_FILE.exists():
        return {}
    try:
        data = json.loads(SELECTION_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_selection() -> tuple[list[str], list[str]]:
    """Selezione salvata, filtrata sui tool/skill realmente esistenti."""
    data = _read_raw()
    tools = [str(x) for x in data.get("tools", [])]
    skills = [str(x) for x in data.get("skills", [])]
    valid_tools = set(list_tool_names())
    valid_skills = {s["name"] for s in list_skills()}
    tools = [t for t in tools if t in valid_tools]
    skills = [s for s in skills if s in valid_skills]
    return tools, skills


def load_auto_skill() -> bool:
    """Auto-skill attivo? Default: sì."""
    return bool(_read_raw().get("auto_skill", True))


def load_auto_tool() -> bool:
    """Auto-tool attivo? Default: sì."""
    return bool(_read_raw().get("auto_tool", True))


def save_selection(tools: list[str], skills: list[str],
                   auto_skill: bool | None = None,
                   auto_tool: bool | None = None) -> None:
    """Salva tool/skill; i flag ``None`` conservano il valore esistente."""
    data = _read_raw()
    if auto_skill is None:
        auto_skill = bool(data.get("auto_skill", True))
    if auto_tool is None:
        auto_tool = bool(data.get("auto_tool", True))
    SELECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_FILE.write_text(
        json.dumps({"tools": sorted(set(tools)),
                    "skills": sorted(set(skills)),
                    "auto_skill": bool(auto_skill),
                    "auto_tool": bool(auto_tool)},
                   indent=2, ensure_ascii=False),
        encoding="utf-8")


def build_context(tools: list[str], skills: list[str]) -> str:
    """Blocco di system prompt con tools/skill selezionati (o '')."""
    parts = []
    signatures = [tool_signature(t) for t in tools]
    signatures = [s for s in signatures if s]
    if signatures:
        body = "\n".join(f"- {s}" for s in signatures)
        parts.append("## Strumenti disponibili nel progetto\n" + body)
    blocks = []
    for name in skills:
        body = skill_body(name)
        if body:
            blocks.append(f"### Skill: {name}\n{body}")
    if blocks:
        parts.append("## Skill abilitate\n" + "\n\n".join(blocks))
    if not parts:
        return ""
    header = (
        "Contesto di test fornito dall'utente. Se ti servono questi "
        "strumenti, spiega quale useresti e con quali argomenti; non "
        "inventare risultati che non hai ottenuto."
    )
    text = header + "\n\n" + "\n\n".join(parts)
    if len(text) > MAX_TOTAL_CHARS:
        text = text[:MAX_TOTAL_CHARS].rstrip() + "\n…(contesto troncato)"
    return text
