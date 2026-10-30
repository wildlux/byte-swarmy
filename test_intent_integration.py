"""
test_intent_integration.py — Test per verificare che l'integrazione
del IntentRouter in byte-swarmy funzioni correttamente.

Da eseguire DOPO aver copiato i file e applicato le patch:
    python tests/test_intent_integration.py

Verifica:
1. intent_router.py carica correttamente
2. intent_bridge.py funziona con add_task() mock
3. Estrazione metadati dal task (per orchestrator)
4. Localizzazione messaggi UI
"""

import sys
import os
from pathlib import Path

# Aggiungi la root del progetto al path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_router_loads():
    """Il router carica correttamente intents.json."""
    from intent_router import IntentRouter
    router = IntentRouter("intents.json")
    assert len(router.intents) >= 20, f"Expected 20+ intents, got {len(router.intents)}"
    print(f"✓ Router carica {len(router.intents)} intent con {len(router._index)} trigger")


def test_bridge_parse():
    """Il bridge parse correttamente input multilingue."""
    from intent_bridge import parse_input
    
    cases = [
        ("crea funzione fattoriale", "it", "create_function"),
        ("create function factorial", "en", "create_function"),
        ("用python写函数", "zh", "create_function"),
        ("ottimizza codice", "it", "optimize"),
        ("swarm status", "en", "swarm_status"),
    ]
    
    for raw, expected_lang, expected_intent in cases:
        result = parse_input(raw)
        assert result["lang"] == expected_lang, \
            f"Lang mismatch: '{raw}' → got {result['lang']}, expected {expected_lang}"
        assert result["intent"] == expected_intent, \
            f"Intent mismatch: '{raw}' → got {result['intent']}, expected {expected_intent}"
        print(f"✓ '{raw}' → intent={result['intent']} lang={result['lang']}")


def test_bridge_add_task():
    """Il bridge chiama add_task con i parametri giusti."""
    from intent_bridge import add_task_with_intent
    
    captured = {}
    def mock_add_task(title, description, context, task_type):
        captured.update(title=title, description=description,
                       context=context, task_type=task_type)
        return {"id": "mock-123", "title": title}
    
    result = add_task_with_intent("ottimizza parse_json", mock_add_task)
    
    assert result["intent"] == "optimize"
    assert result["lang"] == "it"
    assert captured["task_type"] == "implement"
    assert "optimize" in captured["context"]
    assert "it" in captured["context"]
    print(f"✓ add_task_with_intent: type={captured['task_type']}, context ha lang+intent")


def test_metadata_extraction():
    """L'orchestrator può estrarre metadati dal context del task."""
    from intent_bridge import add_task_with_intent, extract_task_metadata
    
    captured = {}
    def mock_add_task(title, description, context, task_type):
        captured["context"] = context
        return {"context": context}
    
    add_task_with_intent("fixa il bug nel login", mock_add_task)
    
    # Simula il task che l'orchestrator leggerebbe dalla coda
    task = {"context": captured["context"], "title": "...", "description": "..."}
    meta = extract_task_metadata(task)
    
    assert meta["lang"] == "it"
    assert meta["intent"] == "fix_error"
    print(f"✓ extract_task_metadata: lang={meta['lang']}, intent={meta['intent']}")


def test_localization():
    """I messaggi UI sono localizzati in 3 lingue."""
    from intent_bridge import localize
    
    for lang, expected_substring in [("it", "aggiunto"), ("en", "added"), ("zh", "添加")]:
        msg = localize("task_added", lang, intent="test", conf=100)
        assert expected_substring in msg, f"Lang {lang}: '{msg}' missing '{expected_substring}'"
        print(f"✓ localize task_added [{lang}]: {msg}")


def test_swarm_command_detection():
    """Gli intent di swarm control vengono identificati correttamente."""
    from intent_bridge import parse_input
    
    swarm_commands = [
        "swarm status",
        "mostra stato swarm",
        "show logs",
        "pause swarm",
        "riprendi swarm",
    ]
    
    for cmd in swarm_commands:
        result = parse_input(cmd)
        # Almeno alcuni dovrebbero essere swarm commands
        if result["is_swarm_command"]:
            print(f"✓ '{cmd}' → swarm command: {result['intent']}")
    
    # Almeno 3 dei 5 devono essere identificati come swarm
    swarm_count = sum(1 for cmd in swarm_commands if parse_input(cmd)["is_swarm_command"])
    assert swarm_count >= 3, f"Only {swarm_count}/5 swarm commands detected"
    print(f"✓ {swarm_count}/5 swarm commands correttamente identificati")


def main():
    print("=" * 60)
    print("TEST INTEGRAZIONE INTENT ROUTER in byte-swarmy")
    print("=" * 60)
    
    tests = [
        test_router_loads,
        test_bridge_parse,
        test_bridge_add_task,
        test_metadata_extraction,
        test_localization,
        test_swarm_command_detection,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            print(f"\n→ {test.__name__}")
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RISULTATO: {passed} passati, {failed} falliti")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
