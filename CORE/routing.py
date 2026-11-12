"""CORE/routing.py — Routing per complessità del task.

Fase 6 (SEMPLICE, keyword): i modelli piccoli passano i task
concreti-deterministici (suite Fase 2: 9/10) ma falliscono sui concetti
astratti e multi-step (T9, T4). Task di complessità ALTA → modello
"heavy" SE installato, altrimenti fallback AUTOMATICO sul base.

Fase 7 (COMPLESSO, grafo): la decisione considera anche l'IMPATTO REALE
del task sul progetto, dal DATABASE della mappa codice (CORE/code_map):
simboli citati nel task → file toccati (definizione + chiamate),
profondità delle dipendenze a valle (chi chiama chi). ≥2 file toccati
oppure profondità ≥3 → heavy anche se le parole del task sembrano
semplici. Isteresi: una volta heavy si resta heavy sui task 'media'
(si torna al base solo con 'bassa') per non sfarfallare tra task.

Fail-open ovunque: senza config, senza heavy installato o senza ollama
si usa il base — mai crash, mai task perso. Attivo SOLO con client
reale (CLI/GUI), mai con client finti da test (determinismo).
"""
from __future__ import annotations

import re
from pathlib import Path
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

_RANK = {"bassa": 0, "media": 1, "alta": 2}

# Isteresi: stato sticky tra task consecutivi (processo GUI lungo).
_HYST = {"heavy": False, "loaded": False}

# M7: lo sticky è PERSISTENTE su disco — il riavvio della GUI non lo
# perde ("una volta heavy, resta heavy"). Fail-open: file assente o
# corrotto → si parte da False. Lo sticky più vecchio di
# STICKY_MAX_AGE_S è scartato (una sessione vecchia non deve inquinare
# una sessione nuova).
_HYST_FILE = Path("state") / "routing_hysteresis.json"
STICKY_MAX_AGE_S = 1800

# M4: guardia termica — in zona PAUSA (soglie del gatekeeper: CPU ≥75,
# GPU ≥80) l'heavy NON parte e si resta sul base. Lezione della suite
# comparativa: il modello grande muore di throttling (4B: 300 s di
# timeout), il piccolo regge. Il campione più fresco disponibile viene
# da state/timestral_history.json (GUI); se non c'è (CLI), lettura
# diretta da /sys — la stessa meccanica di TimestralManager.
THERMAL_FRESH_S = 120

# Impatto: profondità BFS oltre la quale il task è 'alta' comunque.
MAX_CALL_DEPTH = 3
# Impatto: nomi più corti di così ('id', 'x') sono rumore nel testo.
MIN_SYMBOL_LEN = 3


def _max_level(a: str, b: str) -> str:
    return a if _RANK.get(a, 0) >= _RANK.get(b, 0) else b


def _hyst_load() -> None:
    """Carica lo sticky da disco una sola volta per processo (M7)."""
    if _HYST["loaded"]:
        return
    _HYST["loaded"] = True
    try:
        import json
        import time
        data = json.loads(_HYST_FILE.read_text(encoding="utf-8"))
        age = time.time() - float(data.get("ts", 0))
        if age <= STICKY_MAX_AGE_S:
            _HYST["heavy"] = bool(data.get("heavy"))
    except Exception:
        pass  # assente/corrotto: si parte da False


def _hyst_save() -> None:
    """Salva lo sticky su disco (best-effort, mai solleva)."""
    try:
        import json
        import time
        _HYST_FILE.parent.mkdir(parents=True, exist_ok=True)
        _HYST_FILE.write_text(
            json.dumps({"heavy": _HYST["heavy"],
                        "ts": time.time()}), encoding="utf-8")
    except Exception:
        pass


def _apply_hysteresis(level: str) -> str:
    """Isteresi: una volta heavy, 'media' resta heavy; 'bassa' resetta.
    Sticky persistente su disco (M7)."""
    _hyst_load()
    if level == "alta":
        if not _HYST["heavy"]:
            _HYST["heavy"] = True
            _hyst_save()
        return level
    if _HYST["heavy"] and level == "media":
        return "alta"  # sticky: no sfarfallio tra task consecutivi
    if level == "bassa":
        if _HYST["heavy"]:
            _HYST["heavy"] = False
            _hyst_save()
    return level


def reset_hysteresis() -> None:
    """Reset dello sticky: memoria E disco (test, nuovo batch)."""
    _HYST["heavy"] = False
    _HYST["loaded"] = True
    try:
        if _HYST_FILE.exists():
            _HYST_FILE.unlink()
    except Exception:
        pass


