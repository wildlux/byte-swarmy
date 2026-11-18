"""CORE/best_of.py — best-of-N con il gate deterministico come giudice (Fase D-15).

Il gate (slot/asssembler/import-check) è l'unica autorità: quando
`best_of_n > 1` per un task, il flusso genera N candidati e sceglie il
primo che passa il gate (indice più basso). Se nessuno passa, la task
prosegue come un task corretto (correction loop sul candidato scelto o
fallimento pulito) — mai "il migliore a occhio".

Regole:
- candidato -> gate -> se ok: selezionato (scelto). Il gate non è un
  pregiudizio: è un criterio deterministico.
- se nessun candidato passa: rejection con lista dei candidati.
"""

from __future__ import annotations

from dataclasses import dataclass

from CORE.slot_gate import ALLOWED_KINDS, SlotVerdict, gate_slot


@dataclass(frozen=True)
class Candidate:
    index: int
    code: str
    verdict: SlotVerdict


def evaluate_candidates(codes: list[str], refs_by_index: dict[int, list[str]],
                       kinds: list[str]) -> list[Candidate]:
    """Valuta una lista di candidati in ordine (indice 0 = primo)."""
    if len(codes) != len(kinds):
        raise ValueError(
            f"candidates/kinds mismatch: {len(codes)} codici vs {len(kinds)} kind")
    out: list[Candidate] = []
    for i, code in enumerate(codes):
        kind = kinds[i] if i < len(kinds) else "function"
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"kind sconosciuto: {kind}")
        out.append(Candidate(index=i, code=code, verdict=gate_slot(
            code, refs=refs_by_index.get(i, []), kind=kind)))
    return out


def select_passing(candidates: list[Candidate]) -> Candidate | None:
    """Il gate come giudice: il primo candidato che passa vince."""
    for c in candidates:
        if c.verdict.ok:
            return c
    return None


def select_rejected(candidates: list[Candidate]) -> list[Candidate]:
    """Tutti i candidati, con il loro verdetto (per report/log)."""
    return list(candidates)
