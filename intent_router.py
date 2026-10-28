"""
intent_router.py — Intent Router multilingue per byte-swarmy.

Si inserisce PRIMA di queue.add(): prende input raw dell'utente,
restituisce un dict strutturato con intent, lingua, parametri.

Zero dipendenze da orchestrator.py: può essere usato standalone
o integrato in add_task.py / gui.py.

Usage:
    router = IntentRouter("intents.json")
    result = router.parse("ottimizza la funzione parse_json")
    # → {"intent": "optimize", "lang": "it", "params": {...}, "confidence": 92}

    task = router.to_task(result, raw_input)
    queue.add(task)
"""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Optional

try:
    from rapidfuzz import fuzz
except ImportError:
    raise ImportError("pip install rapidfuzz")

log = logging.getLogger("byte-swarmy.intent")


# ====================================================================
# Language detector (zero dipendenze, fallback semplice)
# ====================================================================

# Pattern per cinese: range Unicode CJK Unified Ideographs
_CJK_RE = re.compile(r'[\u4e00-\u9fff]')

# Parole comuni italiane (discriminanti vs inglese)
_IT_HINTS = {
    "il", "lo", "la", "i", "gli", "le", "di", "del", "della", "che", "una",
    "uno", "sono", "è", "per", "con", "non", "ma", "come", "questo",
    "questa", "quello", "quella", "anche", "più", "meno",
    "crea", "scrivi", "modifica", "elimina", "spiega", "correggi",
    "ottimizza", "esegui", "lancia", "mostra", "lista", "riprendi",
    "cancella", "ferma", "blocca", "riassumi", "sistema", "fixa",
}
_EN_HINTS = {
    "the", "of", "to", "and", "a", "an", "in", "on", "for", "with",
    "is", "are", "was", "were", "this", "that", "these", "those",
    "create", "write", "modify", "delete", "explain", "fix", "optimize",
    "run", "show", "list", "find", "search",
}


def detect_lang(text: str) -> str:
    """Rileva lingua: 'zh', 'it', 'en'. Fallback: 'en'."""
    if not text or not text.strip():
        return "en"
    if _CJK_RE.search(text):
        return "zh"
    tokens = re.findall(r'\b[a-zA-Zà-ÿ]+\b', text.lower())
    if not tokens:
        return "en"
    it_score = sum(1 for t in tokens if t in _IT_HINTS)
    en_score = sum(1 for t in tokens if t in _EN_HINTS)
    if it_score > en_score:
        return "it"
    if en_score > it_score:
        return "en"
    # Pareggio: se ha accenti italiani probabile IT
    if re.search(r'[àèéìòù]', text.lower()):
        return "it"
    return "en"


# ====================================================================
# Intent Router
# ====================================================================

