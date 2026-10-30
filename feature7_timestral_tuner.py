#!/usr/bin/env python3
"""
feature7_timestral_tuner.py — Timestral ottimizza i parametri LLM.

Cosa fa:
1. Crea CORE/llm_tuner.py con algoritmo di tuning basato su stato termico
2. Patcha ollama_client.py per usare i parametri tunati
3. Patcha orchestrator.py per MAX_STEPS dinamico
4. Aggiunge sezione [llm_tuner] in config.toml
"""
import re
import shutil
from pathlib import Path

TUNER_FILE = Path("CORE/llm_tuner.py")
ORCH_FILE = Path("CORE/orchestrator.py")
ORCH_BACKUP = Path("CORE/orchestrator.py.bak.tuner")
OLLAMA_FILE = Path("CORE/ollama_client.py")
OLLAMA_BACKUP = Path("CORE/ollama_client.py.bak.tuner")
CONFIG_FILE = Path("CONFIG/config.toml")
CONFIG_BACKUP = Path("CONFIG/config.toml.bak.tuner")
GUI_FILE = Path("GUI/main_window.py")
GUI_BACKUP = Path("GUI/main_window.py.bak.tuner")


# ====================================================================
# 1. CORE/llm_tuner.py — algoritmo di tuning
# ====================================================================

