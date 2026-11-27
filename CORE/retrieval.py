"""CORE/retrieval.py — retrieval TF-IDF di soluzioni passate (Fase F).

NO RAG neurale (verdetto Cycle 78): TF-IDF/keyword su task già chiusi.
Dato un task nuovo, ritorna i task più simili già risolti con la loro
soluzione (output), per iniettarli come esempio nel prompt.

Stdlib only, zero LLM, zero rete.
"""

from __future__ import annotations

import math
import sqlite3
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# Stop words italiane + inglesi (comuni, a basso valore semantico).
_STOP_WORDS = frozenset({
    "il", "lo", "la", "i", "gli", "le", "un", "una", "uno", "di", "a",
    "da", "in", "con", "su", "per", "tra", "fra", "e", "o", "ma", "se",
    "che", "chi", "cui", "non", "piu", "come", "quando", "dove", "cosa",
    "del", "della", "dei", "delle", "al", "alla", "ai", "alle", "dal",
    "dalla", "nei", "nelle", "sul", "sulla", "questo", "questa", "questi",
    "queste", "quello", "quella", "quelli", "quelle", "essere", "avere",
    "fare", "dire", "andare", "potere", "volere", "dovere", "sapere",
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "once", "here", "there", "all", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "can", "will", "just", "should",
    "now", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "of", "it", "its", "this", "that",
    "these", "those", "i", "me", "my", "we", "our", "you", "your", "he",
    "him", "his", "she", "her", "they", "them", "their", "what", "which",
    "who", "whom", "how", "why",
})

# Suffissi comuni da rimuovere (stemming leggero, italiano + inglese).
_SUFFIXES = ("mente", "zione", "zioni", "mento", "menti", "ità", "ivo",
             "iva", "ivi", "ive", "ato", "ata", "ati", "ate", "uto",
             "uta", "uti", "ute", "ando", "endo", "tion", "sion", "ment",
             "ness", "able", "ible", "ing", "ed", "es", "s", "er", "est")


def _stem(tok: str) -> str:
    """Stemming leggero: rimuove suffissi comuni se il risultato ha >=3 char."""
    if len(tok) < 5:
        return tok
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return tok


def tokenize(text: str) -> list[str]:
    """Tokenizzazione migliorata: lowercase, split, stop words, stemming leggero."""
    raw = [t for t in re.findall(r"[a-z0-9_]+", (text or "").lower())
           if len(t) >= 2]
    out = []
    for t in raw:
        if t in _STOP_WORDS:
            continue
        st = _stem(t)
        if len(st) >= 2 and st not in _STOP_WORDS:
            out.append(st)
    return out


@dataclass
class IndexedTask:
    task_id: str
    text: str
    solution: str
    tokens: list[str]


class TaskRetriever:
    """Indice TF-IDF in memoria su task chiusi."""

    def __init__(self, tasks: Iterable[IndexedTask] | None = None):
        self.tasks: list[IndexedTask] = list(tasks or [])
        self._idf: dict[str, float] = {}
        self._built = False

    def build(self) -> None:
        """Calcola IDF sui task presenti."""
        n = len(self.tasks)
        if n == 0:
            self._idf = {}
            self._built = True
            return
        df: Counter = Counter()
        for t in self.tasks:
            for tok in set(t.tokens):
                df[tok] += 1
        self._idf = {tok: math.log((1 + n) / (1 + dfc)) + 1.0
                     for tok, dfc in df.items()}
        self._built = True

    def _ensure(self) -> None:
        if not self._built:
            self.build()

    def _tfidf(self, tokens: list[str]) -> dict[str, float]:
        self._ensure()
        tf = Counter(tokens)
        total = len(tokens) or 1
        return {tok: (cnt / total) * self._idf.get(tok, 1.0)
                for tok, cnt in tf.items()}

    def retrieve(self, query: str, k: int = 3) -> list[tuple[str, float, str]]:
        """Ritorna i top-k task simili: (task_id, score, solution)."""
        self._ensure()
        if not self.tasks or k <= 0:
            return []
        q_vec = self._tfidf(tokenize(query))
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        scored: list[tuple[float, IndexedTask]] = []
        for t in self.tasks:
            d_vec = self._tfidf(t.tokens)
            d_norm = math.sqrt(sum(v * v for v in d_vec.values())) or 1.0
            dot = sum(q_vec.get(tok, 0.0) * d_vec.get(tok, 0.0)
                      for tok in q_vec)
            score = dot / (q_norm * d_norm)
            scored.append((score, t))
        scored.sort(key=lambda x: (-x[0], x[1].task_id))
        out = []
        for score, t in scored[:k]:
            if score <= 0:
                continue
            out.append((t.task_id, round(score, 4), t.solution))
        return out

    def format_results(self, results: list[tuple[str, float, str]],
                       max_chars: int = 1200) -> str:
        if not results:
            return "Nessun task simile trovato."
        blocks = []
        for tid, score, sol in results:
            sol = (sol or "").strip()
            if len(sol) > max_chars:
                sol = sol[:max_chars] + "\n... (troncato)"
            blocks.append(f"--- task {tid} (score {score}) ---\n{sol}")
        return "\n\n".join(blocks)