class IntentRouter:
    """Carica intents.json, fa matching fuzzy multilingue."""

    def __init__(self, json_path: str, confidence_threshold: int = 75):
        self.path = Path(json_path)
        self.threshold = confidence_threshold
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.intents = data["intents"]
        # Indice inverso: (frase_lower, intent_id, lang)
        self._index = []
        for intent in self.intents:
            for lang, frasi in intent.get("triggers", {}).items():
                for frase in frasi:
                    self._index.append((frase.lower(), intent["id"], lang))
        log.info(f"intent_router: loaded {len(self.intents)} intents, "
                 f"{len(self._index)} triggers")

    def parse(self, user_input: str) -> dict:
        """Classifica l'input utente. Ritorna dict strutturato."""
        if not user_input or not user_input.strip():
            return {"intent": "fallback", "lang": "en",
                    "params": {}, "confidence": 0, "raw": user_input}

        text = user_input.lower().strip()
        detected_lang = detect_lang(user_input)

        # Match: testa prima la lingua rilevata, poi tutte
        # Score ibrido: partial_ratio + coverage + length bonus
        best = ("fallback", 0.0, detected_lang)
        candidates_by_lang = {"it": [], "en": [], "zh": []}

        for template, intent_id, lang in self._index:
            score = self._hybrid_score(text, template)
            candidates_by_lang[lang].append((score, intent_id))

        # Priorità alla lingua rilevata
        for lang in [detected_lang, "en", "it", "zh"]:
            if not candidates_by_lang.get(lang):
                continue
            top = max(candidates_by_lang[lang])
            if top[0] > best[1]:
                best = (top[1], top[0], lang)

        intent_id, score, matched_lang = best

        if score < self.threshold:
            return {
                "intent": "fallback",
                "lang": detected_lang,
                "params": {},
                "confidence": round(score, 1),
                "raw": user_input,
                "matched_lang": matched_lang,
            }

        # Recupera schema params dell'intent
        intent_def = next((i for i in self.intents if i["id"] == intent_id), None)
        params_schema = intent_def.get("params", {}) if intent_def else {}
        task_type = intent_def.get("task_type", "generic") if intent_def else "generic"

        return {
            "intent": intent_id,
            "lang": detected_lang,
            "matched_lang": matched_lang,
            "params": self._extract_params(user_input, params_schema),
            "params_schema": params_schema,
            "confidence": round(score, 1),
            "task_type": task_type,
            "category": intent_def.get("category", "") if intent_def else "",
            "raw": user_input,
        }

    def _hybrid_score(self, text: str, template: str) -> float:
        """Score ibrido con priorità per subset matching.
        
        Strategia (in ordine di priorità):
        1. SUBSET MATCH: tutti i token del template sono nel testo → score altissimo
           (più token = più specifico = score più alto)
        2. CJK FULL CHAR COVERAGE: per template cinesi, se tutti i caratteri
           sono presenti nel testo → score alto
        3. NORMAL SCORING: combinazione di partial_ratio, token_set_ratio, coverage
        """
        pr = fuzz.partial_ratio(text, template)
        ts = fuzz.token_set_ratio(text, template)

        # Tokenizzazione migliorata (gestisce whitespace, hyphens, underscores)
        template_tokens = self._tokenize(template)
        text_tokens = self._tokenize(text)

        if not template_tokens:
            return 0.0

        # 1. SUBSET MATCH (più forte): tutti i token del template sono nel testo
        if template_tokens.issubset(text_tokens):
            return 100.0 + len(template_tokens) * 10

        # Coverage token-level
        token_coverage = (len(template_tokens & text_tokens) / len(template_tokens)) * 100

        # 2. CJK char-coverage (per cinese, dove non ci sono spazi tra parole)
        if _CJK_RE.search(template):
            template_chars = set(template) - {' '}
            text_chars = set(text) - {' '}
            if template_chars:
                char_coverage = (len(template_chars & text_chars) / len(template_chars)) * 100
                if char_coverage == 100:
                    # Tutti i caratteri del template cinese sono nel testo
                    return 95.0 + len(template_chars) * 2

        # 3. NORMAL SCORING per match parziali
        base = pr * 0.20 + ts * 0.15 + token_coverage * 0.65
        specificity = min(len(template_tokens) * 2, 10)
        return base + specificity

    def _tokenize(self, text: str) -> set:
        """Tokenizza gestendo whitespace, hyphens, underscores.
        Es: 'task-123' → {'task', '123'} invece di {'task-123'}.
        """
        tokens = re.split(r'[\s\-_]+', text.lower())
        return set(t for t in tokens if t)

    def _extract_params(self, text: str, schema: dict) -> dict:
        """Estrazione parametri semplice. Per casi complessi, usare LLM."""
        params = {}
        for key, ptype in schema.items():
            if ptype == "boolean":
                params[key] = False
            elif ptype == "integer":
                m = re.search(r'\b(\d+)\b', text)
                params[key] = int(m.group(1)) if m else None
            elif ptype == "array":
                params[key] = []
            elif ptype == "object":
                params[key] = {}
            elif ptype.endswith("|null") or ptype == "string|null":
                params[key] = None
            elif "|" in ptype:  # enum: "velocity|memory|size|latency"
                options = ptype.split("|")
                for opt in options:
                    if opt in text.lower():
                        params[key] = opt
                        break
                else:
                    params[key] = options[0] if options else None
            else:
                params[key] = None
        return params

    def to_task(self, parsed: dict, raw_input: str) -> dict:
        """Converte l'output di parse() in un dict pronto per queue.add().

        Mappa:
          - intent_id → task['source'] = "intent:<id>"
          - task_type → task['type'] (compatible con orchestrator: implement|test|fix|generic)
          - lang + params → task['context'] (JSON string)
        """
        return {
            "title": raw_input[:120],
            "description": raw_input,
            "type": parsed.get("task_type", "generic"),
            "source": f"intent:{parsed['intent']}" if parsed["intent"] != "fallback" else "manual",
            "context": json.dumps({
                "lang": parsed["lang"],
                "intent": parsed["intent"],
                "params": parsed["params"],
                "confidence": parsed["confidence"],
            }, ensure_ascii=False),
        }

    def clarify_with_model(self, parsed: dict, model_client=None) -> Optional[str]:
        """Se fallback, chiama il model per chiarire cosa vuole l'utente.
        Ritorna il testo chiarito o None."""
        if parsed["intent"] != "fallback":
            return None
        if not model_client:
            return None
        try:
            prompt = (
                f"L'utente ha scritto: \"{parsed['raw']}\"\n"
                f"Lingua rilevata: {parsed['lang']}\n"
                "Rispondi in UNA frase chiedendo chiarimento su cosa vuole fare. "
                "Non inventare intent."
            )
            return model_client.call(
                model_key="planner",
                prompt=prompt,
                system="Sei un assistente che aiuta a chiarire richieste ambigue.",
                max_tokens=200,
            )
        except Exception as e:
            log.warning(f"clarify_with_model failed: {e}")
            return None


# ====================================================================
# Self-test
# ====================================================================

if __name__ == "__main__":
    import sys
    json_path = sys.argv[1] if len(sys.argv) > 1 else "intents.json"
    router = IntentRouter(json_path)

    tests = [
        "crea una funzione fattoriale in python",
        "create a factorial function in python",
        "用python创建一个阶乘函数",
        "ottimizza questa funzione è lenta",
        "make this faster",
        "fixa il bug che ho descritto",
        "mostra lo stato dello swarm",
        "swarm status",
        "cancella il task-123",
        "riprendi swarm",
        "xyz random nonsense frase",
    ]

    print(f"{'INPUT':<50} {'INTENT':<18} {'LANG':<5} {'CONF':<5}")
    print("-" * 85)
    for t in tests:
        r = router.parse(t)
        print(f"{t[:50]:<50} {r['intent']:<18} {r['lang']:<5} {r['confidence']:<5}")
        task = router.to_task(r, t)
        print(f"  → task: type={task['type']}, source={task['source']}")
