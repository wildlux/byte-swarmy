"""CORE/model_knowledge.py — Conoscenza software sui modelli LLM.

Fonte: ``CONFIG/model_knowledge.json`` (categorizzazione DeepSeek 2026-11-11
+ consigli "entro 4GB" dall'hardware HP dell'utente). Ogni voce::

    {"nome": "qwen2.5-coder:3b", "categoria": "Programmazione",
     "utilizzo": "Coding Bilanciato", "vram_ok": true}

Il modulo risponde alle domande della GUI (pannello Modelli → Attori):
  - quali modelli sono consigliati per un attore (llm / decision_model)?
  - quali sono già installati (``ollama list``)?
  - quali mancano e sono scaricabili (``ollama pull``)?
  - cosa NON è scaricabile (vram_ok == "Cloud" → API remota, non Ollama)

Fail-open: senza file o senza ollama CLI restituisce liste vuote — la GUI
degradando mostra solo i combo esistenti, mai un crash.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
KNOWLEDGE_FILE = BASE_DIR / "CONFIG" / "model_knowledge.json"

# Attore → categorie utili (il worker genera codice, il planner ragiona)
ACTOR_CATEGORIES = {
    "llm": ["Programmazione", "Chat Generale"],
    "decision_model": ["Pensiero Profondo"],
}

MAX_SUGGESTIONS = 8  # cap nel combo: troppi consigli affogano l'utente

# 🆕 Tag di capacità a fine nome (emoji + parola), seguono le categorie
# del JSON di conoscenza: coding / scrittura / ragionamento / …
CATEGORY_TAGS = {
    "Programmazione": "💻 coding",
    "Chat Generale": "💬 chat/scrittura",
    "Pensiero Profondo": "🧠 ragionamento",
    "Sicurezza Informatica": "🛡️ sicurezza",
    "SysAdmin": "🐧 sysadmin",
    "Traduzioni": "🌐 traduzioni",
    "Visione": "👁️ visione",
    "Embeddings": "🧩 embeddings",
    "Cloud": "☁️ cloud",
}

_cache: dict = {"stamp": None, "data": {}}


def _reload() -> dict:
    """Carica/ricarica la conoscenza se il file è cambiato (mtime stamp)."""
    try:
        stamp = KNOWLEDGE_FILE.stat().st_mtime_ns
    except Exception:
        stamp = None
    if stamp == _cache["stamp"]:
        return _cache["data"]
    data: dict = {"consigliati_entro_4gb": {}, "modelli": []}
    try:
        raw = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data["consigliati_entro_4gb"] = dict(
                raw.get("consigliati_entro_4gb", {}))
            models = raw.get("modelli", [])
            if isinstance(models, list):
                data["modelli"] = [m for m in models
                                   if isinstance(m, dict) and m.get("nome")]
    except Exception:
        pass  # fail-open
    _cache["stamp"] = stamp
    _cache["data"] = data
    return data


def list_entries() -> list[dict]:
    """Tutte le voci note."""
    return list(_reload()["modelli"])


def categories() -> list[str]:
    """Categorie presenti, nell'ordine del file."""
    seen: list[str] = []
    for m in _reload()["modelli"]:
        cat = str(m.get("categoria", "")).strip()
        if cat and cat not in seen:
            seen.append(cat)
    return seen


def by_category(category: str) -> list[dict]:
    """Voci di una categoria."""
    return [m for m in _reload()["modelli"]
            if str(m.get("categoria", "")).strip() == category]


def best_for_4gb(category: str) -> list[str]:
    """Consigli 'entro 4GB' per una categoria (dal file di note HP)."""
    return list(_reload()["consigliati_entro_4gb"].get(category, []))


def entry_for(name: str) -> dict | None:
    """Voce di conoscenza per un modello (match esatto o ':latest')."""
    want = _normalize(name)
    if not want:
        return None
    for m in list_entries():
        if _normalize(m.get("nome", "")) == want:
            return m
    return None


def _normalize(name: str) -> str:
    n = str(name or "").strip().lower()
    if n.endswith(":latest"):
        n = n[: -len(":latest")]
    return n


def is_installed(name: str, installed: set[str] | None = None) -> bool:
    """True se il modello è presente localmente (``ollama list``)."""
    got = installed if installed is not None else installed_names()
    n = _normalize(name)
    return n in {_normalize(x) for x in got}


