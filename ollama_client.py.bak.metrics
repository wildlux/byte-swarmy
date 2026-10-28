"""
ollama_client.py — ModelClient class
Wrapper sull'API Ollama con rotation automatica dei modelli.
Un solo modello caricato in RAM alla volta (vincolo 4GB).
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Optional


class ModelClient:
    """
    Client Ollama con rotation esplicita.

    Vincoli:
    - Un solo modello "attivo" alla volta in RAM.
    - Prima di caricare un nuovo modello, scarica quello precedente (keep_alive=0).
    - Verifica che Ollama sia raggiungibile prima di ogni ciclo.
    """

    def __init__(self, config, logger):
        self.cfg = config
        self.log = logger
        self.host = config["ollama"]["host"].rstrip("/")
        self.timeout = config["ollama"]["request_timeout"]
        self.models_cfg = config["models"]

        self.current_model: Optional[str] = None
        self.last_call_ts: float = 0

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def call(self, model_key: str, prompt: str,
             system: Optional[str] = None,
             max_tokens: Optional[int] = None) -> str:
        """Chiama un modello identificato dalla sua chiave in config (es. 'orchestrator').
        Carica/scarica modelli in automatico per rispettare il vincolo di RAM.
        """
        if model_key not in self.models_cfg:
            raise KeyError(f"unknown model key: {model_key}")

        model_cfg = self.models_cfg[model_key]
        model_name = model_cfg["name"]

        # Rotation: scarica il modello precedente se diverso
        if self.current_model is not None and self.current_model != model_name:
            self._unload(self.current_model)

        self.current_model = model_name
        self.last_call_ts = time.time()

        # Costruisci payload
        options = {
            "temperature": model_cfg["temperature"],
            "top_p": model_cfg["top_p"],
            "top_k": model_cfg["top_k"],
            "repeat_penalty": model_cfg["repeat_penalty"],
            "repeat_last_n": model_cfg["repeat_last_n"],
            "num_ctx": model_cfg["num_ctx"],
            "num_predict": max_tokens or model_cfg["num_predict"],
        }
        if "seed" in model_cfg:
            options["seed"] = model_cfg["seed"]

        # Endpoint /api/chat (più pulito di /api/generate per system prompt)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "options": options,
            "stream": False,
        }

        self.log.debug(f"calling model {model_name} (key={model_key}), "
                       f"prompt_len={len(prompt)}")

        response = self._post("/api/chat", payload)
        return response.get("message", {}).get("content", "").strip()

    def embed(self, text: str) -> list:
        """Calcola embedding. Non scarica il modello chat (più leggero)."""
        emb_name = self.models_cfg["embedding"]["name"]
        payload = {"model": emb_name, "prompt": text}
        response = self._post("/api/embeddings", payload)
        return response.get("embedding", [])

    def unload_all(self) -> None:
        """Scarica tutti i modelli (chiamato prima di shutdown)."""
        if self.current_model:
            self._unload(self.current_model)
            self.current_model = None

    def is_available(self) -> bool:
        """Verifica che Ollama sia raggiungibile."""
        try:
            urllib.request.urlopen(
                f"{self.host}/api/tags",
                timeout=5,
            ).read()
            return True
        except Exception:
            return False

    def list_models(self) -> list:
        """Lista modelli disponibili localmente."""
        try:
            data = json.loads(
                urllib.request.urlopen(
                    f"{self.host}/api/tags", timeout=5
                ).read()
            )
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            self.log.error(f"cannot list models: {e}")
            return []

    # ------------------------------------------------------------------
    # Utility interne
    # ------------------------------------------------------------------

    def _unload(self, model_name: str) -> None:
        """Scarica un modello dalla RAM (keep_alive=0)."""
        if not model_name:
            return
        try:
            payload = {
                "model": model_name,
                "messages": [],
                "keep_alive": 0,
            }
            self._post("/api/chat", payload, timeout=30)
            self.log.debug(f"unloaded {model_name}")
        except Exception as e:
            self.log.warning(f"failed to unload {model_name}: {e}")

    def _post(self, endpoint: str, payload: dict, timeout: Optional[int] = None) -> dict:
        url = f"{self.host}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t = timeout or self.timeout
        try:
            with urllib.request.urlopen(req, timeout=t) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {e.code}: {body[:500]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama unreachable: {e}")
