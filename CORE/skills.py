"""CORE/skills.py — Skill procedurali per LLM piccoli.

Una "skill" e' una ricetta operativa (passi numerati + template da
riempire + criteri di done) salvata come file markdown in ``SKILLS/``.
Il matcher sceglie la skill piu' rilevante per il task; il Worker la
inietta nel prompt (sezione ``## SKILL``) e il ciclo di correzione la
ri-inietta ad ogni retry.

Perche' funziona sui modelli piccoli: la skill riduce le scelte libere —
il modello segue una procedura e compila dei vuoti ``{{...}}`` invece di
progettare da zero (dove i modelli piccoli falliscono).

Formato file::

    ---
    id: py-cli-script
    title: Simple Python console script
    keywords: script, cli, sum, ...
    ---
    # Corpo markdown con passi, template e DONE WHEN.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent.resolve()
SKILLS_DIR = BASE_DIR / "SKILLS"

# Cap del corpo iniettato nel prompt: i worker hanno num_ctx limitato,
# una skill lunga affoga il modello piccolo peggio di niente.
MAX_SKILL_BODY_CHARS = 1500

# Cache: ricarica solo se il mtime della directory cambia.
_cache: dict = {"stamp": None, "skills": []}

_FRONTMATTER_RE = re.compile(r"\A-{3,}\s*\n(.*?)\n-{3,}\s*\n?(.*)\Z", re.S)


def _parse_skill_file(path: Path) -> Optional[dict]:
    """Legge un file skill: frontmatter (id/title/keywords) + corpo md."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    m = _FRONTMATTER_RE.match(text.strip())
    if not m:
        return None
    meta_raw, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in meta_raw.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip().lower()] = val.strip()
    sid = meta.get("id", path.stem)
    keywords = [
        k.strip().lower()
        for k in re.split(r"[,;]", meta.get("keywords", ""))
        if k.strip()
    ]
    if not body.strip():
        return None
    return {
        "id": sid,
        "title": meta.get("title", sid),
        "keywords": keywords,
        "body": body.strip(),
        "file": path.name,
    }


def _reload() -> None:
    """Ricarica SKILLS/ se qualcosa e' cambiato (mtime come stamp)."""
    try:
        stamp = tuple(sorted(
            (p.name, p.stat().st_mtime_ns) for p in SKILLS_DIR.glob("*.md")
        )) if SKILLS_DIR.is_dir() else ()
    except Exception:
        stamp = ()
    if stamp == _cache["stamp"]:
        return
    skills = []
    for p in sorted(SKILLS_DIR.glob("*.md")) if SKILLS_DIR.is_dir() else []:
        sk = _parse_skill_file(p)
        if sk:
            skills.append(sk)
    _cache["stamp"] = stamp
    _cache["skills"] = skills


def list_skills() -> list[dict]:
    """Tutte le skill caricate (utile per GUI/debug)."""
    _reload()
    return list(_cache["skills"])


def find_skill(title: str, description: str = "",
               ) -> Optional[dict]:
    """Skill migliore per il task, o None se nessuna matcha.

    Punteggio: occorrenze delle keywords su titolo (peso 3) e descrizione
    (peso 1), match per confine di parola. Deterministico: a parita' di
    score vince la skill con la keyword matchata piu' lunga (piu'
    specifica), poi il titolo piu' corto.
    """
    _reload()
    if not _cache["skills"]:
        return None
    title_l = str(title or "").lower()
    desc_l = str(description or "").lower()

    best, best_score = None, 0.0
    best_kw_len = 0  # keyword matchata più lunga (parità → specificità)
    for sk in _cache["skills"]:
        s = 0.0
        top = 0
        for kw in sk["keywords"]:
            if not kw:
                continue
            pat = re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)")
            if pat.search(title_l):
                s += 3.0 * min(len(kw), 12)
                top = max(top, min(len(kw), 12))
            if desc_l and pat.search(desc_l):
                s += 1.0 * min(len(kw), 12)
                top = max(top, min(len(kw), 12))
        better = (
            s > best_score
            or (s == best_score > 0
                and (top > best_kw_len
                     or (top == best_kw_len and best is not None
                         and len(sk["title"]) < len(best["title"]))))
        )
        if better:
            best, best_score, best_kw_len = sk, s, top
    return best if best_score > 0 else None


def format_skill_block(skill: dict) -> str:
    """Sezione markdown da iniettare nel prompt del Worker."""
    body = str(skill.get("body", ""))[:MAX_SKILL_BODY_CHARS]
    if len(skill.get("body", "")) > MAX_SKILL_BODY_CHARS:
        body += "\n...[skill truncated]"
    return (
        f"## SKILL — follow this recipe EXACTLY\n"
        f"({skill.get('title', skill.get('id', 'skill'))})\n\n"
        f"{body}\n\n"
        f"(End of SKILL: when in doubt, follow the recipe instead of "
        f"inventing.)\n\n"
    )
