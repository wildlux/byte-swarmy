"""
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
    
    print("\nProfiles (no timestral → normal):")
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
        print(f"\n  [{action}] {profile.reason}")
        print(f"    temperature={params['temperature']:.2f}  top_p={params['top_p']:.2f}  "
              f"top_k={params['top_k']}")
        print(f"    num_predict={params['num_predict']}  num_ctx={params['num_ctx']}  "
              f"max_steps={profile.max_steps}")
        print(f"    repeat_penalty={params['repeat_penalty']:.2f}")
    
    print("\n" + "=" * 60)
    print("Status line:")
    print("  " + tuner.format_status())
