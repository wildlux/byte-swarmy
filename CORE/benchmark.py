"""
benchmark.py — Benchmark automatico dei modelli Ollama.

Suite fissa con 3 test:
1. Code generation: "write a factorial function"
2. Summarization: "summarize: lorem ipsum..."
3. Classification: "is this code safe? {code}"

Metriche: tok/s, latenza (TTFT), esito, tokens generati.

Usage:
    python -m CORE.benchmark              # benchmark tutti i modelli
    python -m CORE.benchmark --model qwen2.5-coder:1.5b  # solo uno
    python -m CORE.benchmark --apply      # suggerisci placement nel config
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Optional


BENCHMARK_FILE = Path("state/model_benchmarks.json")

TESTS = [
    {
        "name": "code_generation",
        "prompt": "Write a Python function that calculates the factorial of a number. Include type hints and a docstring.",
        "expected_keywords": ["def", "factorial", "return"],
        "max_tokens": 200,
    },
    {
        "name": "summarization",
        "prompt": "Summarize in one sentence: The quick brown fox jumps over the lazy dog. This sentence contains every letter of the English alphabet at least once. It is commonly used for typing practice and font display.",
        "expected_keywords": ["fox", "alphabet", "sentence"],
        "max_tokens": 100,
    },
    {
        "name": "classification",
        "prompt": "Is this Python code safe to run? Answer YES or NO and explain: import os; os.system('rm -rf /')",
        "expected_keywords": ["NO", "not safe", "dangerous"],
        "max_tokens": 100,
    },
]


def get_ollama_models(host: str = "http://localhost:11434") -> list:
    """Lista modelli disponibili."""
    try:
        data = json.loads(urllib.request.urlopen(f"{host}/api/tags", timeout=5).read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def run_single_test(model: str, test: dict, host: str = "http://localhost:11434") -> dict:
    """Esegue un singolo test su un modello."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": test["prompt"]}],
        "stream": False,
        "options": {"num_predict": test["max_tokens"], "temperature": 0.1},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "error": str(e)[:100]}
    
    elapsed = time.time() - start
    content = result.get("message", {}).get("content", "").strip()
    eval_count = result.get("eval_count", 0)
    ttft = (result.get("load_duration", 0) + result.get("prompt_eval_duration", 0)) / 1e9
    
    # Verifica keywords
    content_lower = content.lower()
    keywords_found = sum(1 for kw in test["expected_keywords"] if kw.lower() in content_lower)
    keyword_score = keywords_found / len(test["expected_keywords"])
    
    tps = eval_count / elapsed if elapsed > 0 else 0
    
    return {
        "status": "pass" if keyword_score >= 0.3 else "fail",
        "tok_s": round(tps, 1),
        "ttft_ms": round(ttft * 1000, 0),
        "tokens": eval_count,
        "elapsed_s": round(elapsed, 1),
        "keyword_score": round(keyword_score, 2),
        "content_preview": content[:100],
    }


def benchmark_model(model: str, host: str = "http://localhost:11434") -> dict:
    """Esegue tutti i test su un modello."""
    results = {"model": model, "timestamp": time.time(), "tests": {}}
    
    for test in TESTS:
        results["tests"][test["name"]] = run_single_test(model, test, host)
    
    # Score complessivo
    passed = sum(1 for t in results["tests"].values() if t.get("status") == "pass")
    avg_tps = sum(t.get("tok_s", 0) for t in results["tests"].values()) / max(1, len(TESTS))
    avg_ttft = sum(t.get("ttft_ms", 0) for t in results["tests"].values()) / max(1, len(TESTS))
    
    results["summary"] = {
        "tests_passed": f"{passed}/{len(TESTS)}",
        "avg_tok_s": round(avg_tps, 1),
        "avg_ttft_ms": round(avg_ttft, 0),
        "score": round((passed / len(TESTS)) * 100, 0),
    }
    
    return results


def run_benchmarks(models: list = None, host: str = "http://localhost:11434") -> dict:
    """Esegue benchmark su tutti i modelli (o una lista specificata)."""
    if models is None:
        models = get_ollama_models(host)
    
    if not models:
        return {"error": "no models available"}
    
    all_results = {}
    for model in models:
        print(f"  Benchmarking {model}...")
        all_results[model] = benchmark_model(model, host)
    
    # Salva
    BENCHMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "timestamp": time.time(),
        "models_tested": len(all_results),
        "results": all_results,
    }
    BENCHMARK_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    
    return output


def format_results(results: dict) -> str:
    """Formatta i risultati per display."""
    lines = ["Benchmark Results:", "=" * 70]
    
    for model, data in results.get("results", {}).items():
        summary = data.get("summary", {})
        lines.append("")
        lines.append(model + ":")
        lines.append(f"  Score: {summary.get('score', 0):.0f}/100 "
                     f"({summary.get('tests_passed', '?')})")
        lines.append(f"  Avg tok/s: {summary.get('avg_tok_s', 0)}")
        lines.append(f"  Avg TTFT: {summary.get('avg_ttft_ms', 0)}ms")
        
        for test_name, test_data in data.get("tests", {}).items():
            status = test_data.get("status", "?")
            tps = test_data.get("tok_s", 0)
            lines.append(f"    {test_name}: {status} ({tps} tok/s)")
    
    return chr(10).join(lines)


if __name__ == "__main__":
    import sys
    models = None
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        models = [sys.argv[idx + 1]]
    
    print("=" * 60)
    print("MODEL BENCHMARK SUITE")
    print("=" * 60)
    
    results = run_benchmarks(models)
    print("\n" + format_results(results))
    print(f"\nSaved to {BENCHMARK_FILE}")
