"""
CORE/auto_skill.py — attivazione automatica delle skill per parole chiave.

Nel pannello Chat l'utente può lasciare attivo **Auto-skill**: quando scrive
un prompt, le skill pertinenti vengono aggiunte da sole al contesto, senza
spuntarle a mano.

Come funziona:
1. ogni skill ha un elenco di parole chiave (italiano + inglese) in
   ``KEYWORDS`` qui sotto;
2. l'utente può aggiungere altre parole senza toccare il codice in
   ``state/auto_skill_keywords.json`` (gitignored), es.::

       {"git-expert": ["rebase", "tag"], "summarizer": ["tl;dr"]}

3. ``detect()`` normalizza il prompt (minuscole, niente accenti/punteggiatura),
   cerca le keyword come parole intere e restituisce le skill più rilevanti.

Non esegue nulla: produce solo nomi di skill da iniettare nel system prompt.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
OVERRIDES_FILE = BASE_DIR / "state" / "auto_skill_keywords.json"

# Quante skill auto-abilitare al massimo per prompt (evita prompt gonfi).
MAX_AUTO_SKILLS = 4

# Parole chiave curate per ogni skill del repo (.opencode/skill/).
# Frasi multi-parola = più precise; i match sono su parole intere.
KEYWORDS: dict[str, list[str]] = {
    "action-planner": [
        "pianifica", "pianificare", "piano", "ambigua", "ambiguo",
        "non chiaro", "chiarimento", "clarify", "plan", "planning",
        "passo passo", "scomponi",
    ],
    "api-refs": [
        "api", "riferimenti api", "cheat sheet", "allucinazioni",
        "introspezione", "api_lookup", "libreria", "librerie", "sdk",
    ],
    "blender": [
        "blender", "bpy", "mesh", "modello 3d", "gltf", "obj", "stl",
        "rendering", "scena 3d",
    ],
    "current-time": [
        "che ore sono", "che ora e", "ora corrente", "data di oggi",
        "data odierna", "current time", "utc", "fuso orario", "giorno attuale",
    ],
    "date-counts": [
        "giorni tra", "differenza tra date", "conteggio giorni",
        "scadenza", "intervallo di date", "deadline", "date diff",
        "quanti giorni", "somma date",
    ],
    "debt-ledger": [
        "debito tecnico", "refactoring", "rifattorizza", "ottimizzazione",
        "ottimizzare", "technical debt", "ledger", "migliorare il codice",
    ],
    "freecad": [
        "freecad", "cad", "partdesign", "step file", "formato step",
        "modellazione", "geometria", "parametrico",
    ],
    "git-expert": [
        "git", "commit", "branch", "merge", "stash", "push", "pull",
        "diff", "versionamento", "repository", "rebase", "conflitto",
    ],
    "linux-driver": [
        "driver linux", "kernel module", "modulo kernel", "i2c", "spi",
        "dma", "irq", "device tree", "regmap", "iio", "gpio",
        "char device", "platform driver",
    ],
    "linux-essentials": [
        "comandi linux", "amministrazione linux", "filesystem", "permessi",
        "processi", "systemd", "bash", "shell", "utenti", "rete linux",
        "lpi", "terminale",
    ],
    "linux-kernel-refs": [
        "header kernel", "api kernel", "kernel refs", "linux kernel",
        "simboli kernel", "kernel headers", "struct kernel",
    ],
    "markdown-formatter": [
        "markdown", "formattazione", "formattare", "tabella", "tabelle",
        "documento", "impaginazione", "report ordinato",
    ],
    "math-engine": [
        "derivata", "integrale", "limite", "simbolico", "algebra",
        "equazione", "calcolo matematico", "sympy", "matematica", "formula",
    ],
    "networking-cisco": [
        "cisco", "ios", "vlan", "acl", "nat", "ospf", "eigrp", "routing",
        "switch", "ccna", "configurazione rete", "trunk",
    ],
    "project-radiography": [
        "radiografia", "censimento", "codebase", "god file", "god-file",
        "salute del progetto", "mappa del progetto", "code map",
        "progetto sconosciuto", "com e fatto il progetto",
    ],
    "qr-code": [
        "qr", "codice qr", "qrcode", "qr code", "codice a barre",
    ],
    "research-report": [
        "ricerca", "ricerche", "fonti", "confronto", "analisi comparativa",
        "report pdf", "file word", "file excel", "odt", "libreoffice",
        "diagramma", "grafico svg", "deliverable",
    ],
    "skill-lister": [
        "chiocciola", "elenca skill", "lista skill", "skill disponibili",
        "quali skill",
    ],
    "skill-searcher": [
        "cerca skill", "trova skill", "skill giusta", "quale skill",
        "skill searcher", "motore di ricerca skill",
    ],
    "sql-writer": [
        "sql", "query", "database", "mysql", "postgres", "postgresql",
        "sqlite", "nosql", "select", "insert", "join", "indice",
    ],
    "static-analyzer": [
        "lint", "pyflakes", "analisi statica", "security scan",
        "gate statico", "compile", "compilazione", "static check",
    ],
    "summarizer": [
        "riassumi", "riassunto", "sintesi", "condensa", "summarize",
        "summary", "ridurre i token", "tl dr",
    ],
    "svg-studio": [
        "svg", "inkscape", "krita", "schema grafico", "disegno vettoriale",
        "diagramma vettoriale",
    ],
}

# Parole troppo comuni: non diventano keyword derivate automaticamente.
_STOPWORDS = {
    "skill", "della", "delle", "degli", "dello", "dalla", "dalle",
    "questo", "questa", "questi", "queste", "quando", "come", "cosa",
    "fare", "fai", "usa", "usare", "usa questa", "serve", "servono",
    "the", "this", "that", "with", "from", "your", "when", "what",
    "and", "for", "per", "una", "uno", "gli", "con", "senza", "anche",
}


def normalize(text: str) -> str:
    """Minuscole, niente accenti/punteggiatura, spazi singoli."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _phrase_hit(haystack: str, keyword: str) -> bool:
    """True se la keyword compare come parola/frase intera."""
    kw = normalize(keyword)
    if not kw:
        return False
    return f" {kw} " in f" {haystack} "


