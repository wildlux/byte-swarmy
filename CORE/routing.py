"""CORE/routing.py — Routing SEMPLICE per complessità del task.

I modelli piccoli passano i task concreti-deterministici (suite Fase 2:
9/10) ma falliscono sui concetti astratti e sui multi-step (T9, T4).
Regola: task di complessità ALTA → modello "heavy" SE installato,
altrimenti fallback AUTOMATICO sul modello base. Fail-open ovunque:
senza config, senza heavy installato o senza ollama si usa il base —
mai crash, mai task perso.

Il routing è attivo SOLO in live (client iniettato = test → off):
i test devono restare deterministici.

Fase 7 (piano): decisione sull'IMPATTO reale usando il grafo del
code_map (file toccati, profondità chiamate) al posto delle keyword.
"""
from __future__ import annotations

import re
from typing import Optional

# Keyword che indicano concetti dove i modelli piccoli falliscono da
# zero (prova della suite: T9 decoratore 2/2 senza skill; T6 fibonacci
# memoizzato invece PASSA sul base → non è nella lista). Matching a
# CONFINE DI PAROLA: niente doppi conteggi per sottocstringa
# ("decoratore" non conta anche "decorator").
ADVANCED_KEYWORDS = [
    # concorrenza
    "thread", "lock", "mutex", "concorrente", "concorrenti",
    "concorrenza", "concurrent", "concurrency", "multiprocessing",
    "multiprocess",
    # astrazioni OOP/funzionali
    "decoratore", "decorator", "ereditarietà", "eredita", "ereditare",
    "sottoclasse", "subclass", "super", "polimorfismo", "override",
    "generatore", "generator", "yield", "lazy", "context manager",
    "__enter__", "__exit__", "dunder", "protocollo",
    # I/O e formati avanzati
    "regex", "espressioni regolari", "api", "http", "socket",
    "sqlite", "database", "argparse", "urllib",
    # verifica
    "unittest", "test unitari",
]
# NOTA: ricorsione/memoizzazione NON sono in ADVANCED — T6 (fibonacci
# memoizzato) passa sul base al 1° tentativo in due fasi di fila:
# concetto gestito, non fallimento sistematico.

# Concetti medi: fattibili con skill ma non banali (1–2 → media,
# ≥3 in un task = multi-concept → alta).
MEDIUM_KEYWORDS = [
    "classe", "class", "json", "file", "eccezioni", "exceptions",
    "dizionario", "dictionary", "ordinamento", "sorting", "persistenza",
    "rubrica", "gui", "finestra", "interfaccia",
]

LEVELS = ("bassa", "media", "alta")


def _hits(text: str, keywords: list[str]) -> int:
    """Numero di keyword presenti a confine di parola (case-insensitive)."""
    n = 0
    for kw in keywords:
        pat = re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", re.I)
        if pat.search(text):
            n += 1
    return n


def estimate_complexity(text: str) -> tuple[int, str]:
    """Score + livello ('bassa'|'media'|'alta') dal testo del task.

    Regola semantica (semplice e spiegabile nel log):
      ALTA  = almeno 1 concetto ADVANCED (fallimento sistematico del 3B,
              prova T9 decoratore 2/2) OPPURE ≥3 concetti MEDIUM
              (task multi-concept: la lezione di T5)
      MEDIA = 1–2 concetti MEDIUM oppure testo molto lungo (>220 char)
      BASSA = nessun segnale

    Score = adv×3 + med×1 + bonus lunghezza (per il log, non decide da
    solo). Mai solleva.
    """
    t = str(text or "")
    adv = _hits(t, ADVANCED_KEYWORDS)
    med = _hits(t, MEDIUM_KEYWORDS)
    length_bonus = 1 if len(t) > 220 else 0
    score = adv * 3 + med + length_bonus
    if adv >= 1 or med >= 3:
        level = "alta"
    elif med >= 1 or length_bonus:
        level = "media"
    else:
        level = "bassa"
    return score, level


def route_model_key(title: str, description: str = "",
                    config: Optional[dict] = None,
                    base_key: str = "worker_coder",
                    installed: Optional[set[str]] = None,
                    ) -> tuple[str, str]:
    """(model_key_da_usare, livello) — heavy SOLO se alta+installata.

    Args:
        config: config.toml caricata (cerca [complexity_routing] e
            [models.*]; NON la sezione [routing] dell'orchestrator).
        base_key: modello base (chiave [models.*]).
        installed: set dei modelli installati (None → ollama list).

    Fail-open: qualsiasi cosa manchi → (base_key, level).
    """
    text = f"{title}\n{description}"
    _score, level = estimate_complexity(text)
    if level != "alta":
        return base_key, level
    cfg = config or {}
    rt = cfg.get("complexity_routing") or {}
    if not rt.get("enabled", True):
        return base_key, level
    heavy_key = str(rt.get("heavy_model", "") or "")
    if not heavy_key:
        return base_key, level
    heavy_cfg = (cfg.get("models") or {}).get(heavy_key) or {}
    heavy_name = str(heavy_cfg.get("name", "") or "")
    if not heavy_name:
        return base_key, level
    try:
        from CORE import model_knowledge as mk
        if not mk.is_installed(heavy_name, installed):
            return base_key, level  # heavy non installato: fallback
    except Exception:
        return base_key, level
    return heavy_key, level


def explain(title: str, description: str = "",
            config: Optional[dict] = None,
            base_key: str = "worker_coder",
            installed: Optional[set[str]] = None) -> str:
    """Spiegazione leggibile della decisione (per log GUI)."""
    score, level = estimate_complexity(f"{title}\n{description}")
    key, _ = route_model_key(title, description, config, base_key, installed)
    heavy = str(((config or {}).get("complexity_routing") or {}).get("heavy_model", ""))
    if key != base_key:
        return (f"complessità {level} (score {score}) → {key} "
                f"(heavy {heavy} installato)")
    if level == "alta" and heavy:
        return (f"complessità {level} (score {score}) → {base_key} "
                f"(heavy {heavy} NON installato: fallback)")
    return f"complessità {level} (score {score}) → {base_key}"