TUNER_CODE = '''"""
llm_tuner.py — Timestral LLM parameter optimizer.

Adjusts LLM parameters (temperature, top_p, top_k, num_predict, num_ctx,
repeat_penalty, max_steps) based on the current thermal state.

The goal: when the system is hot, make the model more deterministic and
produce less output per step (less KV cache, less VRAM, less spill-over
to CPU). When the system is cold, allow more creativity and longer output.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("byte-swarmy.llm_tuner")


# ====================================================================
# Thermal profiles (cold / warm / hot / critical)
# ====================================================================

@dataclass
class LLMProfile:
    """Set of LLM parameters for a given thermal state."""
    name: str
    temperature: float
    top_p: float
    top_k: int
    num_predict: int
    num_ctx: int
    repeat_penalty: float
    repeat_last_n: int
    max_steps: int
    reason: str


# Profiles (matches the 4 Timestral states)
PROFILES = {
    "fast": LLMProfile(
        name="fast",
        temperature=0.25,        # più creativo
        top_p=0.92,
        top_k=45,
        num_predict=600,         # output lungo
        num_ctx=3072,
        repeat_penalty=1.0,
        repeat_last_n=64,
        max_steps=8,
        reason="cold system: creative, long output",
    ),
    "normal": LLMProfile(
        name="normal",
        temperature=0.15,
        top_p=0.85,
        top_k=35,
        num_predict=450,
        num_ctx=3072,
        repeat_penalty=1.10,
        repeat_last_n=64,
        max_steps=6,
        reason="normal: balanced",
    ),
    "slow": LLMProfile(
        name="slow",
        temperature=0.08,        # più deterministico
        top_p=0.78,
        top_k=28,
        num_predict=300,         # output più corto
        num_ctx=2048,            # meno KV cache
        repeat_penalty=1.20,     # anti-loop
        repeat_last_n=96,
        max_steps=5,
        reason="hot system: deterministic, short output, less KV",
    ),
    "pause": LLMProfile(
        name="pause",
        temperature=0.05,
        top_p=0.70,
        top_k=20,
        num_predict=200,
        num_ctx=1536,            # minimo KV cache
        repeat_penalty=1.35,
        repeat_last_n=128,
        max_steps=4,
        reason="critical: minimal work, max determinism",
    ),
}


# ====================================================================
# Tuner
# ====================================================================

class TimestralLLMTuner:
    """Optimizes LLM parameters based on Timestral thermal advice.
    
    Usage:
        tuner = TimestralLLMTuner(timestral_manager)
        params = tuner.get_params("worker_coder")
        # params is a dict ready for ollama options
    """
    
    def __init__(self, timestral_manager=None, config: dict = None):
        self.timestral = timestral_manager
        self.cfg = config or {}
        # Override profiles from config if present
        self._load_overrides()
        self.last_profile: Optional[LLMProfile] = None
        self.last_action: str = "normal"
    
    def _load_overrides(self):
        """Load profile overrides from [llm_tuner] section in config."""
        tuner_cfg = self.cfg.get("llm_tuner", {})
        if not tuner_cfg:
            return
        # Allow per-profile overrides
        for profile_name, profile in PROFILES.items():
            section = tuner_cfg.get(profile_name, {})
            if not isinstance(section, dict):
                continue
            if "temperature" in section:
                profile.temperature = float(section["temperature"])
            if "top_p" in section:
                profile.top_p = float(section["top_p"])
            if "top_k" in section:
                profile.top_k = int(section["top_k"])
            if "num_predict" in section:
                profile.num_predict = int(section["num_predict"])
            if "num_ctx" in section:
                profile.num_ctx = int(section["num_ctx"])
            if "repeat_penalty" in section:
                profile.repeat_penalty = float(section["repeat_penalty"])
            if "max_steps" in section:
                profile.max_steps = int(section["max_steps"])
    
    def get_action(self) -> str:
        """Get current Timestral action: fast|normal|slow|pause."""
        if not self.timestral:
            return "normal"
        try:
            advice = self.timestral.get_advice()
            return advice.action
        except Exception:
            return "normal"
    
    def get_profile(self) -> LLMProfile:
        """Get the LLM profile for the current thermal state."""
        action = self.get_action()
        # Map Timestral action to profile
        # "fast" → fast, "normal" → normal, "slow" → slow, "pause" → pause
        profile = PROFILES.get(action, PROFILES["normal"])
        self.last_profile = profile
        self.last_action = action
        return profile
    
    def get_params(self, model_key: str = "") -> dict:
        """Get tuned parameters as a dict ready for ollama options.
        
        Args:
            model_key: model role (orchestrator, planner, worker_coder, etc.)
                       Used for logging only.
        
        Returns:
            dict with: temperature, top_p, top_k, num_predict, num_ctx,
                       repeat_penalty, repeat_last_n
        """
        profile = self.get_profile()
        
        # Don't go above the model's configured num_ctx
        # (the tuner can only reduce it, not increase)
        if self.cfg and model_key:
            model_cfg = self.cfg.get("models", {}).get(model_key, {})
            max_ctx = model_cfg.get("num_ctx", 4096)
            if profile.num_ctx > max_ctx:
                # Use a copy to not mutate the profile
                params = self._profile_to_params(profile)
                params["num_ctx"] = max_ctx
                return params
        
        params = self._profile_to_params(profile)
        
        log.debug(
            f"llm_tuner: model={model_key} action={self.last_action} "
            f"temp={params['temperature']:.2f} top_p={params['top_p']:.2f} "
            f"num_predict={params['num_predict']} num_ctx={params['num_ctx']} "
            f"max_steps={profile.max_steps}"
        )
        return params
    
    def _profile_to_params(self, profile: LLMProfile) -> dict:
        return {
            "temperature": profile.temperature,
            "top_p": profile.top_p,
            "top_k": profile.top_k,
            "num_predict": profile.num_predict,
            "num_ctx": profile.num_ctx,
            "repeat_penalty": profile.repeat_penalty,
            "repeat_last_n": profile.repeat_last_n,
        }
    
    def get_max_steps(self) -> int:
        """Get the dynamic MAX_STEPS for the current thermal state."""
        profile = self.get_profile()
        return profile.max_steps
    
    def format_status(self) -> str:
        """Format the tuner status for display in the GUI."""
        profile = self.get_profile()
        return (
            f"🎚️ Tuned [{profile.name}]: "
            f"temp={profile.temperature:.2f} "
            f"top_p={profile.top_p:.2f} "
            f"predict={profile.num_predict} "
            f"ctx={profile.num_ctx} "
            f"steps={profile.max_steps}"
        )


# ====================================================================
# Self-test
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("LLM TUNER - TEST")
    print("=" * 60)
    
    tuner = TimestralLLMTuner(timestral_manager=None, config={})
    
    print("\\nProfiles (no timestral → normal):")
    for action in ["fast", "normal", "slow", "pause"]:
        # Simulate timestral
        class FakeTimestral:
            def get_advice(self):
                from dataclasses import dataclass
                @dataclass
                class FakeAdvice:
                    action: str
                return FakeAdvice(action=action)
        
        tuner.timestral = FakeTimestral()
        profile = tuner.get_profile()
        params = tuner.get_params("worker_coder")
        print(f"\\n  [{action}] {profile.reason}")
        print(f"    temperature={params['temperature']:.2f}  top_p={params['top_p']:.2f}  "
              f"top_k={params['top_k']}")
        print(f"    num_predict={params['num_predict']}  num_ctx={params['num_ctx']}  "
              f"max_steps={profile.max_steps}")
        print(f"    repeat_penalty={params['repeat_penalty']:.2f}")
    
    print("\\n" + "=" * 60)
    print("Status line:")
    print("  " + tuner.format_status())
'''


