"""CORE/embedding_retrieval.py — RAG neurale opzionale via Ollama embeddings.

Usa un modello di embedding (es. nomic-embed-text) per retrieval semantico.
Fallback graceful a TF-IDF se il modello non è disponibile o Ollama down.

Consuma RAM: il modello di embedding resta caricato in Ollama. Su macchine
con 4GB, preferire il TF-IDF (CORE.retrieval) — questo modulo è opt-in.

Configurazione: [retrieval] embedding_model = "nomic-embed-text" in config.toml.
Installazione: ollama pull nomic-embed-text
"""
from __future__ import annotations

import json
import math
import urllib.request
import urllib.error
from typing import Optional

DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_HOST = "http://localhost:11434"


def embed_text(text: str, model: str = DEFAULT_MODEL,
               host: str = DEFAULT_HOST) -> Optional[list[float]]:
    """Chiede a Ollama l'embedding di `text`. None se fallisce."""
    try:
        url = host.rstrip("/") + "/api/embeddings"
        data = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                    headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
        emb = obj.get("embedding")
        if isinstance(emb, list) and emb:
            return [float(x) for x in emb]
    except Exception:
        return None
    return None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class EmbeddingRetriever:
    """Retrieval semantico via embeddings Ollama, con fallback TF-IDF."""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST):
        self.model = model
        self.host = host
        self._available: Optional[bool] = None
        self._items: list[tuple[str, str, list[float]]] = []  # (id, text, emb)

    def available(self) -> bool:
        if self._available is None:
            self._available = embed_text("test", self.model, self.host) is not None
        return bool(self._available)

    def add(self, item_id: str, text: str) -> bool:
        """Aggiunge un item. Ritorna True se embedding ottenuto."""
        if not self.available():
            return False
        emb = embed_text(text, self.model, self.host)
        if emb is None:
            return False
        self._items.append((item_id, text, emb))
        return True

    def retrieve(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Top-k per cosine similarity. Vuoto se non disponibile."""
        if not self.available() or not self._items:
            return []
        q_emb = embed_text(query, self.model, self.host)
        if q_emb is None:
            return []
        scored = [(iid, cosine(q_emb, emb)) for iid, _, emb in self._items]
        scored.sort(key=lambda x: -x[1])
        return [(iid, round(sc, 4)) for iid, sc in scored[:k] if sc > 0]


def hybrid_retrieve(query: str, items: list[tuple[str, str]],
                    model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
                    k: int = 5) -> list[tuple[str, float, str]]:
    """Retrieval ibrido: embeddings se disponibili, altrimenti TF-IDF.

    items: lista di (id, text). Ritorna (id, score, text).
    """
    # Prova embeddings
    er = EmbeddingRetriever(model, host)
    if er.available():
        for iid, text in items:
            er.add(iid, text)
        res = er.retrieve(query, k)
        if res:
            id2text = {iid: text for iid, text in items}
            return [(iid, sc, id2text.get(iid, "")) for iid, sc in res]

    # Fallback TF-IDF
    try:
        from CORE.retrieval import TaskRetriever, tokenize, IndexedTask
        tasks = [IndexedTask(task_id=iid, text=text, solution=text,
                             tokens=tokenize(text)) for iid, text in items]
        r = TaskRetriever(tasks)
        r.build()
        res = r.retrieve(query, k)
        return [(tid, sc, sol) for tid, sc, sol in res]
    except Exception:
        return []