def installable(entry: dict) -> bool:
    """Scaricabile via ollama pull? (Cloud = API remota, NON scaricabile)"""
    return entry.get("vram_ok") != "Cloud" and bool(entry.get("nome"))


def is_cloud_name(name: str) -> bool:
    """True se il NOME stesso dichiara il cloud (es. '…:cloud', '…-cloud').

    Copre i modelli presenti in ollama list ma fuori dal JSON di
    conoscenza (gemma4:31b-cloud, deepseek-v4-flash:cloud, …).
    """
    n = _normalize(name)
    return n.endswith(":cloud") or n.endswith("-cloud")


def tag_for(entry: dict) -> str:
    """Tag di capacità dalla categoria: '💻 coding', '🧠 ragionamento', …."""
    cat = str(entry.get("categoria", "")).strip()
    return CATEGORY_TAGS.get(cat, cat)


def place_icon(entry: dict, installed: set[str] | None = None) -> str:
    """Icona di collocazione: 🌍 nel cloud, 📌 locale, ⬇ scaricabile."""
    if entry.get("vram_ok") == "Cloud" or is_cloud_name(entry.get("nome", "")):
        return "🌍"
    if is_installed(entry.get("nome", ""), installed):
        return "📌"
    return "⬇"


def capability_label(name: str) -> str:
    """Tag di capacità per un NOME di modello ('💻 coding' o '')."""
    e = entry_for(name)
    return tag_for(e) if e else ""


def absent_entries(installed: set[str] | None = None) -> list[dict]:
    """Voci conoscite NON installate (cloud INCLUSE, si mostrano 🌍)."""
    got = installed if installed is not None else installed_names()
    norm = {_normalize(x) for x in got}
    return [m for m in list_entries()
            if _normalize(m.get("nome", "")) not in norm]


def installed_names(timeout: float = 3.0) -> set[str]:
    """Nomi dei modelli installati via ``ollama list`` (fail-open → set())."""
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True,
                           text=True, timeout=timeout)
        if r.returncode != 0:
            return set()
        out: set[str] = set()
        for line in r.stdout.splitlines()[1:]:  # la 1ª riga è l'header
            name = line.split()[0] if line.split() else ""
            if name:
                out.add(name)
        return out
    except Exception:
        return set()


def suggest_for_actor(actor: str, installed: set[str] | None = None,
                      ) -> list[dict]:
    """Consigli per un attore, in ordine di priorità.

    Ordine: 1) già installati (li può usare SUBITO), 2) consigliati
    "entro 4GB", 3) resto della categoria. Cap a MAX_SUGGESTIONS.
    """
    cats = ACTOR_CATEGORIES.get(actor, ["Chat Generale"])
    got = installed if installed is not None else installed_names()

    pool: list[dict] = []
    for cat in cats:
        pool.extend(by_category(cat))

    def rank(m: dict) -> tuple:
        nome = str(m.get("nome", ""))
        n = _normalize(nome)
        inst = n in {_normalize(x) for x in got}
        best = n in {_normalize(x) for x in best_for_4gb(
            str(m.get("categoria", "")))}
        return (0 if inst else 1, 0 if best else 1, cats.index(
            str(m.get("categoria", ""))) if str(
            m.get("categoria", "")) in cats else 99)

    seen: set[str] = set()
    out: list[dict] = []
    for m in sorted(pool, key=rank):
        n = _normalize(m.get("nome", ""))
        if n in seen:
            continue
        seen.add(n)
        out.append(m)
        if len(out) >= MAX_SUGGESTIONS:
            break
    return out


def missing_entries(installed: set[str] | None = None) -> list[dict]:
    """Voci conoscite, non installate e scaricabili (per il pulsante ⬇)."""
    got = installed if installed is not None else installed_names()
    norm = {_normalize(x) for x in got}
    return [m for m in list_entries()
            if _normalize(m.get("nome", "")) not in norm
            and installable(m)]


def suggestion_label(entry: dict, installed: set[str] | None = None,
                     ) -> str:
    """Etichetta combo: '📌 nome — utilizzo · 💻 coding'.

    Icona di collocazione davanti al nome (🌍 cloud, 📌 locale,
    ⬇ da scaricare) e tag di capacità a fine riga.
    """
    got = installed if installed is not None else installed_names()
    icon = place_icon(entry, got)
    tag = tag_for(entry)
    tail = f" · {tag}" if tag else ""
    return (f"{icon} {entry.get('nome', '?')} — "
            f"{entry.get('utilizzo', '')}{tail}")