def _load_overrides() -> dict[str, list[str]]:
    """Keyword extra scritte dall'utente in state/auto_skill_keywords.json."""
    if not OVERRIDES_FILE.exists():
        return {}
    try:
        data = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                words = [str(w).strip() for w in value if str(w).strip()]
                if words:
                    out[str(key)] = words
    return out


def _derived_keywords(name: str, description: str) -> list[str]:
    """Fallback per skill nuove: parole significative di nome+descrizione."""
    words = []
    for token in normalize(name).split():
        if len(token) >= 3 and token not in _STOPWORDS:
            words.append(token)
    for token in normalize(description).split():
        if len(token) >= 5 and token not in _STOPWORDS:
            words.append(token)
    seen: set[str] = set()
    out = []
    for word in words:
        if word not in seen:
            seen.add(word)
            out.append(word)
    return out[:12]


def keywords_for(name: str, description: str = "",
                 overrides: dict[str, list[str]] | None = None) -> list[str]:
    """Keyword della skill: curate + override utente (o derivate)."""
    if overrides is None:
        overrides = _load_overrides()
    words = list(KEYWORDS.get(name, []))
    words.extend(overrides.get(name, []))
    if not words:
        words = _derived_keywords(name, description)
    seen: set[str] = set()
    out = []
    for word in words:
        norm = normalize(word)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(word)
    return out


def _available_skills() -> list[dict]:
    """Lista skill del repo, senza import circolare a modulo caricato."""
    try:
        from CORE.chat_context import list_skills
        return list_skills()
    except Exception:
        return []


def detect(text: str, available: list[dict] | None = None) -> list[dict]:
    """Skill pertinenti al testo, ordinate per rilevanza.

    Ritorna ``[{"name", "score", "keywords"}]`` con al massimo
    ``MAX_AUTO_SKILLS`` elementi. ``available`` permette di passare una
    lista già pronta (utile nei test).
    """
    norm = normalize(text)
    if not norm:
        return []
    entries = available if available is not None else _available_skills()
    overrides = _load_overrides()
    matches = []
    for entry in entries:
        name = str(entry.get("name") or "")
        if not name:
            continue
        words = keywords_for(name, str(entry.get("description") or ""),
                             overrides=overrides)
        hit = [w for w in words if _phrase_hit(norm, w)]
        if not hit:
            continue
        longest = max(len(normalize(w)) for w in hit)
        matches.append({
            "name": name,
            "score": len(hit),
            "keywords": hit,
            "_rank": (len(hit), longest),
        })
    matches.sort(key=lambda m: (m["_rank"], m["name"]), reverse=True)
    for match in matches:
        match.pop("_rank", None)
    return matches[:MAX_AUTO_SKILLS]


def detect_names(text: str, available: list[dict] | None = None) -> list[str]:
    """Solo i nomi delle skill rilevate (comodo per la GUI)."""
    return [m["name"] for m in detect(text, available=available)]