# ====================================================================
# 2. Patch ollama_client.py per usare il tuner
# ====================================================================

OLLAMA_PATCH = '''
    def _get_tuned_options(self, model_key: str, model_cfg: dict,
                            max_tokens: Optional[int] = None) -> dict:
        """Build options dict, applying TimestralLLMTuner if available.
        
        The tuner overrides: temperature, top_p, top_k, num_predict, num_ctx,
        repeat_penalty, repeat_last_n — based on current thermal state.
        """
        # Start with config values
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
        
        return options

'''

# Trova e modifica il metodo call() per usare _get_tuned_options
OLLAMA_CALL_OLD = '''        # Costruisci payload
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
            options["seed"] = model_cfg["seed"]'''

OLLAMA_CALL_NEW = '''        # 🆕 Build options with TimestralLLMTuner (if available)
        options = self._get_tuned_options(model_key, model_cfg, max_tokens)'''

# Stesso per call_streaming
OLLAMA_STREAM_OLD = '''        options = {
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
        }'''

OLLAMA_STREAM_NEW = '''        # 🆕 Build options with TimestralLLMTuner (if available)
        options = self._get_tuned_options(model_key, model_cfg, max_tokens)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "options": options,
            "stream": True,  # STREAMING ATTIVO
        }'''

# Aggiungi attributo llm_tuner in __init__
OLLAMA_INIT_OLD = '''        self.current_model: Optional[str] = None
        self.last_call_ts: float = 0'''

OLLAMA_INIT_NEW = '''        self.current_model: Optional[str] = None
        self.last_call_ts: float = 0
        self.llm_tuner = None  # 🆕 TimestralLLMTuner (set by orchestrator)'''


# ====================================================================
# 3. Patch orchestrator.py: collega il tuner + MAX_STEPS dinamico
# ====================================================================

ORCH_INIT_OLD = '''        self.models = ModelClient(self.config, self.log)'''

ORCH_INIT_NEW = '''        self.models = ModelClient(self.config, self.log)
        # 🆕 Initialize LLM tuner (will be connected to Timestral later)
        try:
            from CORE.llm_tuner import TimestralLLMTuner
            self.llm_tuner = TimestralLLMTuner(timestral_manager=None, config=self.config)
            self.models.llm_tuner = self.llm_tuner  # connect to ModelClient
        except Exception as e:
            self.log.warning(f"llm_tuner init failed: {e}")
            self.llm_tuner = None'''

# Collega il tuner a Timestral dopo che Timestral è stato creato
ORCH_TIMESTRAL_OLD = '''        self.timestral = None
        if self.config.get("thermal", {}).get("enabled", False):
            try:
                self.timestral = TimestralManager(self.config, self.log, base_dir=Path(self.config["paths"]["state_dir"]).parent)
                self.timestral.start()'''

ORCH_TIMESTRAL_NEW = '''        self.timestral = None
        if self.config.get("thermal", {}).get("enabled", False):
            try:
                self.timestral = TimestralManager(self.config, self.log, base_dir=Path(self.config["paths"]["state_dir"]).parent)
                self.timestral.start()
                # 🆕 Connect tuner to Timestral
                if self.llm_tuner:
                    self.llm_tuner.timestral = self.timestral
                    self.log.info("llm_tuner connected to Timestral")'''

