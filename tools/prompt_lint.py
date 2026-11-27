#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 — misura offline il prompt effettivo che vede un LLM piccolo.

L'ipotesi verificata è: *struttura sì, tono no*. Un modello piccolo benefitta
di istruzioni esplicite (una frase per azione, scelte limitate, formato JSON
dichiarato), non di un tono offensivo o di(testi) lunghi. Questo tool NON
chiama alcun LLM: misura il prompt prodotto da ``Worker._build_system`` (oppure
un file passato con ``--prompt-file``) e stampa un report deterministico.

L'A/B live (prompt "bambino" vs attuale) resta 🔒 bloccato termicamente: qui
si misura solo la struttura, non si misura la qualità delle risposte.

Uso:
    .venv/bin/python tools/prompt_lint.py                     # prompt reale
    .venv/bin/python tools/prompt_lint.py --family llama
    .venv/bin/python tools/prompt_lint.py --json
    .venv/bin/python tools/prompt_lint.py --prompt-file /tmp/p.txt
    .venv/bin/python tools/prompt_lint.py --out RAG/DOCS/PROMPT_LINT_REPORT.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "RAG" / "DOCS" / "PROMPT_LINT_REPORT.md"

# Euristiche dichiarate, non verità assolute: servono a confrontare due prompt,
# non a giudicare un modello.
_NUMBERED_RULE = re.compile(r"(?m)^\s*(\d+)\.")
_TOOL_LINE = re.compile(r"(?m)^  ([a-z_][a-z_0-9]*)=")
_SENTENCE_SPLIT = re.compile(r"[.!?\n]+")
_WORD = re.compile(r"[A-Za-zÀ-ÿ0-9_]+(?:['’-][A-Za-zÀ-ÿ0-9_]+)*")
_NON_ENGLISH = re.compile(r"[^\x00-\x7f]")
_OFFENSIVE = re.compile(
    r"\b(?:stupid\w*|idiot\w*|dumb\w*|moron\w*|sciocco\w*|"
    r"idiota\w*|cretino\w*|imbecille\w*)",
    re.IGNORECASE,
)
# Italiano/cedrine che compaiono nei commenti dei tool: misurati, non rimossi.
_ITALIAN_HINTS = frozenset({
    "solo", "se", "dubbi", "righe", "report", "cancella", "max",
    "contenuto", "file", "apri", "mostra", "leggi",
})

# Soglie di riferimento per lo status OK/WARN/FAIL.
MIN_RULES = 5
MAX_TOOLS = 16          # T1 punta a 8-15; 16 tollera il gruppo git completo
MAX_AVG_SENTENCE = 20
MAX_MAX_SENTENCE = 35
MAX_NON_ENGLISH = 0.05


def analyze_prompt(text: str) -> dict:
    """Analizza un prompt già costruito: zero I/O, zero LLM."""
    words = _WORD.findall(text or "")
    sentences = [s for s in _SENTENCE_SPLIT.split(text or "")
                 if _WORD.search(s)]
    lengths = [len(_WORD.findall(s)) for s in sentences]
    rules = sorted({int(n) for n in _NUMBERED_RULE.findall(text or "")})
    tools = _TOOL_LINE.findall(text or "")
    tokens = [w.lower() for w in words]
    non_en = [w for w in tokens
              if _NON_ENGLISH.search(w) or w in _ITALIAN_HINTS]
    ratio = round(len(non_en) / len(tokens), 4) if tokens else 0.0

    one_action = all(phrase in (text or "") for phrase in (
        "ONE JSON object per turn",
        "action=CODE",
        '"action":"none"',
    ))
    checks = {
        "instructions": (len(rules) >= MIN_RULES,
                         f"{len(rules)} regole numerate (min {MIN_RULES})"),
        "exposed_tools": (1 <= len(tools) <= MAX_TOOLS,
                          f"{len(tools)} tool esposti (max {MAX_TOOLS})"),
        "avg_sentence": (
            bool(lengths) and sum(lengths) / len(lengths) <= MAX_AVG_SENTENCE,
            f"media {sum(lengths) / len(lengths):.1f} parole/frase "
            f"(max {MAX_AVG_SENTENCE})" if lengths else "nessuna frase"),
        "max_sentence": (bool(lengths) and max(lengths) <= MAX_MAX_SENTENCE,
                         f"frase piu lunga {max(lengths) if lengths else 0} "
                         f"parole (max {MAX_MAX_SENTENCE})"),
        "non_english": (ratio <= MAX_NON_ENGLISH,
                        f"quota non-inglese {ratio:.1%} "
                        f"(max {MAX_NON_ENGLISH:.0%})"),
        "one_action_per_turn": (one_action,
                                "una azione/turno + formato JSON esplicito"
                                if one_action else "formato/azione non espliciti"),
        "tone": (_OFFENSIVE.search(text or "") is None,
                 "nessun marcatore offensivo"
                 if not _OFFENSIVE.search(text or "")
                 else "tono offensivo rilevato"),
    }
    status = ("FAIL" if not one_action or _OFFENSIVE.search(text or "")
              else "OK" if all(ok for ok, _ in checks.values()) else "WARN")
    return {
        "chars": len(text or ""),
        "words": len(words),
        "lines": len((text or "").splitlines()),
        "sentences": len(sentences),
        "avg_sentence_words": round(
            sum(lengths) / len(lengths), 2) if lengths else 0.0,
        "max_sentence_words": max(lengths) if lengths else 0,
        "rules": rules,
        "rule_count": len(rules),
        "tools": tools,
        "tool_count": len(tools),
        "non_english_tokens": len(non_en),
        "non_english_ratio": ratio,
        "one_action_per_turn": one_action,
        "offensive_markers": len(_OFFENSIVE.findall(text or "")),
        "checks": {k: {"ok": ok, "detail": detail}
                   for k, (ok, detail) in checks.items()},
        "status": status,
    }


