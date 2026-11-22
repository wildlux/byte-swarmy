"""
CORE/override_guard.py — validatore deterministico degli override utente.

`auto_skill` e `auto_tool` leggono keyword extra da file JSON in `state/`
(gitignored). Prima di B3 quei file erano accettati così come stavano: una
chiave sbagliata, 50 keyword o duplicati entravano silenziosamente nel
prompt. Questo modulo applica poche regole verificabili:

- l'override DEVE essere un oggetto JSON `{chiave: [keyword, ...]}`;
- la chiave DEVE essere nota (skill/tool esistenti);
- al massimo 4 keyword per chiave (stesso cap di auto-skill/auto-tool);
- nessun duplicato (confronto normalizzato: minuscole, senza accenti);
- keyword non vuote, testuali, < 80 caratteri, senza caratteri di controllo.

Fail-open: file mancante → override vuoti, nessun errore. JSON invalido o
voci invalide → la singola voce viene scartata e un `Issue` con codice e
messaggio chiaro finisce nel report (e nel log del caller). Zero LLM, rete o
I/O al di fuori del file passato.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

MAX_KEYWORDS = 4
MAX_KEYWORD_CHARS = 80
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Issue:
    key: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"key": self.key, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class ValidationResult:
    source: str
    overrides: dict[str, list[str]]
    issues: tuple[Issue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "ok": self.ok,
            "overrides": {k: list(v) for k, v in self.overrides.items()},
            "issues": [i.to_dict() for i in self.issues],
        }

    def markdown(self) -> str:
        lines = [
            f"### Override `{Path(self.source).name or self.source}` — "
            f"{'✅ VALIDO' if self.ok else '🔴 INVALIDO'}",
            "",
            f"- voci valide: {len(self.overrides)}",
            f"- problemi: {len(self.issues)}",
        ]
        for i in self.issues:
            lines.append(f"- `{i.code}` ({i.key or '-'}): {i.message}")
        return "\n".join(lines)


def validate_overrides(data, known_keys, source: str = "") -> ValidationResult:
    """Valida e sanizza un override già letto come oggetto Python."""
    from CORE.auto_skill import normalize

    known = {str(k) for k in known_keys}
    issues: list[Issue] = []
    clean: dict[str, list[str]] = {}

    if not isinstance(data, dict):
        return ValidationResult(
            source, {}, (Issue("", "root_type",
                               "Il file deve contenere un oggetto JSON "
                               "{chiave: [keyword, ...]}."),))

    for key in sorted(data, key=str):
        name = str(key).strip()
        if not name:
            issues.append(Issue("", "empty_key", "Chiave vuota."))
            continue
        if name not in known:
            sample = ", ".join(sorted(known)[:6]) or "(nessuna)"
            issues.append(Issue(name, "unknown_key",
                                f"Chiave sconosciuta; chiavi note: {sample}."))
            continue
        value = data[key]
        if not isinstance(value, list):
            issues.append(Issue(name, "bad_type",
                                "Il valore deve essere una lista di stringhe."))
            continue

        words: list[str] = []
        seen: set[str] = set()
        for raw in value:
            if not isinstance(raw, str):
                issues.append(Issue(name, "bad_keyword",
                                    "Keyword non testuale, scartata."))
                continue
            word = raw.strip()
            norm = normalize(word)
            if not norm or len(word) > MAX_KEYWORD_CHARS or _CONTROL.search(word):
                issues.append(Issue(name, "bad_keyword",
                                    f"Keyword non valida: {word[:40]!r}."))
                continue
            if norm in seen:
                issues.append(Issue(name, "duplicate",
                                    f"Keyword duplicata: {word!r}."))
                continue
            seen.add(norm)
            words.append(word)

        if not words:
            issues.append(Issue(name, "empty_list",
                                "Nessuna keyword valida per questa chiave."))
        elif len(words) > MAX_KEYWORDS:
            issues.append(Issue(name, "too_many",
                                f"{len(words)} keyword: massimo {MAX_KEYWORDS}."))
        else:
            clean[name] = words

    return ValidationResult(source, clean, tuple(issues))


def load_validated(path, known_keys) -> ValidationResult:
    """Legge `path` e valida: file assente = ok con override vuoti."""
    p = Path(path)
    source = str(p)
    if not p.exists():
        return ValidationResult(source, {}, ())
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return ValidationResult(
            source, {}, (Issue("", "invalid_json",
                               f"JSON non leggibile: {str(e)[:160]}"),))
    return validate_overrides(data, known_keys, source)
