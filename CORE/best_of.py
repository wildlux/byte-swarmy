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


@dataclass(frozen=True)
class JudgeResult:
    """Esito deterministico del gate-giudice (nessuna preferenza umana)."""
    selected_index: int | None
    selected_code: str
    reason: str
    verdicts: tuple[SlotVerdict, ...]
    evaluated: int
    limit: int

    @property
    def ok(self) -> bool:
        return self.selected_index is not None


def judge_candidates(codes: list[str], refs_by_index: dict[int, list[str]],
                     kinds: list[str], best_of: int = 1) -> JudgeResult:
    """B1: gate-giudice con N candidati finti o reali — zero LLM.

    Valuta al massimo `best_of` candidati, nell'ordine dato; vince il primo
    che passa il gate. Se nessuno passa, `selected_index=None` e
    `reason='all_rejected'`. La scelta è una funzione pura degli argomenti.
    """
    limit = min(8, max(1, int(best_of)))
    subset = list(codes[:limit])
    try:
        evaluated_candidates = evaluate_candidates(
            subset, refs_by_index, kinds[:limit])
    except ValueError:
        return JudgeResult(None, "", "kinds_mismatch", (), len(subset), limit)
    winner = select_passing(evaluated_candidates)
    verdicts = tuple(c.verdict for c in evaluated_candidates)
    if winner is None:
        return JudgeResult(None, "", "all_rejected", verdicts,
                           len(evaluated_candidates), limit)
    return JudgeResult(winner.index, winner.code, "first_passing", verdicts,
                       len(evaluated_candidates), limit)


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