# ── M4: guardia termica ────────────────────────────────────────────────
def _read_cpu_temp_now() -> float:
    """Temp CPU max (°C) da /sys — stessa meccanica di TimestralManager.
    0.0 = non disponibile (fail-open)."""
    temps: list[float] = []
    try:
        tdir = Path("/sys/class/thermal")
        for zone in tdir.glob("thermal_zone*"):
            f = zone / "temp"
            if f.exists():
                try:
                    temps.append(int(f.read_text().strip()) / 1000.0)
                except Exception:
                    continue
    except Exception:
        pass
    if not temps:
        try:
            hdir = Path("/sys/class/hwmon")
            for hw in hdir.iterdir():
                for f in hw.glob("temp*_input"):
                    try:
                        temps.append(int(f.read_text().strip()) / 1000.0)
                    except Exception:
                        continue
        except Exception:
            pass
    return max(temps) if temps else 0.0


def _latest_temps() -> tuple[float, float]:
    """(cpu_temp, gpu_temp) dal campione più fresco disponibile.

    1) `state/timestral_history.json` se salvato negli ultimi
       THERMAL_FRESH_S secondi (la GUI campiona ogni 30 s);
    2) altrimenti lettura diretta /sys (percorso CLI senza Timestral).
    La GPU viene dal campione, se presente: qui non si legga nvidia-smi
    per non aggiungere I/O pesante alla decisione.
    """
    try:
        import json
        import time
        hist = Path("state") / "timestral_history.json"
        if hist.exists():
            data = json.loads(hist.read_text(encoding="utf-8"))
            samples = data.get("samples") or []
            if samples:
                last = samples[-1]
                age = time.time() - float(last.get("timestamp", 0))
                if age <= THERMAL_FRESH_S:
                    return (float(last.get("cpu_temp_max") or 0.0),
                            float(last.get("gpu_temp") or 0.0))
    except Exception:
        pass
    return (_read_cpu_temp_now(), 0.0)


def _thermal_blocked() -> str:
    """Motivo di blocco termico ('' = libero). Mai solleva.

    Usa la STESSA funzione di soglia del gatekeeper
    (MONITORING.thermal_manager.thermal_should_pause: CPU 75 / GPU 80).
    """
    try:
        from MONITORING.thermal_manager import thermal_should_pause
        cpu, gpu = _latest_temps()
        if thermal_should_pause(cpu, gpu):
            return (f"termico: cpu {cpu:.0f}°C gpu {gpu:.0f}°C "
                    f"≥ soglia → heavy evitato")
    except Exception:
        pass
    return ""


