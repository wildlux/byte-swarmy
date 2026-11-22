"""
CORE/auto_tool.py — attivazione automatica dei tool per parole chiave.

Gemello di ``CORE/auto_skill.py``: nel pannello Chat, con **Auto-tool**
attivo, le parole chiave nel prompt aggiungono da sole le firme dei tool
al contesto. I tool non vengono eseguiti: vengono solo descritti al modello.

Keyword extra dell'utente: ``state/auto_tool_keywords.json`` (gitignored),
es.::

    {"git_commit": ["salva snapshot", "commento commit"]}
"""

from __future__ import annotations

import json
from pathlib import Path

from CORE.auto_skill import normalize

BASE_DIR = Path(__file__).parent.parent.resolve()
OVERRIDES_FILE = BASE_DIR / "state" / "auto_tool_keywords.json"
MAX_AUTO_TOOLS = 4

# Parole chiave per ogni tool di CORE/tools.py (TOOL_SIGNATURES).
TOOL_KEYWORDS: dict[str, list[str]] = {
    "read_file": ["leggi file", "leggere file", "apri file", "mostra file",
                  "contenuto del file", "read file", "cat file"],
    "read_document": ["leggi documento", "estrai testo", "pdf", "documento",
                      "read document", "pdftotext"],
    "list_refs": ["refs", "cheat sheet", "riferimenti gui", "elenco refs"],
    "api_lookup": ["api_lookup", "introspezione", "firma api", "metodi api",
                   "nuova api", "api sconosciuta"],
    "read_file_slice": ["leggi righe", "righe del file", "porzione di file",
                        "da riga a riga", "read file slice"],
    "write_file": ["scrivi file", "crea un file", "salva file", "nuovo file",
                   "write file", "genera file"],
    "patch_code": ["patch", "sostituisci testo", "modifica una porzione",
                   "patch code", "sostituisci stringa"],
    "delete_file": ["cancella file", "elimina file", "rimuovi file",
                    "delete file"],
    "move_file": ["sposta file", "rinomina file", "muovi file", "move file"],
    "list_files": ["elenca file", "lista file", "elenca cartella",
                   "directory", "glob", "list files"],
    "analyze_project": ["analizza progetto", "mappa del progetto",
                        "struttura del progetto", "code map",
                        "analizza codebase"],
    "find_references": ["trova riferimenti", "chi usa", "chiamanti",
                        "occorrenze del simbolo", "find references"],
    "lint_code": ["lint", "controlla lo stile", "verifica sintassi",
                  "errori di sintassi", "pyflakes"],
    "rename_symbol": ["rinomina simbolo", "rinomina funzione",
                      "rinomina variabile", "rename symbol", "anteprima rename"],
    "restore_snapshot": ["rollback", "ripristina snapshot", "annulla rename",
                         "ripristina file"],
    "spawn_subagent": ["crea subagent", "agente figlio", "subagent",
                       "delega task", "spawn agent"],
    "get_subagent_report": ["report subagent", "risultato subagent",
                            "stato subagent"],
    "list_subagents": ["elenca subagent", "lista agenti figli"],
    "retrieve_similar_task": ["task simile", "cerca simile", "task già fatto",
                              "task gia fatto", "retrieval", "similar task",
                              "recupera task"],
    "analyze_complexity": ["complessità", "complessita", "codice complesso",
                           "analyze complexity"],
    "get_call_graph": ["grafo delle chiamate", "call graph", "chi chiama",
                       "catena di chiamate"],
    "find_dead_code": ["codice morto", "dead code", "funzioni non usate",
                       "codice inutilizzato", "import inutilizzati"],
    "extract_method": ["estrae metodo", "estrai funzione", "refactor blocco",
                       "extract method"],
    "run_bash": ["esegui comando", "comando bash", "comando shell",
                 "run bash", "terminale"],
    "git_commit": ["commit", "snapshot git", "git commit", "salva modifiche"],
    "git_diff": ["diff", "differenze", "git diff", "mostra modifiche"],
    "search": ["cerca", "grep", "ricerca nel progetto", "trova nel codice"],
    "git_status": ["stato git", "git status", "file modificati",
                   "non committati"],
    "git_log": ["git log", "ultimi commit", "cronologia commit"],
    "git_branch": ["branch", "git branch", "crea branch", "cambia branch"],
    "git_merge": ["merge", "unisci branch", "git merge"],
    "git_pull": ["git pull", "scarica dal remote", "pull"],
    "git_push": ["git push", "pubblica su github", "push"],
    "git_remote": ["remote", "git remote", "configura remote"],
    "run_test_suite": ["esegui test", "run test", "pytest", "suite di test",
                       "test suite", "lancia i test"],
    "list_tools": ["strumenti disponibili", "elenca tool", "quali tool",
                   "list tools"],
}


def _load_overrides() -> dict[str, list[str]]:
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


def _tool_names() -> list[str]:
    try:
        from CORE.tools import TOOL_SIGNATURES
        return sorted(TOOL_SIGNATURES)
    except Exception:
        return []


def keywords_for(name: str,
                 overrides: dict[str, list[str]] | None = None) -> list[str]:
    """Keyword del tool: curate + eventuali override utente."""
    if overrides is None:
        overrides = _load_overrides()
    words = list(TOOL_KEYWORDS.get(name, []))
    words.extend(overrides.get(name, []))
    seen: set[str] = set()
    out = []
    for word in words:
        norm = normalize(word)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(word)
    return out


def detect(text: str, available: list[str] | None = None) -> list[dict]:
    """Tool pertinenti al prompt, ordinati per numero di keyword match."""
    norm = normalize(text)
    if not norm:
        return []
    names = available if available is not None else _tool_names()
    overrides = _load_overrides()
    matches = []
    for name in names:
        words = keywords_for(str(name), overrides=overrides)
        hit = [w for w in words
               if f" {normalize(w)} " in f" {norm} "]
        if not hit:
            continue
        longest = max(len(normalize(w)) for w in hit)
        matches.append({
            "name": str(name),
            "score": len(hit),
            "keywords": hit,
            "_rank": (len(hit), longest),
        })
    matches.sort(key=lambda m: (m["_rank"], m["name"]), reverse=True)
    for match in matches:
        match.pop("_rank", None)
    return matches[:MAX_AUTO_TOOLS]


def detect_names(text: str, available: list[str] | None = None) -> list[str]:
    """Solo i nomi dei tool rilevati."""
    return [m["name"] for m in detect(text, available=available)]
