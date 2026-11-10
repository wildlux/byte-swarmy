"""
CORE/loop_detector.py — Rilevamento ripetizioni nell'output dei modelli LLM.

Scopo: evitare che il worker rimanga intrappolato in loop di ripetizione
(stesse frasi/n-grammi che si ripetono, o output con bassissima entropia
indice di testo generato in loop).

Quando viene rilevato un loop, il chiamante deve:
  1. considerare il tentativo come fallito (punteggio zero);
  2. applicare il fallback: nuovo seed, temperatura +0.1, repeat_penalty +0.05.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional


def _ngrams(text: str, n: int) -> list[str]:
    """Ritorna tutti gli n-grammi (token basati su caratteri) di lunghezza n."""
    text = text or ""
    if n <= 0 or len(text) < n:
        return []
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def _compression_ratio(text: str) -> float:
    """
    Rapporto di compressione approssimativo: lunghezza del testo / numero di
    token unici. Valori molto alti indicano testo ripetitivo (bassa entropia).

    Ritorna 0.0 per testo vuoto.
    """
    text = text or ""
    if not text:
        return 0.0
    # Token semplici: sequenze alfanumeriche + punteggiatura isolata
    tokens = re.findall(r"\S+", text)
    if not tokens:
        return 0.0
    unique = len(set(tokens))
    if unique == 0:
        return 0.0
    return len(tokens) / unique


def _repeated_ngram_ratio(text: str, n: int = 5, threshold: int = 3) -> float:
    """
    Frazione di n-grammi che appaiono più di `threshold` volte nel testo.

    Ritorna 0.0 per testo troppo corto per formare n-grammi.
    """
    grams = _ngrams(text, n)
    if not grams:
        return 0.0
    counts = Counter(grams)
    repeated = sum(1 for c in counts.values() if c > threshold)
    return repeated / len(grams)


def detect_loop(
    text: str,
    *,
    ngram_n: int = 5,
    ngram_threshold: int = 3,
    ngram_ratio_limit: float = 0.25,
    compression_limit: float = 4.0,
    min_len: int = 40,
) -> Optional[str]:
    """
    Rileva se `text` contiene un loop di ripetizione.

    Parametri:
        ngram_n: lunghezza degli n-grammi da analizzare (caratteri).
        ngram_threshold: un n-gramma conta come "ripetuto" se appare più di
            questo numero di volte.
        ngram_ratio_limit: se oltre questa frazione di n-grammi è ripetuta,
            si segnala loop.
        compression_limit: se il rapporto di compressione supera questo
            valore, si segnala loop (testo a bassissima entropia).
        min_len: sotto questa lunghezza il testo è troppo corto per essere
            valutato; ritorna None.

    Ritorna:
        None se nessun loop rilevato, altrimenti una stringa che descrive
        il motivo (es. "repeated 5-grams" o "high compression ratio").
    """
    text = text or ""
    if len(text) < min_len:
        return None

    # 1) N-grammi ripetuti
    ratio = _repeated_ngram_ratio(text, n=ngram_n, threshold=ngram_threshold)
    if ratio >= ngram_ratio_limit:
        return f"repeated {ngram_n}-grams (ratio={ratio:.2f})"

    # 2) Alto rapporto di compressione (testo ripetitivo / bassa entropia)
    comp = _compression_ratio(text)
    if comp >= compression_limit:
        return f"high compression ratio ({comp:.1f}x)"

    return None


def is_loop(text: str, **kwargs) -> bool:
    """Ritorna True se `text` contiene un loop di ripetizione."""
    return detect_loop(text, **kwargs) is not None


__all__ = ["detect_loop", "is_loop", "_compression_ratio", "_repeated_ngram_ratio"]
