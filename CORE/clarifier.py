"""
CORE/clarifier.py — Fase 9: rilevamento ambiguità e domande interattive.

Quando un task è complesso o richiede decisioni importanti (architettura,
linguaggio, docker, kubernetes, servizi), il sistema identifica i punti
ambigui e genera domande con opzioni numerate. L'utente risponde → il
sistema raffina → nuove domande se necessario → solo quando non ci sono
più dubbi, inizia il lavoro.

API:
  detect_ambiguity(task_title, task_description="") -> list[Question]
      Analizza il task e restituisce le domande con opzioni.

  format_questions(questions) -> str
      Formatta le domande per CLI/GUI.

  parse_answer(answer, questions) -> dict
      Parsa la risposta dell'utente (es. "1,3,1") in un dict.

  clarify(task, answers) -> dict
      Arricchisce il task con le risposte dell'utente.

  is_clear(task) -> bool
      True se il task non ha ambiguità rilevanti.

Fail-open ovunque: se il rilevamento fallisce, il task procede normalmente.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Question:
    """Una domanda con opzioni numerate."""
    id: str
    text: str
    options: list[str] = field(default_factory=list)
    allow_free: bool = True  # permette risposta libera

    def format(self) -> str:
        lines = [f"  {self.id}. {self.text}"]
        for i, opt in enumerate(self.options, 1):
            lines.append(f"     {i}) {opt}")
        if self.allow_free:
            lines.append(f"     0) Altro (specifica)")
        return "\n".join(lines)


@dataclass
class ClarificationResult:
    """Risultato del processo di chiarimento."""
    questions: list[Question] = field(default_factory=list)
    is_clear: bool = True
    enriched_title: str = ""
    enriched_description: str = ""

    def has_questions(self) -> bool:
        return len(self.questions) > 0


# ── Pattern di ambiguità ──────────────────────────────────────────────
# Ogni pattern è una tupla (regex, lista di (keyword, opzioni)).
# Se il regex matcha nel testo del task, viene generata una domanda.

_AMBIGUITY_PATTERNS: list[tuple[re.Pattern, str, list[str]]] = [
    # Architettura / framework
    (re.compile(r"\b(rifattorizz\w*|refactor\w*|riscrivi\w*|riorganizz\w*)\b", re.I),
     "Quale architettura/framework vuoi usare?",
     ["Mantieni l'attuale", "MVC", "Microservizi", "Monolite modulare"]),
    # Linguaggio
    (re.compile(r"\b(migra|migrazione|converti|porta)\b.*\b(python|java|go|rust|node|js|ts)\b", re.I),
     "Confermi il linguaggio/framework target?",
     ["Python", "JavaScript/TypeScript", "Go", "Rust", "Java"]),
    # Database
    (re.compile(r"\b(database|db|persistenza|storage)\b", re.I),
     "Quale database/storage vuoi usare?",
     ["SQLite (locale)", "PostgreSQL", "MongoDB", "File JSON", "Nessuno (in-memory)"]),
    # Docker / container
    (re.compile(r"\b(docker|container|kubernetes|k8s|deploy)\b", re.I),
     "Quale strategia di deployment?",
     ["Docker Compose (locale)", "Kubernetes", "Nessuno (script diretto)", "Altro"]),
    # Autenticazione
    (re.compile(r"\b(auth|autenticazione|login|oauth|jwt|token)\b", re.I),
     "Quale meccanismo di autenticazione?",
     ["OAuth2 (Google)", "OAuth2 (GitHub)", "JWT locale", "Sessioni cookie", "Dual auth (password + OAuth)"]),
    # API / servizi
    (re.compile(r"\b(api|endpoint|servizio|service|gateway)\b", re.I),
     "Quale formato API?",
     ["REST (JSON)", "gRPC", "GraphQL", "WebSocket", "CLI"]),
    # Concorrenza
    (re.compile(r"\b(concorren|thread|async|parallelo|worker)\b", re.I),
     "Quale modello di concorrenza?",
     ["Sincrono (sequenziale)", "Threading", "Async/await", "Multiprocessing"]),
    # Sicurezza
    (re.compile(r"\b(sicurezza|security|auth|permessi|rbac)\b", re.I),
     "Livello di sicurezza richiesto?",
     ["Base (validazione input)", "Standard (auth + RBAC)", "Enterprise (audit + encryption)", "Massimo (zero-trust)"]),
]


def detect_ambiguity(task_title: str, task_description: str = "") -> list[Question]:
    """Analizza il task e restituisce le domande con opzioni.

    Fail-open: se il rilevamento fallisce, restituisce lista vuota
    (il task procede senza chiarimento).
    """
    try:
        text = f"{task_title}\n{task_description}".lower()
        questions: list[Question] = []
        seen_ids: set[str] = set()
        for i, (pattern, qtext, options) in enumerate(_AMBIGUITY_PATTERNS):
            if pattern.search(text):
                qid = f"Q{i+1}"
                if qid not in seen_ids:
                    seen_ids.add(qid)
                    questions.append(Question(
                        id=qid,
                        text=qtext,
                        options=list(options),
                    ))
        return questions
    except Exception:
        return []


def is_clear(task_title: str, task_description: str = "") -> bool:
    """True se il task non ha ambiguità rilevanti."""
    return len(detect_ambiguity(task_title, task_description)) == 0


def format_questions(questions: list[Question]) -> str:
    """Formatta le domande per CLI/GUI."""
    if not questions:
        return ""
    lines = ["Ho bisogno di chiarire alcuni punti prima di iniziare:\n"]
    for q in questions:
        lines.append(q.format())
        lines.append("")
    lines.append("Rispondi con i numeri (es. 1,3,1) oppure 0 per specificare:")
    return "\n".join(lines)


def parse_answer(answer: str, questions: list[Question]) -> dict:
    """Parsa la risposta dell'utente in un dict {question_id: selected_option}.

    Formati accettati:
      - "1,3,1" → seleziona l'opzione 1 per Q1, 3 per Q2, 1 per Q3
      - "1" → seleziona l'opzione 1 per Q1 (solo se una domanda)
      - "0: testo libero" → risposta libera per la domanda corrispondente
    """
    result: dict[str, str] = {}
    parts = [p.strip() for p in str(answer).split(",")]
    for i, q in enumerate(questions):
        if i < len(parts):
            val = parts[i]
            if not val:
                result[q.id] = "non specificato"
            elif val == "0":
                result[q.id] = "free"
            elif val.isdigit() and 1 <= int(val) <= len(q.options):
                result[q.id] = q.options[int(val) - 1]
            else:
                result[q.id] = val  # testo libero
        else:
            result[q.id] = "non specificato"
    return result


def clarify(task_title: str, task_description: str = "",
            answers: Optional[dict] = None) -> "ClarificationResult":
    """Arricchisce il task con le risposte dell'utente.

    Se answers è None o vuoto, rileva le ambiguità e restituisce le domande.
    Se answers è fornito, costruisce il task arricchito.
    """
    questions = detect_ambiguity(task_title, task_description)
    result = ClarificationResult(questions=questions, is_clear=len(questions) == 0)

    if not questions:
        result.enriched_title = task_title
        result.enriched_description = task_description
        return result

    if not answers:
        result.enriched_title = task_title
        result.enriched_description = task_description
        return result

    # Arricchisci il task con le risposte
    enriched_parts = [task_title, task_description]
    enriched_parts.append("\n## Chiarimenti dell'utente:")
    for q in questions:
        ans = answers.get(q.id, "non specificato")
        enriched_parts.append(f"- {q.text} → {ans}")
        # Q4: salva la preferenza
        try:
            from CORE.persistent_memory import record_preference
            record_preference(q.text[:60], ans)
        except Exception:
            pass

    result.enriched_title = task_title
    result.enriched_description = "\n".join(enriched_parts)
    result.is_clear = True  # dopo le risposte, consideriamo chiarito
    return result


def clarify_loop(task_title: str, task_description: str = "",
                 ask_fn=None) -> "ClarificationResult":
    """Loop di chiarimento: continua a chiedere finché non è chiaro.

    ask_fn: callable che riceve il testo formattato delle domande e
    restituisce la risposta dell'utente (str). Se None, usa input().

    Fail-open: se ask_fn è None e non c'è stdin, restituisce il task
    originale senza chiarimento.
    """
    if ask_fn is None:
        try:
            ask_fn = lambda text: input(text)
        except Exception:
            # No stdin: procedi senza chiarimento
            return ClarificationResult(
                questions=[], is_clear=True,
                enriched_title=task_title,
                enriched_description=task_description)

    current_title = task_title
    current_desc = task_description
    max_rounds = 5

    for _ in range(max_rounds):
        questions = detect_ambiguity(current_title, current_desc)
        if not questions:
            return ClarificationResult(
                questions=[], is_clear=True,
                enriched_title=current_title,
                enriched_description=current_desc)

        text = format_questions(questions)
        try:
            answer = ask_fn(text)
        except (EOFError, KeyboardInterrupt):
            # Utente interrompe: procedi senza chiarimento
            return ClarificationResult(
                questions=questions, is_clear=False,
                enriched_title=current_title,
                enriched_description=current_desc)

        answers = parse_answer(answer, questions)
        enriched = clarify(current_title, current_desc, answers)
        current_title = enriched.enriched_title
        current_desc = enriched.enriched_description

    # Dopo max_rounds, procedi comunque
    return ClarificationResult(
        questions=[], is_clear=True,
        enriched_title=current_title,
        enriched_description=current_desc)


def cli_interactive(task_title: str, task_description: str = "") -> None:
    """Modalità CLI interattiva per il chiarimento."""
    print(f"\nTask: {task_title}\n")
    result = clarify_loop(task_title, task_description)
    print("\n--- Task arricchito ---")
    print(f"Titolo: {result.enriched_title}")
    print(f"Descrizione:\n{result.enriched_description}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        prog="python -m CORE.clarifier",
        description="Fase 9: chiarimento interattivo di un task.")
    parser.add_argument("title", help="Titolo del task.")
    parser.add_argument("--description", "-d", default="", help="Descrizione.")
    args = parser.parse_args()
    cli_interactive(args.title, args.description)