def build_from_pairs(pairs: Iterable[tuple[str, str, str]]) -> TaskRetriever:
    """pairs: (task_id, text, solution)."""
    tasks = [IndexedTask(task_id=tid, text=text, solution=sol,
                        tokens=tokenize(text))
             for tid, text, sol in pairs]
    r = TaskRetriever(tasks)
    r.build()
    return r


def _resolve_queue_db(tasks_dir=None, state_dir=None) -> Path | None:
    """Trova queue.db (data/tasks o tasks/ o tasks_dir)."""
    candidates = []
    if tasks_dir:
        candidates.append(Path(tasks_dir) / "queue.db")
    if state_dir:
        candidates.append(Path(state_dir).parent / "tasks" / "queue.db")
    root = Path(__file__).resolve().parent.parent
    candidates += [root / "data" / "tasks" / "queue.db",
                   root / "tasks" / "queue.db"]
    for c in candidates:
        if c.exists():
            return c
    return None


def build_from_queue_db(tasks_dir=None, state_dir=None, db_path=None) -> TaskRetriever:
    """Costruisce l'indice dai task chiusi in queue.db.

    text = title + description; solution = result (troncato a 500 dal DB).
    db_path: override esplicito (per test/isolamento).
    """
    if db_path is not None:
        db = Path(db_path)
        if not db.exists():
            return TaskRetriever([])
    else:
        db = _resolve_queue_db(tasks_dir, state_dir)
        if db is None:
            return TaskRetriever([])
    pairs = []
    try:
        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, title, description, result FROM tasks "
                "WHERE status = 'done'").fetchall()
    except sqlite3.Error:
        return TaskRetriever([])
    for r in rows:
        tid = r["id"]
        text = f"{r['title'] or ''}\n{r['description'] or ''}"
        sol = r["result"] or ""
        if not text.strip():
            continue
        pairs.append((tid, text, sol))
    return build_from_pairs(pairs)


def build_from_corpus(state_dir) -> TaskRetriever:
    """Costruisce l'indice dal corpus di feedback (output completi)."""
    from CORE import feedback_corpus as fc
    base = Path(state_dir) / "feedback_corpus"
    pairs = []
    if base.exists():
        for f in base.glob("*.jsonl"):
            for t in fc.load_task(f.stem, state_dir=state_dir):
                text = f"{t.title}\n{t.description}"
                if t.refs:
                    text += "\n" + " ".join(t.refs)
                pairs.append((t.task_id, text, t.output))
    # dedup per task_id: tieni l'ultimo (più recente)
    seen = set()
    uniq = []
    for tid, text, sol in reversed(pairs):
        if tid in seen:
            continue
        seen.add(tid)
        uniq.append((tid, text, sol))
    uniq.reverse()
    return build_from_pairs(uniq)
