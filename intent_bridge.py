"""
intent_bridge.py — Bridge tra IntentRouter e il sistema byte-swarmy.

Progettato per funzionare con:
- gui.py: add_task(title, description, context, task_type) → scrive su tasks/queue.json
- orchestrator.py: estrae metadati dal campo 'context' (JSON) del task

Usage GUI:
    from intent_bridge import add_task_with_intent, localize
    
    task = add_task_with_intent("ottimizza parse_json è lenta")
    # → usa la tua add_task() esistente, arricchisce context con lang+intent+params

Usage Orchestrator:
    from intent_bridge import extract_task_metadata
    meta = extract_task_metadata(task)
    user_lang = meta["lang"]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Callable

from intent_router import IntentRouter


# ====================================================================
# Singleton: il router viene caricato una sola volta
# ====================================================================

_ROUTER: Optional[IntentRouter] = None
_ROUTER_PATH = Path(__file__).parent / "intents.json"


def get_router() -> IntentRouter:
    """Restituisce il singleton IntentRouter. Lo crea al primo utilizzo."""
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = IntentRouter(str(_ROUTER_PATH))
        logging.getLogger("byte-swarmy").info(
            f"intent_bridge: router loaded from {_ROUTER_PATH}"
        )
    return _ROUTER


# ====================================================================
# Funzione principale: parse + add_task (GUI-friendly)
# ====================================================================

def parse_input(raw_input: str) -> dict:
    """Prende input utente raw, lo classifica. NON aggiunge alla coda.
    
    Returns:
        dict con: {intent, lang, params, confidence, task_type, source, 
                   title, description, context, fallback, is_swarm_command}
    """
    router = get_router()
    parsed = router.parse(raw_input)
    task = router.to_task(parsed, raw_input)
    
    # Identifica intent di "swarm control" che non richiedono worker
    swarm_intents = {
        "swarm_status", "list_tasks", "show_logs", "pause_swarm",
        "resume_swarm", "inspect_memory", "cancel_task", "run_audit",
    }
    is_swarm = parsed["intent"] in swarm_intents
    
    return {
        # Dati per add_task()
        "title": task["title"],
        "description": task["description"],
        "context": task["context"],   # JSON string con lang+intent+params+confidence
        "task_type": task["type"],
        "source": task["source"],
        # Metadati per UI feedback
        "intent": parsed["intent"],
        "lang": parsed["lang"],
        "confidence": parsed["confidence"],
        "fallback": parsed["intent"] == "fallback",
        "is_swarm_command": is_swarm,
    }


def add_task_with_intent(
    raw_input: str,
    add_task_fn: Callable,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """Wrapper: parse + chiama add_task() del gui.py.
    
    Args:
        raw_input: testo utente (IT/EN/ZH)
        add_task_fn: riferimento alla funzione add_task() di gui.py
        logger: opzionale
    
    Returns:
        dict con: {task, intent, lang, confidence, fallback, is_swarm_command}
    """
    parsed = parse_input(raw_input)
    
    if logger:
        logger.info(
            f"intent_bridge: '{raw_input[:60]}' → "
            f"intent={parsed['intent']} lang={parsed['lang']} "
            f"conf={parsed['confidence']} swarm={parsed['is_swarm_command']}"
        )
    
    # Chiama la add_task() di gui.py con i campi strutturati
    task = add_task_fn(
        title=parsed["title"],
        description=parsed["description"],
        context=parsed["context"],
        task_type=parsed["task_type"],
    )
    
    return {
        "task": task,
        "intent": parsed["intent"],
        "lang": parsed["lang"],
        "confidence": parsed["confidence"],
        "fallback": parsed["fallback"],
        "is_swarm_command": parsed["is_swarm_command"],
    }


# ====================================================================
# Helper per l'orchestrator: estrai metadati dal task
# ====================================================================

def extract_task_metadata(task: dict) -> dict:
    """Estrae dal campo 'context' (JSON) i metadati del router.
    Da chiamare in orchestrator._tick() prima di dispatchare."""
    ctx_raw = task.get("context", "")
    if not ctx_raw:
        return {"lang": "en", "intent": None, "params": {}, "confidence": 0,
                "is_swarm_command": False}
    try:
        ctx = json.loads(ctx_raw)
        intent = ctx.get("intent")
        swarm_intents = {
            "swarm_status", "list_tasks", "show_logs", "pause_swarm",
            "resume_swarm", "inspect_memory", "cancel_task", "run_audit",
        }
        return {
            "lang": ctx.get("lang", "en"),
            "intent": intent,
            "params": ctx.get("params", {}),
            "confidence": ctx.get("confidence", 0),
            "is_swarm_command": intent in swarm_intents,
        }
    except (json.JSONDecodeError, TypeError):
        return {"lang": "en", "intent": None, "params": {}, "confidence": 0,
                "is_swarm_command": False}


# ====================================================================
# Helper per risposte localizzate (UI feedback)
# ====================================================================

_TEMPLATES = {
    "task_added": {
        "it": "✓ Task aggiunto: {intent} (confidenza {conf}%)",
        "en": "✓ Task added: {intent} (confidence {conf}%)",
        "zh": "✓ 任务已添加：{intent}（置信度 {conf}%）",
    },
    "fallback": {
        "it": "⚠ Non ho capito. Prova: 'crea funzione X', 'ottimizza Y', 'fixa bug Z'",
        "en": "⚠ Didn't understand. Try: 'create function X', 'optimize Y', 'fix bug Z'",
        "zh": "⚠ 没理解。试试：'创建函数X'，'优化Y'，'修复bug Z'",
    },
    "swarm_command": {
        "it": "🐝 Comando swarm: {intent} (in attesa di handler dedicato)",
        "en": "🐝 Swarm command: {intent} (awaiting dedicated handler)",
        "zh": "🐝 集群命令：{intent}（等待专用处理器）",
    },
}

def localize(key: str, lang: str, **kwargs) -> str:
    """Restituisce un messaggio localizzato."""
    templates = _TEMPLATES.get(key, {})
    template = templates.get(lang) or templates.get("en") or key
    return template.format(**kwargs)


# ====================================================================
# Self-test
# ====================================================================

if __name__ == "__main__":
    import sys
    
    # Mock della funzione add_task di gui.py
    def mock_add_task(title, description, context, task_type):
        print(f"\n[MOCK add_task] type={task_type}")
        print(f"  title: {title}")
        print(f"  context (JSON): {context}")
        return {"id": f"mock-{int(__import__('time').time()*1000)}"}
    
    tests = [
        ("IT", "ottimizza parse_json è lenta"),
        ("EN", "create a new file utils.py"),
        ("ZH", "用python写一个加法函数"),
        ("IT", "mostra stato swarm"),
        ("EN", "swarm status"),
        ("?",  "xyz nonsense frase"),
    ]
    
    print("=" * 70)
    for label, raw in tests:
        print(f"\n[{label}] INPUT: {raw}")
        result = add_task_with_intent(raw, mock_add_task)
        msg = localize(
            "swarm_command" if result["is_swarm_command"]
            else ("fallback" if result["fallback"] else "task_added"),
            result["lang"],
            intent=result["intent"],
            conf=result["confidence"],
        )
        print(f"  UI: {msg}")