# MAX_STEPS dinamico in Worker.execute
# Cerca "for step in range(self.MAX_STEPS):"
ORCH_MAX_STEPS_OLD = '''        for step in range(self.MAX_STEPS):'''

ORCH_MAX_STEPS_NEW = '''        # 🆕 Dynamic MAX_STEPS from TimestralLLMTuner
        try:
            from CORE.orchestrator import Orchestrator as _Orch
            # Access the global orchestrator instance via models.llm_tuner
            if hasattr(self.models, "llm_tuner") and self.models.llm_tuner:
                current_max = self.models.llm_tuner.get_max_steps()
            else:
                current_max = self.MAX_STEPS
        except Exception:
            current_max = self.MAX_STEPS
        
        for step in range(current_max):'''


# ====================================================================
# 4. Sezione [llm_tuner] in config.toml
# ====================================================================

TUNER_CONFIG = '''
# ====================================================================
# LLM Tuner — Timestral ottimizza i parametri LLM in base allo stato termico
# ====================================================================
[llm_tuner]
# Il tuner è attivo se [thermal].enabled = true
# Override dei profili (opzionale, lasciare commentato per usare i default)

[llm_tuner.fast]
# Sistema freddo (< 50°C): creativo, output lungo
# temperature = 0.25
# top_p = 0.92
# num_predict = 600
# num_ctx = 3072
# max_steps = 8

[llm_tuner.normal]
# Sistema normale (50-65°C): bilanciato
# temperature = 0.15
# top_p = 0.85
# num_predict = 450
# num_ctx = 3072
# max_steps = 6

[llm_tuner.slow]
# Sistema caldo (65-85°C): deterministico, output corto
# temperature = 0.08
# top_p = 0.78
# num_predict = 300
# num_ctx = 2048
# max_steps = 5

[llm_tuner.pause]
# Sistema critico (> 85°C): lavoro minimo
# temperature = 0.05
# top_p = 0.70
# num_predict = 200
# num_ctx = 1536
# max_steps = 4
'''


# ====================================================================
# 5. GUI: mostra "Tuned" indicator nel Live Activity Panel
# ====================================================================

GUI_REFRESH_OLD = '''        # Avvia spinner
        if not self.spinner_timer.isActive():
            self.spinner_timer.start(120)'''

GUI_REFRESH_NEW = '''        # 🆕 Mostra stato LLM tuner
        try:
            from CORE.llm_tuner import TimestralLLMTuner
            # Crea un tuner temporaneo per leggere lo stato (no timestral connection)
            # In futuro: leggere dall'orchestrator vero
            import sqlite3
            from pathlib import Path
            # Leggi l'ultimo advice dal file di stato (se esiste)
            tuner_status = ""
            advice_file = Path("state/timestral_advice.json")
            if advice_file.exists():
                import json
                advice_data = json.loads(advice_file.read_text())
                action = advice_data.get("action", "normal")
                # Map action to profile
                profile_map = {
                    "fast": ("FAST", "cold: creative"),
                    "normal": ("NORMAL", "balanced"),
                    "slow": ("SLOW", "hot: deterministic"),
                    "pause": ("PAUSE", "critical: minimal"),
                }
                label, desc = profile_map.get(action, ("NORMAL", "balanced"))
                tuner_status = f"🎚️ LLM Tuned: {label} ({desc})"
            
            if hasattr(self, "tuner_label"):
                if tuner_status:
                    self.tuner_label.setText(tuner_status)
                    self.tuner_label.setStyleSheet(
                        "color: #ff79c6; font-family: monospace; "
                        "font-size: 9pt; padding: 2px 0;"
                    )
                else:
                    self.tuner_label.setText("🎚️ LLM Tuned: (no data)")
        except Exception:
            pass

        # Avvia spinner
        if not self.spinner_timer.isActive():
            self.spinner_timer.start(120)'''

