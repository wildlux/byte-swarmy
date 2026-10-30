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
from pathlib import Path
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
        content = response.get("message", {}).get("content", "").strip()
        self._save_call_metrics(model_key, model_name, response)
        return content

    def _save_call_metrics(self, model_key: str, model_name: str,
                           response: dict) -> None:
        """Estrae metriche dalla response Ollama e le salva su file.
        Ollama include nei campi finali: eval_count, eval_duration,
        prompt_eval_count, load_duration, total_duration.
        """
        try:
            import time as _time
            metrics = {
                "timestamp": _time.time(),
                "model": model_name,
                "model_key": model_key,
                "tokens_in": response.get("prompt_eval_count", 0),
                "tokens_out": response.get("eval_count", 0),
                "ttft_ms": (
                    response.get("load_duration", 0)
                    + response.get("prompt_eval_duration", 0)
                ) / 1e6,
                "total_ms": response.get("total_duration", 0) / 1e6,
                "tokens_per_sec": 0.0,
                "context_used": 0,
            }
            eval_dur_s = response.get("eval_duration", 0) / 1e9
            if eval_dur_s > 0 and metrics["tokens_out"] > 0:
                metrics["tokens_per_sec"] = round(
                    metrics["tokens_out"] / eval_dur_s, 1
                )
            metrics["context_used"] = (
                metrics["tokens_in"] + metrics["tokens_out"]
            )
            mfile = Path("state/last_metrics.json")
            mfile.parent.mkdir(parents=True, exist_ok=True)
            mfile.write_text(json.dumps(metrics, indent=2))
        except Exception as e:
            self.log.debug(f"metrics save failed: {e}")


    def call_streaming(self, model_key: str, prompt: str,
                       system: Optional[str] = None,
                       max_tokens: Optional[int] = None):
        """Chiama un modello in streaming mode. Yielda token per token.
        
        Usage:
            for token in client.call_streaming("worker_coder", prompt, system):
                print(token, end="", flush=True)
        """
        if model_key not in self.models_cfg:
            raise KeyError(f"unknown model key: {model_key}")

        model_cfg = self.models_cfg[model_key]
        model_name = model_cfg["name"]

        # Rotation: scarica modello precedente se diverso
        if self.current_model is not None and self.current_model != model_name:
            self._unload(self.current_model)
        self.current_model = model_name
        self.last_call_ts = time.time()

        options = {
            "temperature": model_cfg["temperature"],
            "top_p": model_cfg["top_p"],
            "top_k": model_cfg["top_k"],
            "repeat_penalty": model_cfg["repeat_penalty"],
            "repeat_last_n": model_cfg["repeat_last_n"],
            "num_ctx": model_cfg["num_ctx"],
            "num_predict": max_tokens or model_cfg["num_predict"],
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "options": options,
            "stream": True,  # STREAMING ATTIVO
        }

        self.log.debug(f"streaming model {model_name} (key={model_key}), "
                       f"prompt_len={len(prompt)}")

        # Streaming HTTP request
        import urllib.request
        url = f"{self.host}/api/chat"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        full_response = []
        metrics_data = {
            "model": model_name, "model_key": model_key,
            "tokens_in": 0, "tokens_out": 0,
            "tokens_per_sec": 0.0, "context_used": 0,
        }
        start_time = time.time()
        first_token_time = None
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    
                    # Estrai token
                    if "message" in chunk and "content" in chunk["message"]:
                        token = chunk["message"]["content"]
                        if token:
                            if first_token_time is None:
                                first_token_time = time.time()
                            full_response.append(token)
                            metrics_data["tokens_out"] += 1
                            yield token
                    
                    # Fine stream: salva metriche
                    if chunk.get("done", False):
                        eval_count = chunk.get("eval_count", metrics_data["tokens_out"])
                        eval_dur = chunk.get("eval_duration", 0) / 1e9
                        prompt_eval_count = chunk.get("prompt_eval_count", 0)
                        metrics_data["tokens_in"] = prompt_eval_count
                        metrics_data["tokens_out"] = eval_count
                        metrics_data["context_used"] = prompt_eval_count + eval_count
                        if eval_dur > 0 and eval_count > 0:
                            metrics_data["tokens_per_sec"] = round(eval_count / eval_dur, 1)
                        break
        except Exception as e:
            self.log.error(f"streaming failed: {e}")
            raise
        
        # Salva metriche (come call normale)
        self._save_streaming_metrics(model_key, model_name, metrics_data,
                                     start_time, first_token_time)

    def _save_streaming_metrics(self, model_key, model_name, metrics,
                                start_time, first_token_time):
        """Salva metriche streaming su state/last_metrics.json."""
        try:
            metrics["timestamp"] = time.time()
            metrics["ttft_ms"] = (
                (first_token_time - start_time) * 1000 if first_token_time else 0
            )
            metrics["total_ms"] = (time.time() - start_time) * 1000
            metrics["model"] = model_name
            metrics["model_key"] = model_key
            
            mfile = Path("state/last_metrics.json")
            mfile.parent.mkdir(parents=True, exist_ok=True)
            mfile.write_text(json.dumps(metrics, indent=2))
        except Exception as e:
            self.log.debug(f"streaming metrics save failed: {e}")


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