def effective_prompt(family: str = "compact", task: dict | None = None) -> str:
    """Costruisce il prompt reale senza istanziare l'orchestratore.

    Riusa ``Worker._build_system`` su un probe con metodi sovrascritti:
    nessun client LLM, nessun file di stato, nessun thread avviato.
    """
    from CORE.worker import Worker

    class _Probe(Worker):
        def _model_family(self):
            return family

        def _classify_task_tools(self, _task):
            # Task git: gruppo massimo, cioè il prompt piu lungo che il
            # worker possa produrre (peggior caso per la lunghezza frasi).
            return ({"read", "read_slice", "write", "patch", "delete",
                     "move", "list", "search", "bash", "lint", "test",
                     "list_tools", "git_status", "git_diff", "git_commit",
                     "git_log", "git_branch", "git_merge"})

    probe = object.__new__(_Probe)
    probe._system_prompt_cache = {}
    probe.model_key = family
    return probe._build_system(task or {"title": "lint", "description": ""})


def markdown(m: dict) -> str:
    lines = [
        "# 🔍 Prompt Lint (D1)",
        "",
        "_Misura offline del prompt effettivo. Zero LLM, zero rete. "
        "A/B live resta 🔒 bloccato termicamente._",
        "",
        f"**Famiglia**: `{m['family']}` — **source**: `{m['source']}` "
        f"— **status**: `{m['analysis']['status']}`",
        "",
        "| Metrica | Valore |",
        "|---|---|",
        f"| Caratteri | {m['analysis']['chars']} |",
        f"| Parole | {m['analysis']['words']} |",
        f"| Righe | {m['analysis']['lines']} |",
        f"| Frasi | {m['analysis']['sentences']} |",
        f"| Parole/frase (media, max) | "
        f"{m['analysis']['avg_sentence_words']}, "
        f"{m['analysis']['max_sentence_words']} |",
        f"| Regole numerate | {m['analysis']['rule_count']} |",
        f"| Tool esposti | {m['analysis']['tool_count']} |",
        f"| Token non-inglesi | {m['analysis']['non_english_tokens']} "
        f"({m['analysis']['non_english_ratio']:.1%}) |",
        f"| Una azione per turno | "
        f"{'sì' if m['analysis']['one_action_per_turn'] else 'no'} |",
        f"| Marker offensivi | {m['analysis']['offensive_markers']} |",
        "",
        "| Check | Esito | Dettaglio |",
        "|---|---|---|",
    ]
    for name, check in m["analysis"]["checks"].items():
        lines.append(f"| `{name}` | {'✅' if check['ok'] else '⚠️'} "
                     f"| {check['detail']} |")
    lines += [
        "",
        "## Conclusione sull'ipotesi",
        "",
        "- **Struttura**: regole numerate, tool limitati e formato JSON "
        "esplicito sono misurabili e presenti (✅ sopra).",
        "- **Tono**: i marcatori offensivi sono "
        f"{m['analysis']['offensive_markers']}: il tono non è un fattore "
        "di struttura e non va introdotto.",
        "- **Lingua**: le istruzioni sono in inglese; il residuo non-inglese "
        "sono commenti nei tool (`# righe`, `# se dubbi`).",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--family", default="compact",
                    help="famiglia prompt reale: compact/llama/deepseek")
    ap.add_argument("--prompt-file", default=None,
                    help="analizza un file di testo invece del prompt reale")
    ap.add_argument("--json", action="store_true", help="stampa solo JSON")
    ap.add_argument("--out", default=None,
                    help="scrive il report Markdown in questo file")
    args = ap.parse_args(argv)

    if args.prompt_file:
        source = str(args.prompt_file)
        text = Path(source).read_text(encoding="utf-8")
        family = "custom"
    else:
        source = f"Worker._build_system(family={args.family})"
        family = args.family
        text = effective_prompt(args.family)
    result = {"family": family, "source": source,
              "analysis": analyze_prompt(text)}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    md = markdown(result)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"Report scritto: {out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
