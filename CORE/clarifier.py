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
            lines.append("     0) Altro (specifica)")
        return "\n".join(lines)


@dataclass
class ClarificationResult:
    """Risultato del processo di chiarimento."""
    questions: list[Question] = field(default_factory=list)
    is_clear: bool = True
    enriched_title: str = ""
    enriched_description: str = ""
    cancelled: bool = False  # True se l'utente ha annullato il dialog

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
    # 🆕 P2-6: test runner/marker
    (re.compile(r"\b(scrivi|aggiungi|genera)\s+test\b|\btest\s+(per|su|di)\b", re.I),
     "Quale runner/marker di test vuoi usare?",
     ["pytest (default)", "unittest", "marker @slow/@integration", "coverage report"]),
    # 🆕 P2-6: handler di sistema / servizio
    (re.compile(r"\b(handler\s+di\s+sistema|servizio\s+di\s+sistema|daemon|systemd|cron\s+job|background\s+service)\b", re.I),
     "Quale meccanismo per il servizio di sistema?",
     ["systemd unit", "cron job", "script manuale", "demone Python"]),
    # 🆕 P2-6: formato file di configurazione
    (re.compile(r"\b(file\s+(json|yaml|toml|csv|ini)|configurazione\s+file|config\s+file)\b", re.I),
     "Quale formato per i file di configurazione?",
     ["TOML (config.toml)", "JSON", "YAML", "INI"]),
    # 🆕 Vague software creation: l'utente non specifica lingua/framework/scopo
    (re.compile(r"\b(crea|creami|fammi|realizza|sviluppa|scrivi)\s+(un\s+)?(software|app|programma|tool|applicazione|script)\b", re.I),
     "Il task è vago — quale linguaggio/framework vuoi usare?",
     ["Python", "JavaScript/TypeScript", "Go", "Rust", "Altro (specifica)"]),
]


# ── Window manager / GUI toolkit (Cycle 84) ─────────────────────
# Se il task parla di GUI/interfaccia/finestra ma NON specifica il
# toolkit, è ambiguo: il worker rischierebbe di inventare (PyQt vs
# PySide vs tkinter). Principio: "ask vaghi, then if X do Y" —
# deterministico: toolkit specificato → ref iniettato (Cycle 82-83).
_GUI_TOOLKIT_RE = re.compile(
    r"\b(gui|interfaccia|finestra|window|widget|maschera)\b", re.I)
_GUI_TOOLKIT_NAMES = ("pyqt", "pyside", "tkinter", "qt", "tk", "ttk", "wx",
                      "kivy", "flet", "dearpygui")


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
        # 🆕 Cycle 84: GUI senza toolkit specificato -> chiedi.
        # Deterministico: se nessun toolkit e' menzionato, e' ambiguo.
        if _GUI_TOOLKIT_RE.search(text):
            if not any(t in text for t in _GUI_TOOLKIT_NAMES):
                qid = "Qgui"
                if qid not in seen_ids:
                    seen_ids.add(qid)
                    questions.append(Question(
                        id=qid,
                        text="Quale toolkit GUI/window manager vuoi usare?",
                        options=["PyQt6", "PySide6", "tkinter (stdlib)",
                                 "Altro (specifica)"],
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


def _is_real_answer(value: object) -> bool:
    """Vero solo se l'utente ha dato un contenuto utilizzabile.

    'free' e 'non specificato' sono segnaposto: non devono essere
    spacciati per risposte, ma NON devono nemmeno innescare un nuovo giro
    di domande (il clarifier chiede ogni domanda una sola volta).
    """
    return bool(value) and str(value) not in {"free", "non specificato"}


def parse_answer(answer: str, questions: list[Question]) -> dict:
    """Parsa la risposta dell'utente in un dict {question_id: selected_option}.

    Formati accettati:
      - "1,3,1" → seleziona l'opzione 1 per Q1, 3 per Q2, 1 per Q3
      - "1" → seleziona l'opzione 1 per Q1 (solo se una domanda)
      - "0: testo libero" → risposta libera per la domanda corrispondente
      - "testo libero" → risposta libera (formato del dialog PyQt6)

    Il testo libero viene preservato integralmente, virgole incluse: è il
    valore che `clarify()` inietta nella descrizione passata al modello.
    """
    def looks_like_answer(value: str, question: Question) -> bool:
        return value == "0" or (
            value.isdigit() and 1 <= int(value) <= len(question.options))

    result: dict[str, str] = {}
    raw = str(answer).strip()
    # Con una sola domanda l'intera risposta è il valore: non spezzare
    # una frase libera sulle virgole.
    parts = [p.strip() for p in raw.split(",")] if len(questions) > 1 else [raw]
    idx = 0
    for q in questions:
        if idx >= len(parts):
            result[q.id] = "non specificato"
            continue
        val = parts[idx]
        idx += 1
        if not val:
            result[q.id] = "non specificato"
        elif val == "0":
            result[q.id] = "free"
        elif re.match(r"^0\s*[:.)\-]\s*", val):
            result[q.id] = re.sub(r"^0\s*[:.)\-]\s*", "", val).strip() or "free"
        elif val.isdigit() and 1 <= int(val) <= len(q.options):
            result[q.id] = q.options[int(val) - 1]
        else:
            result[q.id] = val
        # Il testo libero può contenere virgole: consuma i pezzi seguenti
        # finché non assomigliano alla risposta della domanda successiva.
        if not _is_real_answer(result[q.id]):
            continue
        if result[q.id] in q.options:
            continue
        while (idx < len(parts) and idx < len(questions)
               and not looks_like_answer(parts[idx], questions[idx])):
            result[q.id] = f"{result[q.id]}, {parts[idx]}"
            idx += 1
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
    """Chiede le ambiguità relative al task, una sola volta ciascuna.

    ask_fn: callable che riceve il testo formattato delle domande e
    restituisce la risposta dell'utente (str). Se None, usa input().

    Il vecchio ciclo ri-rilevava le ambiguità sul testo *arricchito*: la
    frase originale restava presente, quindi la stessa domanda veniva
    riposta fino a 5 volte anche dopo una risposta valida. Ora il set di
    domande è calcolato una sola volta sul task originale e arricchito con
    le risposte; il testo libero dell'utente arriva così al modello senza
    ripetizioni.

    Fail-open: senza stdin (o su EOF/KeyboardInterrupt) restituisce il task
    originale senza chiarimento. `is_clear` resta False se mancano risposte
    utilizzabili, ma l'esecuzione procede comunque.
    """
    questions = detect_ambiguity(task_title, task_description)
    if not questions:
        return ClarificationResult(
            questions=[], is_clear=True,
            enriched_title=task_title,
            enriched_description=task_description)

    if ask_fn is None:
        try:
            ask_fn = lambda text: input(text)
        except Exception:
            return ClarificationResult(
                questions=[], is_clear=True,
                enriched_title=task_title,
                enriched_description=task_description)

    try:
        answer = ask_fn(format_questions(questions))
    except (EOFError, KeyboardInterrupt):
        return ClarificationResult(
            questions=questions, is_clear=False, cancelled=True,
            enriched_title=task_title,
            enriched_description=task_description)

    # Annullato dall'utente (dialog chiuso o risposta None/vuota)
    if answer is None or str(answer).strip() == "":
        return ClarificationResult(
            questions=questions, is_clear=False, cancelled=True,
            enriched_title=task_title,
            enriched_description=task_description)

    answers = parse_answer(answer, questions)
    result = clarify(task_title, task_description, answers)
    result.questions = questions
    result.is_clear = all(_is_real_answer(answers.get(q.id)) for q in questions)
    return result


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