def estimate_impact(text: str, project_root: str | Path,
                    exclude_files: Optional[set[str]] = None,
                    ) -> dict:
    """Impatto REALE del task sul progetto, dal grafo del code_map.

    Per Fase 7 (idea utente: il DB mappa il codice → la decisione usa
    il DB, non solo le parole). Cosa misura:
      - cited:  simboli del progetto CITATI nel testo del task
                (match a confine di parola, case-sensitive: i nomi
                Python lo sono; min 3 char per evitare rumore)
      - files:  file che DEFINISCONO i simboli citati ∪ file che li
                CHIAMANO (il file target è escluso: sta per essere
                riscritto, i suoi simboli sono rumore)
      - depth:  profondità BFS delle dipendenze a valle (chi chiama i
                chiamanti), cap MAX_CALL_DEPTH
      - tests:  almeno un file toccato è un test (copertura)

    Livello: '' (nessun simbolo citato) · 'media' (1 file toccato) ·
    'alta' (≥2 file toccati oppure profondità ≥ MAX_CALL_DEPTH).
    Mai solleva.
    """
    out = {"cited": [], "files": [], "depth": 0, "tests": False,
           "level": ""}
    try:
        from CORE import code_map as cm
        root = Path(project_root)
        cm.rebuild(root)
        syms = cm.symbols(root)
        call_rows = cm.calls(root)
    except Exception:
        return out
    if not syms:
        return out

    text_s = str(text or "")
    ex = {str(e) for e in (exclude_files or ())}
    by_name: dict[str, list[dict]] = {}
    for s in syms:
        if s["file"] in ex:
            continue
        by_name.setdefault(s["name"], []).append(s)

    cited = [n for n in sorted(by_name) if len(n) >= MIN_SYMBOL_LEN
             and re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", text_s)]
    if not cited:
        return out
    out["cited"] = cited[:8]

    def_files = {s["file"] for n in cited for s in by_name[n]}
    call_files = {c["file"] for c in call_rows
                  if c["callee"] in cited and c["file"] not in ex}
    touched = def_files | call_files
    out["files"] = sorted(touched)

    # BFS a valle: callee→caller (ultimo segmento del qualname). I file
    # dei chiamanti TRANSITIVI non contano come "toccati", ma servono a
    # profondità e copertura test (un test che chiama un chiamante
    # copre il simbolo citato).
    bfs_files: set[str] = set()
    frontier = set(cited)
    depth = 0
    for _ in range(MAX_CALL_DEPTH):
        rows = [c for c in call_rows
                if c["callee"] in frontier and c["file"] not in ex]
        nxt = {c["caller"].split(".")[-1] for c in rows} - frontier
        if not nxt:
            break
        depth += 1
        bfs_files |= {c["file"] for c in rows}
        frontier |= nxt
    out["depth"] = depth
    out["tests"] = any(f.lower().startswith("test")
                       for f in (touched | bfs_files))

    if len(touched) >= 2 or depth >= MAX_CALL_DEPTH:
        out["level"] = "alta"
    else:
        out["level"] = "media"
    return out


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


def _route_decide(title: str, description: str = "",
                  config: Optional[dict] = None,
                  base_key: str = "worker_coder",
                  installed: Optional[set[str]] = None,
                  project_root: Optional[str] = None,
                  exclude_files: Optional[set[str]] = None,
                  ) -> tuple[str, str, str]:
    """Corpo della decisione: (model_key, livello, motivi grezzi)."""
    text = f"{title}\n{description}"
    _score, kw_level = estimate_complexity(text)
    level = kw_level
    imp_level = ""
    reason_bits: list[str] = []
    if project_root is not None:
        try:
            imp = estimate_impact(text, project_root, exclude_files)
        except Exception:
            imp = {"level": "", "cited": [], "files": [], "depth": 0,
                   "tests": False}
        imp_level = imp.get("level", "")
        if imp_level:
            level = _max_level(level, imp_level)
            reason_bits.append(
                f"impatto {imp_level} ({len(imp['files'])} file, "
                f"profondità {imp['depth']}, simboli citati: "
                f"{', '.join(imp['cited'][:4]) or '—'})")
        else:
            reason_bits.append("nessun simbolo di progetto citato")
    level = _apply_hysteresis(level)
    if (level == "alta" and kw_level != "alta"
            and imp_level != "alta"):
        reason_bits.append("isteresi: resta heavy dal task precedente")

    if level != "alta":
        return base_key, level, "; ".join(reason_bits)
    cfg = config or {}
    rt = cfg.get("complexity_routing") or {}
    if not rt.get("enabled", True):
        return base_key, level, "; ".join(reason_bits + ["routing off"])
    heavy_key = str(rt.get("heavy_model", "") or "")
    if not heavy_key:
        return base_key, level, "; ".join(reason_bits)
    heavy_cfg = (cfg.get("models") or {}).get(heavy_key) or {}
    heavy_name = str(heavy_cfg.get("name", "") or "")
    if not heavy_name:
        return base_key, level, "; ".join(reason_bits)
    try:
        from CORE import model_knowledge as mk
        if not mk.is_installed(heavy_name, installed):
            return (base_key, level,
                    "; ".join(reason_bits + [
                        f"heavy {heavy_name} NON installato: fallback"]))
    except Exception:
        return base_key, level, "; ".join(reason_bits)
    return heavy_key, level, "; ".join(reason_bits)


def route_model_key(title: str, description: str = "",
                    config: Optional[dict] = None,
                    base_key: str = "worker_coder",
                    installed: Optional[set[str]] = None,
                    project_root: Optional[str] = None,
                    exclude_files: Optional[set[str]] = None,
                    ) -> tuple[str, str, str]:
    """(model_key_da_usare, livello, DECISIONE leggibile).

    Decisione (Fase 7): livello = MAX tra
      - complessità percettiva (keyword: estimate_complexity)
      - IMPATTO REALE sul progetto (estimate_impact, se project_root è
        dato: simboli citati nel task → file toccati/profondità dal DB)
    con ISTERESI: una volta heavy, un task 'media' resta heavy; si torna
    al base solo con un task 'bassa' (niente sfarfallio tra task).

    Il terzo elemento è la frase completa tipo
    "complessità alta → worker_coder_big | impatto alta (…); isteresi…"
    pronta per il dict del risultato e per i log.

    Fail-open: qualsiasi cosa manchi → (base_key, level, motivo).
    """
    key, level, bits = _route_decide(
        title, description, config, base_key, installed,
        project_root, exclude_files)
    heavy = str(((config or {}).get("complexity_routing") or {})
                .get("heavy_model", ""))
    if key != base_key:
        head = f"complessità {level} → {key} (heavy {heavy})"
    elif level == "alta" and heavy:
        head = (f"complessità {level} → {base_key} "
                f"(heavy {heavy} NON installato: fallback)")
    else:
        head = f"complessità {level} → {base_key}"
    return key, level, (f"{head} | {bits}" if bits else head)


def explain(title: str, description: str = "",
            config: Optional[dict] = None,
            base_key: str = "worker_coder",
            installed: Optional[set[str]] = None,
            project_root: Optional[str] = None,
            exclude_files: Optional[set[str]] = None) -> str:
    """Spiegazione leggibile della decisione (per log GUI)."""
    return route_model_key(
        title, description, config, base_key, installed,
        project_root, exclude_files)[2]
