#!/usr/bin/env python3
"""
feature1_streaming.py — Streaming token real-time nel Live Activity Panel.

Modifiche:
1. CORE/ollama_client.py: aggiunge call_streaming() che yielda token
2. CORE/orchestrator.py: worker usa streaming, scrive su state/streaming.txt
3. GUI/main_window.py: LiveActivityPanel legge streaming.txt e mostra token live
"""
import re
import shutil
from pathlib import Path

OLLAMA_FILE = Path("CORE/ollama_client.py")
OLLAMA_BACKUP = Path("CORE/ollama_client.py.bak.streaming")
ORCH_FILE = Path("CORE/orchestrator.py")
ORCH_BACKUP = Path("CORE/orchestrator.py.bak.streaming")
GUI_FILE = Path("GUI/main_window.py")
GUI_BACKUP = Path("GUI/main_window.py.bak.streaming")


# ====================================================================
# 1. CORE/ollama_client.py: aggiungi call_streaming()
# ====================================================================

OLLAMA_PATCH = '''
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

'''


# ====================================================================
# 2. CORE/orchestrator.py: worker usa streaming
# ====================================================================

# Trova la chiamata models.call nel worker e sostituiscila con streaming
ORCH_OLD_CALL = '''            try:
                raw = self.models.call(
                    model_key=self.model_key,
                    prompt=prompt,
                    system=self.SYSTEM,
                    max_tokens=400,
                )
            except Exception as e:
                self.log.error(f"[{self.agent_id}] model call failed: {e}")
                return f"ERROR: model unavailable: {e}"'''

ORCH_NEW_CALL = '''            try:
                # 🆕 Streaming: raccogli token e scrivi su file per la GUI
                streaming_file = Path("state/streaming.txt")
                streaming_file.parent.mkdir(parents=True, exist_ok=True)
                streaming_file.write_text("")  # reset all'inizio di ogni call
                
                raw_parts = []
                token_count = 0
                for token in self.models.call_streaming(
                    model_key=self.model_key,
                    prompt=prompt,
                    system=self.SYSTEM,
                    max_tokens=400,
                ):
                    raw_parts.append(token)
                    token_count += 1
                    # Scrivi su file (append) per la GUI
                    with open(streaming_file, "a", encoding="utf-8") as f:
                        f.write(token)
                    # Log ogni 50 token
                    if token_count % 50 == 0:
                        self.log.debug(f"[{self.agent_id}] streaming: {token_count} tokens")
                
                raw = "".join(raw_parts)
                self.log.debug(f"[{self.agent_id}] streaming done: {token_count} tokens total")
            except Exception as e:
                self.log.error(f"[{self.agent_id}] model call failed: {e}")
                return f"ERROR: model unavailable: {e}"'''


# ====================================================================
# 3. GUI/main_window.py: LiveActivityPanel mostra streaming
# ====================================================================

GUI_OLD_REFRESH = '''        # Avvia spinner
        if not self.spinner_timer.isActive():
            self.spinner_timer.start(120)'''

GUI_NEW_REFRESH = '''        # 🆕 Mostra token streaming
        try:
            streaming_file = Path("state/streaming.txt")
            if streaming_file.exists():
                content = streaming_file.read_text(encoding="utf-8", errors="replace")
                if content:
                    # Mostra ultimi 400 caratteri
                    display = content[-400:] if len(content) > 400 else content
                    # Pulisci per display (rimuovi newline eccessivi)
                    display = display.replace("\\n", " ⏎ ").strip()
                    if hasattr(self, 'thought_label'):
                        self.thought_label.setText(f"⚡ Streaming: {display}")
                        self.thought_label.setStyleSheet(
                            "color: #50fa7b; font-family: monospace; "
                            "font-size: 9pt; padding: 2px 0;"
                        )
        except Exception:
            pass

        # Avvia spinner
        if not self.spinner_timer.isActive():
            self.spinner_timer.start(120)'''

# Aggiungi anche un timer più veloce quando c'è streaming
GUI_OLD_TIMER = '''        # Timer aggiornamento dati (1.5s)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1500)'''

GUI_NEW_TIMER = '''        # Timer aggiornamento dati (300ms per streaming real-time)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(300)'''


