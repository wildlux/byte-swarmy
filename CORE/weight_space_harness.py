"""
weight_space_harness.py — Harness "Weight-Space Programming" (estremamente beta).

Ispirato a "Sparks of Weight-Space Programming: LLMs can natively read &
write neural network weights" (Takehi, Teoh, Zhang, Khattab — MIT CSAIL,
novembre 2026, https://rikiyat.github.io/blog/weight-space-programming/).

Il paper mostra:
  (a) gli LLM possono LEGGERE il comportamento dei pesi grezzi (esperimenti 1-3);
  (b) possono CORREGGERE i pesi senza gradienti (esperimenti 4, 8) — il fallimento
      tipico dei modelli piccoli sono i LOOP (ed. 8, Qwen3.5-0.8B: 93% delle
      risposte andava in loop fino al limite dei token).

Questo harness (versione minimale, per macchine 4GB):
  1. "Legge il file dei pesi" (header GGUF: architettura, nome, tensori).
  2. Attacca i pesi a un decoder locale (Ollama) e prova il modello su
     problemi comuni di programmazione: loop di somma, fizzbuzz, conteggio,
     inversione, fix di loop infiniti e off-by-one.
  3. Misura la RIPETIZIONE dell'output (metrica loop, ispirata all'ed. 8):
     output che si ripete = probabile modello bloccato in loop.
  4. Produce un report JSON in state/weight_space/ con punteggio e verdetto.

Sicurezza: il codice generato NON viene mai eseguito — valutazione statica.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Optional, Callable

from CORE.regex_controller import RegexController, DEFAULT_PATTERNS, number_after_label, last_number
from CORE.constants import OLLAMA_HOST

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "state" / "weight_space"

# ─────────────────────────────────────────────────────────────────────
# Problemi comuni da programmatore (con check statico)
# ─────────────────────────────────────────────────────────────────────
# Ogni problema chiede un output verificabile: number su "RISULTATO: x"
# oppure keyword obbligatorie nel codice. Nessuna esecuzione del codice.

# Controllore regex riusabile per i check dell'harness.
# (loop_increment e off_by_one_fix sono già nei default di regex_controller)
_HARNESS_RE = RegexController(DEFAULT_PATTERNS)
_HARNESS_RE.add("fizz", r"\bFizz\b")
_HARNESS_RE.add("buzz", r"\bBuzz\b")
_HARNESS_RE.add("numero_7", r"(?m)^\s*7\s*$")
_HARNESS_RE.add(
    "loop_increment_fix",
    r"(?i)(i\s*\+=\s*1|i\s*=\s*i\s*\+\s*1|i\s*=\s*[0-9]+\s*\+\s*1|incrementa|increment)",
)

PROBLEMS = [
    {
        "id": "sum_loop",
        "title": "Loop di somma 1..100",
        "prompt": (
            "Scrivi in Python un ciclo che somma i numeri da 1 a 100.\n"
            "Alla fine rispondi SOLO su questa riga di riepilogo:\n"
            "RISULTATO: <numero>"
        ),
        "check": lambda out: _expected_number(out, 5050),
        "hint": "atteso RISULTATO: 5050",
    },
    {
        "id": "fizzbuzz",
        "title": "FizzBuzz (multipli di 3 e 5)",
        "prompt": (
            "Rispondi con l'output di FizzBuzz per i numeri da 1 a 15, "
            "uno per riga (numero, Fizz, Buzz o FizzBuzz)."
        ),
        "check": lambda out: (
            "FizzBuzz" in out and
            _HARNESS_RE.search("fizz", out) is not None and
            _HARNESS_RE.search("buzz", out) is not None and
            _HARNESS_RE.search("numero_7", out) is not None
        ),
        "hint": "atteso: FizzBuzz, Fizz, Buzz e '7' al primo posto numerico",
    },
    {
        "id": "count_loop",
        "title": "Conteggio elementi (loop)",
        "prompt": (
            "Dato nums = [3, 7, 1, 7, 7, 2], conta quante volte appare 7 "
            "usando un ciclo. Rispondi SOLO:\nRISULTATO: <numero>"
        ),
        "check": lambda out: _expected_number(out, 3),
        "hint": "atteso RISULTATO: 3",
    },
    {
        "id": "reverse",
        "title": "Inversione stringa",
        "prompt": (
            "Scrivi il contenuto della stringa 'rotinom' al contrario, "
            "cioè leggibile da destra verso sinistra. Rispondi SOLO:\n"
            "RISULTATO: <testo>"
        ),
        "check": lambda out: _expected_word(out, "monitor"),
        "hint": "atteso RISULTATO: monitor",
    },
    {
        "id": "fix_infinite_loop",
        "title": "Fix loop infinito",
        "prompt": (
            "Questo codice non termina mai:\n\n"
            "    i = 0\n"
            "    while i < 10:\n"
            "        print(i)\n\n"
            "Correggilo con la MINIMA modifica. Rispondi con il codice "
            "corretto completo."
        ),
        "check": lambda out: _HARNESS_RE.search("loop_increment_fix", out) is not None,
        "hint": "attesa l'istruzione di incremento di i (es. i += 1)",
    },
    {
        "id": "off_by_one",
        "title": "Off-by-one negli indici",
        "prompt": (
            "Questo errore deve iterare su TUTTI i numeri da 1 a n inclusi:\n\n"
            "    for i in range(1, n):\n"
            "        total += i\n\n"
            "Correggilo. Rispondi con il codice corretto."
        ),
        "check": lambda out: _HARNESS_RE.search("off_by_one_fix", out) is not None,
        "hint": "atteso range(1, n + 1)",
    },
]

REPEAT_METRIC_NOTE = (
    "metrica loop (ispirata all'Esperimento 8 del paper): ratio di linee "
    "duplicate consecutive nell'output — modello che si ripete = loop"
)


# ─────────────────────────────────────────────────────────────────────
# Check helper
# ─────────────────────────────────────────────────────────────────────

def _expected_number(text: str, expected: int) -> bool:
    val = number_after_label(text, "RISULTATO")
    if val is not None:
        return val == expected
    # fallback: prendi l'ultimo numero isolato fuori dal prompt ripetuto
    nums = last_number(text)
    return nums is not None and nums == expected


def _expected_word(text: str, expected: str) -> bool:
    matches = re.findall(r"RISULTATO\s*[:=]\s*(.+)", text)
    if matches:
        val = matches[-1].strip().strip("`'\"")
        return val.lower() == expected
    return bool(re.search(rf"\b{re.escape(expected)}\b", text.lower()))


# ─────────────────────────────────────────────────────────────────────
# Metrica loop / ripetizione (ispirata Esperimento 8 del paper)
# ─────────────────────────────────────────────────────────────────────

def repetition_metrics(text: str, ngram: int = 4, window: int = 40) -> dict:
    """Stima quanto l'output 'loopa'.

    - duplicate_line_ratio: frazione di righe non vuote ripetute
      (modello che stampa la stessa riga all'infinito).
    - tail_selfsimilarity: sovrapposizione della coda con se stessa
      (repetizione di frasi/blocchi).
    Ritorna {"duplicate_line_ratio", "tail_selfsimilarity", "loops_like"}.
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) >= 3:
        from collections import Counter
        c = Counter(lines)
        dup = sum(cnt for ln, cnt in c.items() if cnt > 1)
        dup_ratio = dup / len(lines)
    else:
        dup_ratio = 0.0

    tail = " ".join(lines[-window:]) if lines else ""
    n = len(tail)
    tail_sim = 0.0
    if n >= 20:
        low = tail.lower()
        for shift in range(3, max(4, n // 2)):
            seg_len = n - shift
            if seg_len < 8:
                continue
            cur = best_run = 0
            for a, b in zip(low[:-shift], low[shift:]):
                if a == b:
                    cur += 1
                    best_run = max(best_run, cur)
                else:
                    cur = 0
            # rapporto tra la lunghezza della run sovrapposta e quella confrontabile
            tail_sim = max(tail_sim, min(1.0, best_run / max(1, seg_len)))

    loops_like = dup_ratio >= 0.33 and len(lines) >= 6 or tail_sim >= 0.55
    return {
        "duplicate_line_ratio": round(dup_ratio, 3),
        "tail_selfsimilarity": round(tail_sim, 3),
        "loops_like": bool(loops_like),
    }


# ─────────────────────────────────────────────────────────────────────
# Generazione via Ollama (sostituibile nei test con generate_fn)
# ─────────────────────────────────────────────────────────────────────

def ollama_generate(model: str, prompt: str, host: str = OLLAMA_HOST,
                    num_predict: int = 512, timeout: int = 180) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": num_predict,
                    "num_ctx": 3072, "repeat_penalty": 1.1},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("response", "")


# ─────────────────────────────────────────────────────────────────────
# Harness
# ─────────────────────────────────────────────────────────────────────

def run_harness(model_name: str, host: str = OLLAMA_HOST,
                generate_fn: Optional[Callable[..., str]] = None,
                progress_cb: Optional[Callable[[str], None]] = None,
                should_cancel: Optional[Callable[[], bool]] = None,
                num_predict: int = 512) -> dict:
    """Esegue la suite di problemi da programmatore sul modello scaricato.

    Ritorna report dict: {"model", "problems": [...], "score", "loop_avg",
    "verdict", "saved_to", "ts"}. Il codice generato NON viene mai eseguito.
    """
    if generate_fn is None:
        generate_fn = lambda prompt: ollama_generate(
            model_name, prompt, host=host, num_predict=num_predict)  # noqa: E731
    t0 = time.time()
    results = []
    for problem in PROBLEMS:
        if should_cancel and should_cancel():
            raise RuntimeError("Harness annullato dall'utente")
        if progress_cb:
            progress_cb(f"Prova: {problem['title']}")
        try:
            out = generate_fn(problem["prompt"])
        except Exception as e:
            results.append({
                **{k: problem[k] for k in ("id", "title", "hint")},
                "passed": False, "error": str(e)[:200],
                **repetition_metrics(""),
            })
            continue
        metrics = repetition_metrics(out)
        passed = False
        err = ""
        try:
            passed = bool(problem["check"](out))
        except Exception as e:
            err = f"check error: {e}"
            passed = False
        results.append({
            **{k: problem[k] for k in ("id", "title", "hint")},
            "passed": passed,
            "error": err,
            "duplicate_line_ratio": metrics["duplicate_line_ratio"],
            "tail_selfsimilarity": metrics["tail_selfsimilarity"],
            "loops_like": metrics["loops_like"],
        })
    total = len(results)
    passed_n = sum(1 for r in results if r.get("passed"))
    ratios = [r.get("duplicate_line_ratio", 0) for r in results]
    loopy = any(r.get("loops_like") for r in results)
    loop_avg = round(sum(ratios) / max(1, len(ratios)), 3)
    score = round(passed_n / max(1, total), 2)

    # Verdetto in stile paper: i loop erano il fallimento tipico (ed. 8)
    if loopy:
        verdict = (
            "LOOP rilevati — come nell'Esperimento 8 del paper, il modello "
            "si ripete invece di terminare. Suggerito: repeat_penalty/temperature "
            "più aggressive o weight-space fix (fuori scope di questa beta)."
        )
    elif score >= 0.8:
        verdict = "Buono: la maggioranza dei problemi comuni è risolta."
    elif score >= 0.5:
        verdict = "Misto: istruzioni base OK, metà dei problemi falliti."
    else:
        verdict = "Debole per il coding: la maggioranza dei problemi fallisce."

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "-", model_name)[:80]
    report_path = REPORT_DIR / f"report_{safe_name}_{ts}.json"
    report = {
        "model": model_name,
        "ts": ts,
        "duration_s": round(time.time() - t0, 1),
        "problems": results,
        "score": score,
        "passed": passed_n,
        "total": total,
        "loop_avg": loop_avg,
        "loops_detected": loopy,
        "verdict": verdict,
        "saved_to": str(report_path),
        "reference": "https://rikiyat.github.io/blog/weight-space-programming/",
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def format_report(report: dict) -> str:
    """Report leggibile per la GUI (QPlainTextEdit)."""
    lines = [
        f"MODELLO:   {report['model']}",
        f"PUNTEGGIO: {report['passed']}/{report['total']} ({report['score']*100:.0f}%)",
        f"LOOP:      avg {report['loop_avg']:.2f}" + ("  ⚠️ loop rilevati" if report['loops_detected'] else ""),
        "",
        "PROBLEMI:",
    ]
    for r in report["problems"]:
        mark = "✅" if r.get("passed") else "❌"
        loop_mark = "  (loop!)" if r.get("loops_like") else ""
        lines.append(f"  {mark} {r['title']}{loop_mark}")
        if not r.get("passed"):
            lines.append(f"     → {r.get('hint', '')}")
            if r.get("error"):
                lines.append(f"     → {r['error']}")
    lines += ["", "VERDETTO:", f"  {report['verdict']}", "",
              f"report: {report['saved_to']}",
              f"paper di riferimento: {report.get('reference', '')}"]
    return "\n".join(lines)