# Aggiungi la label tuner_label alla UI del LiveActivityPanel
GUI_BUILD_OLD = '''        # 🆕 Riga VRAM (modelli caricati)
        self.vram_label = QLabel("💾 VRAM: ...")'''

GUI_BUILD_NEW = '''        # 🆕 Riga LLM Tuner (parametri ottimizzati)
        self.tuner_label = QLabel("🎚️ LLM Tuned: ...")
        self.tuner_label.setStyleSheet(
            "color: #ff79c6; font-family: monospace; font-size: 9pt; "
            "padding: 2px 0;"
        )
        self.tuner_label.setWordWrap(True)
        gl.addWidget(self.tuner_label)

        # 🆕 Riga VRAM (modelli caricati)
        self.vram_label = QLabel("💾 VRAM: ...")'''


# ====================================================================
# Esecuzione
# ====================================================================

def main():
    print("=" * 60)
    print("FEATURE 7: TIMESTRAL LLM PARAMETER OPTIMIZER")
    print("=" * 60)
    print()
    
    # 1. Crea CORE/llm_tuner.py
    print("→ Creazione CORE/llm_tuner.py")
    if TUNER_FILE.exists():
        print("  ℹ  già esiste, skip")
    else:
        TUNER_FILE.write_text(TUNER_CODE)
        try:
            compile(TUNER_CODE, "llm_tuner.py", "exec")
            print("  ✓ Creato CORE/llm_tuner.py")
        except SyntaxError as e:
            print(f"  ❌ Errore sintassi: {e}")
            return 1
    
    # 2. Patch ollama_client.py
    print()
    print("→ Patch ollama_client.py")
    if not OLLAMA_FILE.exists():
        print("  ❌ non trovato")
        return 1
    
    content = OLLAMA_FILE.read_text()
    if "_get_tuned_options" in content:
        print("  ℹ  già patchato, skip")
    else:
        shutil.copy2(OLLAMA_FILE, OLLAMA_BACKUP)
        modified = False
        
        # Aggiungi attributo llm_tuner in __init__
        if OLLAMA_INIT_OLD in content:
            content = content.replace(OLLAMA_INIT_OLD, OLLAMA_INIT_NEW, 1)
            modified = True
            print("  ✓ Aggiunto attributo llm_tuner in __init__")
        
        # Aggiungi metodo _get_tuned_options prima di embed()
        insert_point = "    def embed(self, text: str) -> list:"
        if insert_point in content and "_get_tuned_options" not in content:
            content = content.replace(insert_point, OLLAMA_PATCH + "\n" + insert_point, 1)
            modified = True
            print("  ✓ Aggiunto metodo _get_tuned_options()")
        
        # Patch call() per usare _get_tuned_options
        if OLLAMA_CALL_OLD in content:
            content = content.replace(OLLAMA_CALL_OLD, OLLAMA_CALL_NEW, 1)
            modified = True
            print("  ✓ call() usa _get_tuned_options()")
        else:
            print("  ⚠  Pattern call() non trovato")
        
        # Patch call_streaming() per usare _get_tuned_options
        if OLLAMA_STREAM_OLD in content:
            content = content.replace(OLLAMA_STREAM_OLD, OLLAMA_STREAM_NEW, 1)
            modified = True
            print("  ✓ call_streaming() usa _get_tuned_options()")
        else:
            print("  ⚠  Pattern call_streaming() non trovato")
        
        if modified:
            OLLAMA_FILE.write_text(content)
            try:
                compile(content, "ollama_client.py", "exec")
                print("  ✓ Verifica sintassi OK")
            except SyntaxError as e:
                print(f"  ❌ Errore sintassi: {e}")
                shutil.copy2(OLLAMA_BACKUP, OLLAMA_FILE)
                return 1
    
    # 3. Patch orchestrator.py
    print()
    print("→ Patch orchestrator.py")
    if not ORCH_FILE.exists():
        print("  ❌ non trovato")
        return 1
    
    content = ORCH_FILE.read_text()
    if "self.llm_tuner = TimestralLLMTuner" in content:
        print("  ℹ  già patchato, skip")
    else:
        shutil.copy2(ORCH_FILE, ORCH_BACKUP)
        modified = False
        
        # Init tuner dopo ModelClient
        if ORCH_INIT_OLD in content:
            content = content.replace(ORCH_INIT_OLD, ORCH_INIT_NEW, 1)
            modified = True
            print("  ✓ Inizializzazione TimestralLLMTuner in __init__")
        
        # Collega tuner a Timestral
        if ORCH_TIMESTRAL_OLD in content:
            content = content.replace(ORCH_TIMESTRAL_OLD, ORCH_TIMESTRAL_NEW, 1)
            modified = True
            print("  ✓ Tuner collegato a Timestral")
        
        # MAX_STEPS dinamico
        if ORCH_MAX_STEPS_OLD in content and "Dynamic MAX_STEPS" not in content:
            content = content.replace(ORCH_MAX_STEPS_OLD, ORCH_MAX_STEPS_NEW, 1)
            modified = True
            print("  ✓ MAX_STEPS dinamico in Worker.execute")
        
        if modified:
            ORCH_FILE.write_text(content)
            try:
                compile(content, "orchestrator.py", "exec")
                print("  ✓ Verifica sintassi OK")
            except SyntaxError as e:
                print(f"  ❌ Errore sintassi: {e}")
                shutil.copy2(ORCH_BACKUP, ORCH_FILE)
                return 1
    
    # 4. Sezione [llm_tuner] in config.toml
    print()
    print("→ Aggiunta sezione [llm_tuner] in config.toml")
    if not CONFIG_FILE.exists():
        print("  ❌ config.toml non trovato")
    else:
        content = CONFIG_FILE.read_text()
        if "[llm_tuner]" in content:
            print("  ℹ  già presente, skip")
        else:
            shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)
            content = content.rstrip() + "\n" + TUNER_CONFIG
            CONFIG_FILE.write_text(content)
            print("  ✓ Aggiunta sezione [llm_tuner] con profili override")
    
    # 5. Patch GUI per mostrare stato tuner
    print()
    print("→ Patch GUI/main_window.py")
    if not GUI_FILE.exists():
        print("  ❌ main_window.py non trovato")
    else:
        content = GUI_FILE.read_text()
        if "tuner_label" in content:
            print("  ℹ  già patchato, skip")
        else:
            shutil.copy2(GUI_FILE, GUI_BACKUP)
            modified = False
            
            # Aggiungi tuner_label alla UI
            if GUI_BUILD_OLD in content:
                content = content.replace(GUI_BUILD_OLD, GUI_BUILD_NEW, 1)
                modified = True
                print("  ✓ Aggiunta tuner_label al LiveActivityPanel")
            
            # Aggiorna _refresh per popolare tuner_label
            if GUI_REFRESH_OLD in content:
                content = content.replace(GUI_REFRESH_OLD, GUI_REFRESH_NEW, 1)
                modified = True
                print("  ✓ _refresh mostra stato LLM tuner")
            
            if modified:
                GUI_FILE.write_text(content)
                try:
                    compile(content, "main_window.py", "exec")
                    print("  ✓ Verifica sintassi OK")
                except SyntaxError as e:
                    print(f"  ❌ Errore sintassi: {e}")
                    shutil.copy2(GUI_BACKUP, GUI_FILE)
    
    print()
    print("=" * 60)
    print("✓ FEATURE 7 COMPLETATA")
    print("=" * 60)
    print()
    print("Cosa cambia:")
    print("  - Timestral ora ottimizza i parametri LLM (non solo il tick)")
    print("  - 4 profili: fast (freddo) / normal / slow (caldo) / pause (critico)")
    print("  - Parametri tunati: temperature, top_p, top_k, num_predict,")
    print("    num_ctx, repeat_penalty, repeat_last_n, max_steps")
    print("  - GUI mostra '🎚️ LLM Tuned: SLOW (hot: deterministic)'")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh")
    print()
    print("Test:")
    print("  python -m CORE.llm_tuner  # self-test dei 4 profili")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
