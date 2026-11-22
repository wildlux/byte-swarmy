"""
test_prompt_lint.py — D1: misura offline del prompt (struttura sì, tono no).
Nessun LLM, nessuna rete: analizza stringhe e il prompt reale del worker.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.prompt_lint import analyze_prompt, effective_prompt  # noqa: E402


BAD_PROMPT = (
    "Sei uno stupido, scrivi tutto quello che vuoi in modo confuso e "
    "lunghissimo senza alcun formato preciso, usa pure parole a caso e "
    "non rispettare nessuna regola perche' tanto non importa nulla."
)

GOOD_PROMPT = (
    "You are a coding agent.\n"
    "Reply with ONE JSON object per turn and NOTHING else.\n"
    "RULES:\n"
    "1. Paths in project/.\n2. One cmd per bash.\n3. write=CREATE.\n"
    "4. Run tests.\n5. Security enforced.\n"
    "6. action=CODE from list above.\n"
    '7. When done: {"thought":"...","action":"none","args":[],'
    '"done":true,"result":"..."}.\n'
    "TOOLS:\n  read=read_file(path)\n  write=write_file(path,content)\n"
)


def test_struttura_del_prompt_reale():
    m = analyze_prompt(effective_prompt("compact"))
    assert m["status"] == "OK"
    assert m["one_action_per_turn"] is True
    assert m["offensive_markers"] == 0
    assert m["rule_count"] >= 5
    assert 1 <= m["tool_count"] <= 16
    assert all(c["ok"] for c in m["checks"].values())


def test_famiglie_llama_e_deepseek_hanno_struttura():
    for family in ("llama", "deepseek"):
        m = analyze_prompt(effective_prompt(family))
        assert m["one_action_per_turn"] is True, family
        assert m["offensive_markers"] == 0, family
        assert m["rule_count"] >= 5, family


def test_prompt_cattivo_e_fallito():
    m = analyze_prompt(BAD_PROMPT)
    assert m["status"] == "FAIL"
    assert m["offensive_markers"] >= 1
    assert m["one_action_per_turn"] is False
    assert m["checks"]["tone"]["ok"] is False


def test_prompt_buono_passa():
    m = analyze_prompt(GOOD_PROMPT)
    assert m["one_action_per_turn"] is True
    assert m["offensive_markers"] == 0
    assert m["rule_count"] >= 5
    assert m["checks"]["instructions"]["ok"] is True


def test_metriche_stringa_vuota_fail_open():
    m = analyze_prompt("")
    assert m["words"] == 0
    assert m["sentences"] == 0
    assert m["avg_sentence_words"] == 0.0
    assert m["non_english_ratio"] == 0.0
    assert m["status"] == "FAIL"


def test_quota_non_inglese_misura_commenti_italiani():
    m = analyze_prompt("read_file(path)  # solo report, non cancella\n"
                       "write_file(path,content)")
    assert m["non_english_tokens"] >= 2
    assert 0 < m["non_english_ratio"] <= 1.0
