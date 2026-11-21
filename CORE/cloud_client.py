"""
CORE/cloud_client.py — client OpenAI-compatibile per provider cloud gratuiti.

Serve SOLO per test manuali (pannello Chat / tools/test_cloud_api.py):
non sostituisce ``ModelClient`` (che resta Ollama-only per la pipeline).

Provider supportati (tutti con tier gratuito):
- groq        https://console.groq.com/keys
- gemini      https://aistudio.google.com/apikey
- openrouter  https://openrouter.ai/keys   (modelli ":free")

La chiave si legge da:
1. variabile d'ambiente del provider (es. GROQ_API_KEY);
2. ``state/cloud_api.json`` (scritto dalla GUI, permessi 0600, gitignored).
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
KEYS_FILE = BASE_DIR / "state" / "cloud_api.json"

log = logging.getLogger("byte-swarmy")

PROVIDERS = {
    "groq": {
        "label": "Groq",
        "icon": "⚡",
        "base_url": "https://api.groq.com/openai/v1",
        "env": "GROQ_API_KEY",
        "signup": "https://console.groq.com/keys",
    },
    "gemini": {
        "label": "Google AI Studio",
        "icon": "✨",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env": "GEMINI_API_KEY",
        "signup": "https://aistudio.google.com/apikey",
    },
    "openrouter": {
        "label": "OpenRouter",
        "icon": "🌐",
        "base_url": "https://openrouter.ai/api/v1",
        "env": "OPENROUTER_API_KEY",
        "signup": "https://openrouter.ai/keys",
    },
}


def provider_info(provider: str) -> dict:
    """Metadati del provider (KeyError se sconosciuto)."""
    return PROVIDERS[provider]


def _load_keys() -> dict:
    if not KEYS_FILE.exists():
        return {}
    try:
        data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_api_key(provider: str) -> str:
    """Chiave API: prima l'ambiente, poi ``state/cloud_api.json``."""
    info = provider_info(provider)
    from_env = os.environ.get(info["env"], "").strip()
    if from_env:
        return from_env
    stored = _load_keys().get(provider, {})
    if isinstance(stored, dict):
        return str(stored.get("api_key", "")).strip()
    return ""


def save_api_key(provider: str, key: str) -> None:
    """Salva la chiave in ``state/cloud_api.json`` con permessi 0600."""
    provider_info(provider)
    data = _load_keys()
    data[provider] = {"api_key": (key or "").strip()}
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEYS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        KEYS_FILE.chmod(0o600)
    except OSError:
        pass


def has_api_key(provider: str) -> bool:
    return bool(get_api_key(provider))


def _headers(provider: str) -> dict:
    info = provider_info(provider)
    headers = {
        "Authorization": f"Bearer {get_api_key(provider)}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/wildlux/byte-swarmy"
        headers["X-Title"] = "byte-swarmy test"
    return headers


def _request_json(url: str, headers: dict, payload: dict | None = None,
                  timeout: float = 30.0) -> dict:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", "replace")
            detail = json.loads(raw).get("error", raw)
            if isinstance(detail, dict):
                detail = detail.get("message", detail)
        except Exception:
            detail = str(e)
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e


def list_models(provider: str, timeout: float = 20.0) -> list[str]:
    """Elenca i modelli disponibili per il provider (richiede la chiave)."""
    info = provider_info(provider)
    if not has_api_key(provider):
        raise RuntimeError(
            f"Manca la chiave API per {info['label']}. "
            f"Ottienila su {info['signup']}")
    body = _request_json(
        f"{info['base_url']}/models", _headers(provider), timeout=timeout)
    out = []
    for item in body.get("data", []) if isinstance(body, dict) else []:
        mid = str(item.get("id", "")).strip()
        if mid:
            out.append(mid)
    return sorted(set(out))


def _is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    bad = ("whisper", "tts", "embed", "guard", "moderation", "rerank",
           "image", "vision-only", "audio", "realtime")
    return not any(b in low for b in bad)


def pick_default_model(provider: str, models: list[str]) -> str:
    """Sceglie un modello chat ragionevole per il provider."""
    pool = [m for m in models if _is_chat_model(m)]
    if provider == "openrouter":
        free = [m for m in pool if m.lower().endswith(":free")]
        pool = free or pool
    if not pool:
        pool = list(models)
    if not pool:
        return ""
    # Punteggio deterministico: coding > grandi > instruct > flash/instant.
    def score(m: str) -> tuple:
        low = m.lower()
        return (
            0 if "coder" in low else 1,
            0 if ("70b" in low or "32b" in low or "flash" in low) else 1,
            0 if ("instruct" in low or "versatile" in low) else 1,
            0 if ("mini" in low or "instant" in low or "lite" in low) else 1,
            len(low),
            low,
        )
    return sorted(pool, key=score)[0]


def chat(provider: str, model: str, messages: list[dict],
         max_tokens: int = 512, temperature: float = 0.2,
         timeout: float = 90.0) -> dict:
    """Esegue una chat completion. Restituisce content/tempo/usage."""
    info = provider_info(provider)
    if not has_api_key(provider):
        raise RuntimeError(
            f"Manca la chiave API per {info['label']}. "
            f"Ottienila su {info['signup']}")
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    t0 = time.time()
    body = _request_json(
        f"{info['base_url']}/chat/completions",
        _headers(provider), payload, timeout=timeout)
    elapsed = time.time() - t0
    try:
        content = body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        content = ""
    log.debug("cloud %s/%s: %.2fs", provider, model, elapsed)
    return {
        "content": content.strip(),
        "model": model,
        "provider": provider,
        "elapsed": elapsed,
        "usage": body.get("usage", {}) if isinstance(body, dict) else {},
    }
