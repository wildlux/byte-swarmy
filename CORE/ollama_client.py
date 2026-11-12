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

from CORE.constants import DEFAULT_NUM_CTX


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
        self.llm_tuner = None  # 🆕 TimestralLLMTuner (set by orchestrator)
        self.last_options_used: dict = {}  # 🆕 ultima opzioni usate per model_key

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

        # 🆕 Timeout PER MODELLO: i modelli grandi (o le macchine lente)
        # possono superare il default [ollama].request_timeout — la suite
        # T8/T9/T10 col 4B ha bruciato 3 task su "LLM call failed: timed
        # out" a 300 s esatti.
        model_timeout = model_cfg.get("timeout", self.timeout)

        # Rotation: scarica il modello precedente se diverso
        if self.current_model is not None and self.current_model != model_name:
            self._unload(self.current_model)

        self.current_model = model_name
        self.last_call_ts = time.time()

        # 🆕 Build options with TimestralLLMTuner (if available)
        options = self._get_tuned_options(model_key, model_cfg, max_tokens)
        # 🆕 Salva le opzioni usate per il rollback "last good config"
        self.last_options_used[model_key] = dict(options)

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

        response = self._post("/api/chat", payload, timeout=model_timeout)
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
                       max_tokens: Optional[int] = None,
                       options_override: Optional[dict] = None):
        """Chiama un modello in streaming mode. Yielda token per token.

        Usage:
            for token in client.call_streaming("worker_coder", prompt, system):
                print(token, end="", flush=True)

        Args:
            options_override: dizionario di opzioni (temperature, seed,
                repeat_penalty, ...) che sovrascrive quelle calcolate
                dinamicamente per questa singola chiamata. Utile per il
                fallback su loop (nuovo seed, temperatura più alta,
                penalità maggiore).
        """
        if model_key not in self.models_cfg:
            raise KeyError(f"unknown model key: {model_key}")

        model_cfg = self.models_cfg[model_key]
        model_name = model_cfg["name"]

        # 🆕 Timeout per modello (vedi call()): override da [models.*]
        model_timeout = model_cfg.get("timeout", self.timeout)

        # Rotation: scarica modello precedente se diverso
        if self.current_model is not None and self.current_model != model_name:
            self._unload(self.current_model)
        self.current_model = model_name
        self.last_call_ts = time.time()

        # 🆕 Build options with TimestralLLMTuner (if available)
        options = self._get_tuned_options(model_key, model_cfg, max_tokens)

        # Applica override per singola chiamata (fallback su loop, ecc.)
        if options_override:
            options.update(options_override)
        # 🆕 Salva le opzioni usate per il rollback "last good config"
        self.last_options_used[model_key] = dict(options)

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
            with urllib.request.urlopen(req, timeout=model_timeout) as resp:
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



    def _get_tuned_options(self, model_key: str, model_cfg: dict,
                            max_tokens: Optional[int] = None) -> dict:
        """Build options dict, applying TimestralLLMTuner if available.

        The tuner overrides: temperature, top_p, top_k, num_predict, num_ctx,
        repeat_penalty, repeat_last_n — based on current thermal state.

        🆕 Punto di partenza fisso: i PARAMETER effettivi del Modelfile di
        Ollama (se disponibili) hanno priorità sui valori di config.toml.
        L'ottimizzatore può esplorare solo in un intorno limitato attorno a
        questi valori ufficiali.
        """
        # 1) Leggi i PARAMETER effettivi dal Modelfile di Ollama
        model_name = model_cfg.get("name", "")
        modelfile_params = {}
        if model_name:
            try:
                from CORE.ollama_modelfile import get_modelfile_params
                modelfile_params = get_modelfile_params(model_name)
            except Exception:
                modelfile_params = {}

        # 2) Base di partenza: Modelfile > config.toml > default
        def _pick(key, default=None):
            if key in modelfile_params and modelfile_params[key] is not None:
                return modelfile_params[key]
            if key in model_cfg and model_cfg[key] is not None:
                return model_cfg[key]
            return default

        options = {
            "temperature": _pick("temperature", 0.1),
            "top_p": _pick("top_p", 0.8),
            "top_k": _pick("top_k", 40),
            "repeat_penalty": _pick("repeat_penalty", 1.1),
            "repeat_last_n": _pick("repeat_last_n", 256),
            "num_ctx": _pick("num_ctx", DEFAULT_NUM_CTX),
            "num_predict": max_tokens or _pick("num_predict", 256),
        }
        if "seed" in model_cfg and model_cfg["seed"] is not None:
            options["seed"] = model_cfg["seed"]
        elif "seed" in modelfile_params and modelfile_params["seed"] is not None:
            options["seed"] = modelfile_params["seed"]

        # 🆕 Apply TimestralLLMTuner if available
        if hasattr(self, "llm_tuner") and self.llm_tuner:
            try:
                tuned = self.llm_tuner.get_params(model_key)
                # Override with tuned values (except num_predict if max_tokens was explicit)
                for key in ("temperature", "top_p", "top_k", "num_ctx",
                            "repeat_penalty", "repeat_last_n"):
                    if key in tuned:
                        options[key] = tuned[key]
                # num_predict: use explicit max_tokens if provided, else tuned
                if max_tokens is None:
                    options["num_predict"] = tuned.get("num_predict", options["num_predict"])
            except Exception as e:
                self.log.debug(f"llm_tuner failed (using static config): {e}")

        return self._clamp_options(options, model_key)

    def _clamp_options(self, options: dict, model_key: str = "") -> dict:
        """Applica clamp di sicurezza alle opzioni del modello.

        Non lasciare mai uscire dall'ottimizzatore:
          - repeat_penalty >= 1.05 (sotto 1.05 il modello tende a ripetere)
          - temperatura > 0 per modelli piccoli (temperatura 0 è deterministica
            ma può incollare il modello su un singolo token in loop)
        I valori sono punti di partenza sicuri; l'ottimizzatore può esplorare
        solo in un intorno limitato.
        """
        clamped = dict(options)
        # Clamp repeat_penalty: minimo 1.05
        if "repeat_penalty" in clamped:
            try:
                clamped["repeat_penalty"] = max(1.05, float(clamped["repeat_penalty"]))
            except (TypeError, ValueError):
                clamped["repeat_penalty"] = 1.15
        # Clamp temperatura: mai 0 per modelli piccoli (Qwen 1.5B/3B)
        if "temperature" in clamped:
            try:
                t = float(clamped["temperature"])
                if t <= 0:
                    t = 0.1
                clamped["temperature"] = max(0.05, min(1.0, t))
            except (TypeError, ValueError):
                clamped["temperature"] = 0.1
        # repeat_last_n sempre attivo e in range sicuro [64, 256]
        if "repeat_last_n" in clamped:
            try:
                clamped["repeat_last_n"] = max(64, min(256, int(clamped["repeat_last_n"])))
            except (TypeError, ValueError):
                clamped["repeat_last_n"] = 256
        # num_predict sempre finito
        if "num_predict" in clamped:
            try:
                clamped["num_predict"] = max(32, min(4096, int(clamped["num_predict"])))
            except (TypeError, ValueError):
                clamped["num_predict"] = 512
        return clamped
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
        """Scarica o mantiene un modello in RAM in base al profilo hardware.

        Comportamento:
          - Hardware tradizionale (cpu_only, VRAM dedicata piccola): keep_alive=0
            → scarica subito per liberare RAM (comportamento originale)
          - Memoria unificata Apple Silicon ≥16GB: keep_alive=300-600s
            → mantiene il modello in RAM per riuso rapido
          - NVIDIA/AMD con VRAM ≥20GB: keep_alive=300s
            → mantiene su VRAM dedicata
          - Override manuale da CONFIG/config.toml [hardware].keep_alive_sec
        """
        if not model_name:
            return
        # Determina keep_alive dal profilo hardware o dal config
        try:
            from CORE.hardware_detector import get_keep_alive_override
            keep_alive = get_keep_alive_override(getattr(self, "cfg", None))
        except Exception:
            keep_alive = 0  # fallback: scarica subito (comportamento originale)
        try:
            payload = {
                "model": model_name,
                "messages": [],
                "keep_alive": keep_alive,
            }
            self._post("/api/chat", payload, timeout=30)
            if keep_alive > 0:
                self.log.debug(f"unloaded {model_name} (keep_alive={keep_alive}s — resterà in RAM)")
            else:
                self.log.debug(f"unloaded {model_name} (keep_alive=0 — scaricato subito)")
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