def patch_ollama():
    """Aggiunge call_streaming a ollama_client.py."""
    if not OLLAMA_FILE.exists():
        print("❌ ollama_client.py non trovato")
        return False
    
    content = OLLAMA_FILE.read_text()
    
    if "def call_streaming" in content:
        print("ℹ  call_streaming già presente, skip")
        return True
    
    shutil.copy2(OLLAMA_FILE, OLLAMA_BACKUP)
    
    # Inserisci call_streaming prima di embed()
    insert_point = "    def embed(self, text: str) -> list:"
    if insert_point not in content:
        print("❌ Punto inserimento non trovato in ollama_client.py")
        return False
    
    content = content.replace(insert_point, OLLAMA_PATCH + "\n" + insert_point, 1)
    OLLAMA_FILE.write_text(content)
    
    try:
        compile(content, "ollama_client.py", "exec")
        print("✓ call_streaming() aggiunto a ollama_client.py")
        return True
    except SyntaxError as e:
        print(f"❌ Errore sintassi: {e}")
        shutil.copy2(OLLAMA_BACKUP, OLLAMA_FILE)
        return False


def patch_orchestrator():
    """Worker usa streaming invece di call normale."""
    if not ORCH_FILE.exists():
        print("❌ orchestrator.py non trovato")
        return False
    
    content = ORCH_FILE.read_text()
    
    if "call_streaming" in content:
        print("ℹ  Worker già usa streaming, skip")
        return True
    
    if ORCH_OLD_CALL not in content:
        print("⚠  Pattern chiamata worker non trovato esattamente")
        # Prova con regex più flessibile
        pattern = re.compile(
            r'            try:\s*\n\s*raw = self\.models\.call\(\s*\n\s*model_key=self\.model_key,.*?return f"ERROR: model unavailable: \{e\}"',
            re.DOTALL
        )
        if pattern.search(content):
            content = pattern.sub(ORCH_NEW_CALL, content, count=1)
        else:
            print("❌ Impossibile trovare la chiamata worker")
            return False
    else:
        content = content.replace(ORCH_OLD_CALL, ORCH_NEW_CALL, 1)
    
    shutil.copy2(ORCH_FILE, ORCH_BACKUP)
    ORCH_FILE.write_text(content)
    
    try:
        compile(content, "orchestrator.py", "exec")
        print("✓ Worker usa streaming in orchestrator.py")
        return True
    except SyntaxError as e:
        print(f"❌ Errore sintassi: {e}")
        shutil.copy2(ORCH_BACKUP, ORCH_FILE)
        return False


def patch_gui():
    """LiveActivityPanel legge streaming.txt e mostra token live."""
    if not GUI_FILE.exists():
        print("❌ main_window.py non trovato")
        return False
    
    content = GUI_FILE.read_text()
    shutil.copy2(GUI_FILE, GUI_BACKUP)
    modified = False
    
    # 1. Aggiorna _refresh per mostrare streaming
    if "state/streaming.txt" not in content:
        if GUI_OLD_REFRESH in content:
            content = content.replace(GUI_OLD_REFRESH, GUI_NEW_REFRESH, 1)
            modified = True
            print("✓ _refresh aggiorna streaming token")
        else:
            print("⚠  Pattern _refresh non trovato")
    
    # 2. Timer più veloce (300ms invece di 1500ms)
    if "self.timer.start(300)" not in content:
        if GUI_OLD_TIMER in content:
            content = content.replace(GUI_OLD_TIMER, GUI_NEW_TIMER, 1)
            modified = True
            print("✓ Timer LiveActivityPanel: 1.5s → 300ms (streaming real-time)")
        else:
            print("⚠  Pattern timer non trovato")
    
    if modified:
        GUI_FILE.write_text(content)
        try:
            compile(content, "main_window.py", "exec")
            print("✓ GUI aggiornata per streaming")
            return True
        except SyntaxError as e:
            print(f"❌ Errore sintassi: {e}")
            shutil.copy2(GUI_BACKUP, GUI_FILE)
            return False
    else:
        print("ℹ  GUI già patchata o pattern non trovati")
        return True


def main():
    print("=" * 60)
    print("FEATURE 1: STREAMING TOKEN REAL-TIME")
    print("=" * 60)
    print()
    
    print("→ Patch ollama_client.py")
    patch_ollama()
    print()
    
    print("→ Patch orchestrator.py")
    patch_orchestrator()
    print()
    
    print("→ Patch GUI/main_window.py")
    patch_gui()
    print()
    
    print("=" * 60)
    print("✓ FEATURE 1 COMPLETATA")
    print("=" * 60)
    print()
    print("Cosa cambia:")
    print("  - Il worker genera token in streaming (non aspetta tutto)")
    print("  - I token vengono scritti su state/streaming.txt")
    print("  - Il LiveActivityPanel si aggiorna ogni 300ms")
    print("  - Vedi i token apparire in tempo reale nel pannello")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh")
    print()
    print("Test: aggiungi un task e guarda il pannello Live Activity")
    print("  dovresti vedere '⚡ Streaming: ...' con i token che appaiono")


if __name__ == "__main__":
    main()
