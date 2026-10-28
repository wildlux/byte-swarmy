"""
integrazione_add_task.py — Esempio di integrazione del IntentRouter
in add_task.py (CLI entry point di byte-swarmy).

Copia le parti rilevanti nel tuo add_task.py esistente.
Non sovrascrivere la logica esistente, aggiungi solo il router.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

# Import esistenti del tuo progetto
# from orchestrator import TaskQueue, setup_logger, load_config
# (mantieni tutto quello che hai già)

# 🆕 Aggiungi questo import
from intent_router import IntentRouter


def add_task_with_intent(queue, logger, raw_input: str, router: IntentRouter,
                         force_fallback_as_generic: bool = True) -> str:
    """
    Punto di ingresso: utente scrive testo libero (IT/EN/ZH),
    il router lo classifica e aggiunge un task strutturato alla coda.
    
    Args:
        queue: TaskQueue esistente
        logger: logger esistente
        raw_input: testo dell'utente
        router: IntentRouter istanza (singleton)
        force_fallback_as_generic: se True, i fallback vanno come task 'generic'
                                   (verranno gestiti da GenericTaskPlanner)
    
    Returns:
        task_id generato
    """
    # 1. Classifica intent
    parsed = router.parse(raw_input)
    logger.info(f"intent_router: parsed '{raw_input[:60]}' → "
                f"intent={parsed['intent']}, lang={parsed['lang']}, "
                f"conf={parsed['confidence']}")
    
    # 2. Se fallback, opzionalmente chiedi chiarimento al modello
    if parsed["intent"] == "fallback":
        if not force_fallback_as_generic:
            # Opzione A: chiama modello per chiarire (usa ollama_client)
            # clarification = router.clarify_with_model(parsed, model_client=models)
            # return None  # o gestisci diversamente
            pass
        # Opzione B: tratta come task generico, il GenericTaskPlanner se ne occupa
        logger.info(f"intent_router: fallback, treating as generic task")
    
    # 3. Converte in task dict compatibile con queue.add()
    task = router.to_task(parsed, raw_input)
    
    # 4. Arricchisci il task con metadati che l'orchestrator può usare
    # Il campo 'context' contiene già lang + intent + params + confidence (JSON)
    # L'orchestrator può leggerlo così:
    #   ctx = json.loads(task["context"])
    #   user_lang = ctx["lang"]
    
    # 5. Aggiungi alla coda (metodo esistente di TaskQueue)
    task_id = queue.add(task)
    logger.info(f"task added: {task_id} (type={task['type']}, source={task['source']})")
    
    return task_id


# ====================================================================
# Esempio CLI minimale
# ====================================================================

def main():
    """CLI: python add_task.py 'crea funzione fattoriale in python'"""
    
    # Carica config e setup (usa quello che hai già)
    # config = load_config("config.toml")
    # logger = setup_logger(config)
    # queue = TaskQueue(Path(config["paths"]["tasks_dir"]), logger)
    
    # Per l'esempio, simulo:
    import logging
    logger = logging.getLogger("byte-swarmy")
    logging.basicConfig(level=logging.INFO)
    
    # Simulo una coda mock
    class MockQueue:
        def add(self, task):
            tid = f"mock-{int(__import__('time').time()*1000)}"
            print(f"\n[QUEUE] added task:")
            print(json.dumps(task, indent=2, ensure_ascii=False))
            return tid
    
    queue = MockQueue()
    
    # 🆕 Inizializza il router ONCE (singleton)
    router = IntentRouter("intents.json")
    
    # Prendi input dall'utente
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("Cosa vuoi fare? > ")
    
    # Aggiungi task
    task_id = add_task_with_intent(queue, logger, user_input, router)
    print(f"\n✓ Task ID: {task_id}")


# ====================================================================
# Patch consigliata per orchestrator.py (OPZIONALE)
# ====================================================================
"""
Per far sì che l'orchestrator risponda nella lingua dell'utente e
utilizzi i metadati del router, applica questa piccola patch
al metodo _tick() di Orchestrator:

PRIMA:
    task = self.queue.next_pending()
    if not task: return
    self.log.info(f"dispatching {task['id']}...")

DOPO:
    task = self.queue.next_pending()
    if not task: return
    
    # 🆕 Estrai metadati router dal context
    user_lang = "en"  # default
    user_intent = None
    if task.get("context"):
        try:
            ctx = json.loads(task["context"])
            user_lang = ctx.get("lang", "en")
            user_intent = ctx.get("intent")
            self.log.info(f"dispatching {task['id']} (intent={user_intent}, lang={user_lang})")
        except json.JSONDecodeError:
            self.log.info(f"dispatching {task['id']} (no intent metadata)")
    else:
        self.log.info(f"dispatching {task['id']}")
    
    # ... resto della logica esistente invariata ...

Per rispondere in user_lang quando il worker finisce, modifica il prompt
del worker in _build_initial_prompt() aggiungendo:
    f"\\n\\n## USER LANGUAGE\\nRespond in {user_lang}."
"""


if __name__ == "__main__":
    main()
