"""CORE/model_catalog.py — Catalogo dei modelli Ollama più comuni.

Fornisce una classifica per categoria dei ~100 modelli più usati, con
descrizione, uso consigliato, RAM stimata e tag. L'utente (o l'agente)
può consultarlo per capire cosa fa un modello scaricato, senza impazzire.

Uso:
    python -m CORE.model_catalog lookup qwen2.5-coder:3b
    python -m CORE.model_catalog list --category coding
    python -m CORE.model_catalog search "vision"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Formato: nome (lowercase) -> dict con categoria, descrizione, uso, ram_gb, tags
CATALOG: dict[str, dict] = {
    # === CODING ===
    "qwen2.5-coder:0.5b": {"cat": "coding", "desc": "Coder ultra-leggero (0.5B)", "use": "autocomplete, snippet", "ram": 0.5, "tags": ["code", "fast"]},
    "qwen2.5-coder:1.5b": {"cat": "coding", "desc": "Coder piccolo", "use": "task semplici, refactoring", "ram": 1.2, "tags": ["code"]},
    "qwen2.5-coder:3b": {"cat": "coding", "desc": "Coder medio, buon rapporto qualità/velocità", "use": "generazione codice, debug", "ram": 2.0, "tags": ["code", "recommended"]},
    "qwen2.5-coder:7b": {"cat": "coding", "desc": "Coder grande, alta qualità", "use": "architettura, refactor complessi", "ram": 4.5, "tags": ["code", "quality"]},
    "qwen2.5-coder:14b": {"cat": "coding", "desc": "Coder molto grande", "use": "task complessi, review", "ram": 9.0, "tags": ["code", "heavy"]},
    "qwen2.5-coder:32b": {"cat": "coding", "desc": "Coder top-tier", "use": "produzione, architettura", "ram": 20.0, "tags": ["code", "heavy"]},
    "codellama:7b": {"cat": "coding", "desc": "CodeLlama base (Meta)", "use": "generazione codice", "ram": 4.0, "tags": ["code"]},
    "codellama:13b": {"cat": "coding", "desc": "CodeLlama medio", "use": "refactoring, debug", "ram": 7.5, "tags": ["code"]},
    "codellama:34b": {"cat": "coding", "desc": "CodeLlama grande", "use": "architettura", "ram": 20.0, "tags": ["code", "heavy"]},
    "codellama:70b": {"cat": "coding", "desc": "CodeLlama top", "use": "produzione", "ram": 40.0, "tags": ["code", "heavy"]},
    "deepseek-coder:1.3b": {"cat": "coding", "desc": "DeepSeek coder piccolo", "use": "snippet, autocomplete", "ram": 1.0, "tags": ["code", "fast"]},
    "deepseek-coder:6.7b": {"cat": "coding", "desc": "DeepSeek coder medio", "use": "generazione codice", "ram": 4.0, "tags": ["code"]},
    "deepseek-coder:33b": {"cat": "coding", "desc": "DeepSeek coder grande", "use": "architettura, review", "ram": 20.0, "tags": ["code", "heavy"]},
    "deepseek-coder-v2:16b": {"cat": "coding", "desc": "DeepSeek Coder V2 (MoE)", "use": "coding avanzato", "ram": 9.0, "tags": ["code", "moe"]},
    "deepseek-coder-v2:236b": {"cat": "coding", "desc": "DeepSeek Coder V2 top (MoE)", "use": "produzione", "ram": 140.0, "tags": ["code", "heavy", "moe"]},
    "starcoder:3b": {"cat": "coding", "desc": "StarCoder piccolo", "use": "autocomplete", "ram": 2.0, "tags": ["code", "fast"]},
    "starcoder:7b": {"cat": "coding", "desc": "StarCoder medio", "use": "generazione codice", "ram": 4.0, "tags": ["code"]},
    "starcoder:15b": {"cat": "coding", "desc": "StarCoder grande", "use": "refactoring", "ram": 9.0, "tags": ["code"]},
    "granite-code:3b": {"cat": "coding", "desc": "Granite Code (IBM) piccolo", "use": "coding enterprise", "ram": 2.0, "tags": ["code", "enterprise"]},
    "granite-code:8b": {"cat": "coding", "desc": "Granite Code medio", "use": "coding enterprise", "ram": 4.5, "tags": ["code", "enterprise"]},
    "granite-code:20b": {"cat": "coding", "desc": "Granite Code grande", "use": "architettura", "ram": 12.0, "tags": ["code", "enterprise"]},
    "granite-code:34b": {"cat": "coding", "desc": "Granite Code top", "use": "produzione", "ram": 20.0, "tags": ["code", "enterprise", "heavy"]},
    "phi3:mini": {"cat": "coding", "desc": "Phi-3 Mini (Microsoft)", "use": "coding leggero, reasoning", "ram": 2.0, "tags": ["code", "light"]},
    "phi3:medium": {"cat": "coding", "desc": "Phi-3 Medium", "use": "coding + reasoning", "ram": 8.0, "tags": ["code", "reasoning"]},
    "phi3:14b": {"cat": "coding", "desc": "Phi-3 14B", "use": "task complessi", "ram": 8.5, "tags": ["code", "heavy"]},
    "phi4:14b": {"cat": "coding", "desc": "Phi-4 (Microsoft)", "use": "coding + math + reasoning", "ram": 8.5, "tags": ["code", "reasoning", "math"]},
    "mistral:7b": {"cat": "coding", "desc": "Mistral base", "use": "coding generico, chat", "ram": 4.0, "tags": ["code", "chat"]},
    "mixtral:8x7b": {"cat": "coding", "desc": "Mixtral (MoE)", "use": "coding + chat avanzato", "ram": 26.0, "tags": ["code", "chat", "moe", "heavy"]},
    "mixtral:8x22b": {"cat": "coding", "desc": "Mixtral grande (MoE)", "use": "produzione", "ram": 80.0, "tags": ["code", "chat", "moe", "heavy"]},
    "wizardcoder:7b": {"cat": "coding", "desc": "WizardCoder", "use": "generazione codice", "ram": 4.0, "tags": ["code"]},
    "wizardcoder:13b": {"cat": "coding", "desc": "WizardCoder medio", "use": "refactoring", "ram": 7.5, "tags": ["code"]},
    "wizardcoder:34b": {"cat": "coding", "desc": "WizardCoder grande", "use": "architettura", "ram": 20.0, "tags": ["code", "heavy"]},
    "magicoder:7b": {"cat": "coding", "desc": "Magicoder", "use": "generazione codice", "ram": 4.0, "tags": ["code"]},
    "codegemma:2b": {"cat": "coding", "desc": "CodeGemma piccolo (Google)", "use": "snippet, autocomplete", "ram": 1.5, "tags": ["code", "fast"]},
    "codegemma:7b": {"cat": "coding", "desc": "CodeGemma medio", "use": "generazione codice", "ram": 4.0, "tags": ["code"]},
    "opencoder:1.5b": {"cat": "coding", "desc": "OpenCoder piccolo", "use": "autocomplete", "ram": 1.2, "tags": ["code", "fast"]},
    "opencoder:8b": {"cat": "coding", "desc": "OpenCoder medio", "use": "generazione codice", "ram": 4.5, "tags": ["code"]},
    "yi-coder:1.5b": {"cat": "coding", "desc": "Yi-Coder piccolo", "use": "snippet", "ram": 1.2, "tags": ["code", "fast"]},
    "yi-coder:9b": {"cat": "coding", "desc": "Yi-Coder medio", "use": "generazione codice", "ram": 5.0, "tags": ["code"]},
    "qwen3-coder:4b": {"cat": "coding", "desc": "Qwen3 Coder 4B (recente)", "use": "coding moderno", "ram": 2.6, "tags": ["code", "recommended"]},
    "qwen3-coder:8b": {"cat": "coding", "desc": "Qwen3 Coder 8B", "use": "coding avanzato", "ram": 4.5, "tags": ["code"]},
    "qwen3-coder:30b": {"cat": "coding", "desc": "Qwen3 Coder 30B", "use": "produzione", "ram": 18.0, "tags": ["code", "heavy"]},
    # === CHAT / GENERAL ===
    "llama3:8b": {"cat": "chat", "desc": "Llama 3 base (Meta)", "use": "chat, Q&A, reasoning", "ram": 4.7, "tags": ["chat", "general"]},
    "llama3:70b": {"cat": "chat", "desc": "Llama 3 grande", "use": "produzione, reasoning", "ram": 40.0, "tags": ["chat", "heavy"]},
    "llama3.1:8b": {"cat": "chat", "desc": "Llama 3.1 base", "use": "chat, tool use", "ram": 4.7, "tags": ["chat", "general", "tools"]},
    "llama3.1:70b": {"cat": "chat", "desc": "Llama 3.1 grande", "use": "produzione", "ram": 40.0, "tags": ["chat", "heavy"]},
    "llama3.1:405b": {"cat": "chat", "desc": "Llama 3.1 top", "use": "massima qualità", "ram": 230.0, "tags": ["chat", "heavy"]},
    "llama3.2:1b": {"cat": "chat", "desc": "Llama 3.2 ultra-leggero", "use": "edge, mobile", "ram": 1.3, "tags": ["chat", "light", "fast"]},
    "llama3.2:3b": {"cat": "chat", "desc": "Llama 3.2 piccolo", "use": "chat leggero", "ram": 2.0, "tags": ["chat", "light"]},
    "llama3.3:70b": {"cat": "chat", "desc": "Llama 3.3 grande", "use": "produzione", "ram": 40.0, "tags": ["chat", "heavy"]},
    "qwen2.5:0.5b": {"cat": "chat", "desc": "Qwen 2.5 ultra-leggero", "use": "edge, mobile", "ram": 0.5, "tags": ["chat", "light", "fast"]},
    "qwen2.5:1.5b": {"cat": "chat", "desc": "Qwen 2.5 piccolo", "use": "chat leggero", "ram": 1.2, "tags": ["chat", "light"]},
    "qwen2.5:3b": {"cat": "chat", "desc": "Qwen 2.5 medio", "use": "chat generico", "ram": 2.0, "tags": ["chat"]},
    "qwen2.5:7b": {"cat": "chat", "desc": "Qwen 2.5 grande", "use": "chat + reasoning", "ram": 4.5, "tags": ["chat", "reasoning"]},
    "qwen2.5:14b": {"cat": "chat", "desc": "Qwen 2.5 molto grande", "use": "produzione", "ram": 9.0, "tags": ["chat", "heavy"]},
    "qwen2.5:32b": {"cat": "chat", "desc": "Qwen 2.5 top", "use": "massima qualità", "ram": 20.0, "tags": ["chat", "heavy"]},
    "qwen2.5:72b": {"cat": "chat", "desc": "Qwen 2.5 enorme", "use": "produzione enterprise", "ram": 45.0, "tags": ["chat", "heavy"]},
    "qwen3:0.6b": {"cat": "chat", "desc": "Qwen 3 ultra-leggero", "use": "edge", "ram": 0.5, "tags": ["chat", "light", "fast"]},
    "qwen3:1.7b": {"cat": "chat", "desc": "Qwen 3 piccolo", "use": "chat leggero", "ram": 1.2, "tags": ["chat", "light"]},
    "qwen3:4b": {"cat": "chat", "desc": "Qwen 3 medio", "use": "chat + reasoning", "ram": 2.5, "tags": ["chat", "reasoning"]},
    "qwen3:8b": {"cat": "chat", "desc": "Qwen 3 grande", "use": "chat avanzato", "ram": 4.5, "tags": ["chat", "reasoning"]},
    "qwen3:14b": {"cat": "chat", "desc": "Qwen 3 molto grande", "use": "produzione", "ram": 9.0, "tags": ["chat", "heavy"]},
    "qwen3:30b": {"cat": "chat", "desc": "Qwen 3 top", "use": "massima qualità", "ram": 18.0, "tags": ["chat", "heavy"]},
    "qwen3:32b": {"cat": "chat", "desc": "Qwen 3 32B", "use": "produzione", "ram": 20.0, "tags": ["chat", "heavy"]},
    "gemma2:2b": {"cat": "chat", "desc": "Gemma 2 piccolo (Google)", "use": "chat leggero", "ram": 1.5, "tags": ["chat", "light"]},
    "gemma2:9b": {"cat": "chat", "desc": "Gemma 2 medio", "use": "chat + reasoning", "ram": 5.0, "tags": ["chat", "reasoning"]},
    "gemma2:27b": {"cat": "chat", "desc": "Gemma 2 grande", "use": "produzione", "ram": 16.0, "tags": ["chat", "heavy"]},
    "gemma3:1b": {"cat": "chat", "desc": "Gemma 3 ultra-leggero", "use": "edge", "ram": 0.8, "tags": ["chat", "light", "fast"]},
    "gemma3:4b": {"cat": "chat", "desc": "Gemma 3 piccolo", "use": "chat leggero", "ram": 2.5, "tags": ["chat", "light"]},
    "gemma3:12b": {"cat": "chat", "desc": "Gemma 3 medio", "use": "chat + reasoning", "ram": 7.0, "tags": ["chat", "reasoning"]},
    "gemma3:27b": {"cat": "chat", "desc": "Gemma 3 grande", "use": "produzione", "ram": 16.0, "tags": ["chat", "heavy"]},
    "mistral:7b": {"cat": "chat", "desc": "Mistral base", "use": "chat generico", "ram": 4.0, "tags": ["chat"]},
    "mistral-nemo:12b": {"cat": "chat", "desc": "Mistral Nemo", "use": "chat avanzato", "ram": 7.0, "tags": ["chat"]},
    "mistral-small:22b": {"cat": "chat", "desc": "Mistral Small", "use": "produzione", "ram": 13.0, "tags": ["chat", "heavy"]},
    "mistral-large:123b": {"cat": "chat", "desc": "Mistral Large", "use": "massima qualità", "ram": 70.0, "tags": ["chat", "heavy"]},
    "phi4:14b": {"cat": "chat", "desc": "Phi-4 (Microsoft)", "use": "chat + reasoning + math", "ram": 8.5, "tags": ["chat", "reasoning", "math"]},
    "phi4-mini:3.8b": {"cat": "chat", "desc": "Phi-4 Mini", "use": "chat leggero", "ram": 2.5, "tags": ["chat", "light"]},
    "tinyllama:1.1b": {"cat": "chat", "desc": "TinyLlama ultra-leggero", "use": "edge, mobile", "ram": 0.7, "tags": ["chat", "light", "fast"]},
    "orca-mini:3b": {"cat": "chat", "desc": "Orca Mini", "use": "chat leggero", "ram": 2.0, "tags": ["chat", "light"]},
    "orca-mini:7b": {"cat": "chat", "desc": "Orca Mini 7B", "use": "chat generico", "ram": 4.0, "tags": ["chat"]},
    "vicuna:7b": {"cat": "chat", "desc": "Vicuna (fine-tuned Llama)", "use": "chat", "ram": 4.0, "tags": ["chat"]},
    "vicuna:13b": {"cat": "chat", "desc": "Vicuna 13B", "use": "chat avanzato", "ram": 7.5, "tags": ["chat"]},
    "neural-chat:7b": {"cat": "chat", "desc": "Neural Chat (Intel)", "use": "chat ottimizzato CPU", "ram": 4.0, "tags": ["chat", "cpu"]},
    "openchat:7b": {"cat": "chat", "desc": "OpenChat", "use": "chat generico", "ram": 4.0, "tags": ["chat"]},
    "starling-lm:7b": {"cat": "chat", "desc": "Starling LM", "use": "chat avanzato", "ram": 4.0, "tags": ["chat"]},
    "zephyr:7b": {"cat": "chat", "desc": "Zephyr (HuggingFace)", "use": "chat allineato", "ram": 4.0, "tags": ["chat"]},
    "command-r:35b": {"cat": "chat", "desc": "Command R (Cohere)", "use": "RAG, tool use", "ram": 20.0, "tags": ["chat", "rag", "tools", "heavy"]},
    "command-r-plus:104b": {"cat": "chat", "desc": "Command R Plus", "use": "produzione, RAG", "ram": 60.0, "tags": ["chat", "rag", "heavy"]},
    "yi:6b": {"cat": "chat", "desc": "Yi 6B", "use": "chat + coding", "ram": 3.5, "tags": ["chat", "code"]},
    "yi:9b": {"cat": "chat", "desc": "Yi 9B", "use": "chat avanzato", "ram": 5.0, "tags": ["chat"]},
    "yi:34b": {"cat": "chat", "desc": "Yi 34B", "use": "produzione", "ram": 20.0, "tags": ["chat", "heavy"]},
    "solar:10.7b": {"cat": "chat", "desc": "Solar (Upstage)", "use": "chat + reasoning", "ram": 6.0, "tags": ["chat", "reasoning"]},
    "nous-hermes2:7b": {"cat": "chat", "desc": "Nous Hermes 2", "use": "chat allineato", "ram": 4.0, "tags": ["chat"]},
    "nous-hermes2:34b": {"cat": "chat", "desc": "Nous Hermes 2 34B", "use": "produzione", "ram": 20.0, "tags": ["chat", "heavy"]},
    "dolphin-mixtral:8x7b": {"cat": "chat", "desc": "Dolphin Mixtral (uncensored)", "use": "chat senza filtri", "ram": 26.0, "tags": ["chat", "uncensored", "heavy"]},
    "dolphin-llama3:8b": {"cat": "chat", "desc": "Dolphin Llama3 (uncensored)", "use": "chat senza filtri", "ram": 4.7, "tags": ["chat", "uncensored"]},
    "llama2:7b": {"cat": "chat", "desc": "Llama 2 (legacy)", "use": "chat base", "ram": 4.0, "tags": ["chat", "legacy"]},
    "llama2:13b": {"cat": "chat", "desc": "Llama 2 13B", "use": "chat avanzato", "ram": 7.5, "tags": ["chat", "legacy"]},
    "llama2:70b": {"cat": "chat", "desc": "Llama 2 70B", "use": "produzione", "ram": 40.0, "tags": ["chat", "legacy", "heavy"]},
    # === VISION ===
    "llava:7b": {"cat": "vision", "desc": "LLaVA (visione + chat)", "use": "analisi immagini, OCR", "ram": 4.5, "tags": ["vision", "multimodal"]},
    "llava:13b": {"cat": "vision", "desc": "LLaVA 13B", "use": "analisi immagini avanzata", "ram": 7.5, "tags": ["vision", "multimodal"]},
    "llava:34b": {"cat": "vision", "desc": "LLaVA 34B", "use": "produzione vision", "ram": 20.0, "tags": ["vision", "heavy"]},
    "llava-llama3:8b": {"cat": "vision", "desc": "LLaVA su Llama3", "use": "vision + chat", "ram": 4.7, "tags": ["vision", "multimodal"]},
    "bakllava:7b": {"cat": "vision", "desc": "BakLLaVA", "use": "analisi immagini", "ram": 4.0, "tags": ["vision", "multimodal"]},
    "moondream:latest": {"cat": "vision", "desc": "Moondream (ultra-leggero)", "use": "edge vision, captioning", "ram": 1.7, "tags": ["vision", "light", "fast"]},
    "moondream2": {"cat": "vision", "desc": "Moondream 2", "use": "edge vision", "ram": 1.7, "tags": ["vision", "light"]},
    "minicpm-v:8b": {"cat": "vision", "desc": "MiniCPM-V", "use": "vision + OCR", "ram": 5.0, "tags": ["vision", "multimodal"]},
    "qwen2.5-vl:3b": {"cat": "vision", "desc": "Qwen 2.5 VL piccolo", "use": "vision leggera", "ram": 2.0, "tags": ["vision", "multimodal", "light"]},
    "qwen2.5-vl:7b": {"cat": "vision", "desc": "Qwen 2.5 VL medio", "use": "vision + chat", "ram": 4.5, "tags": ["vision", "multimodal"]},
    "qwen2.5-vl:32b": {"cat": "vision", "desc": "Qwen 2.5 VL grande", "use": "produzione vision", "ram": 20.0, "tags": ["vision", "heavy"]},
    "llama3.2-vision:11b": {"cat": "vision", "desc": "Llama 3.2 Vision", "use": "vision + chat", "ram": 6.5, "tags": ["vision", "multimodal"]},
    "granite3.2-vision:2b": {"cat": "vision", "desc": "Granite Vision piccolo", "use": "edge vision", "ram": 1.5, "tags": ["vision", "light", "enterprise"]},
    # === EMBEDDING ===
    "nomic-embed-text:latest": {"cat": "embedding", "desc": "Nomic Embed (consigliato)", "use": "RAG, ricerca semantica", "ram": 0.3, "tags": ["embedding", "rag", "recommended"]},
    "nomic-embed-text:v1.5": {"cat": "embedding", "desc": "Nomic Embed v1.5", "use": "RAG", "ram": 0.3, "tags": ["embedding", "rag"]},
    "mxbai-embed-large:latest": {"cat": "embedding", "desc": "MixedBread Embed Large", "use": "RAG alta qualità", "ram": 0.7, "tags": ["embedding", "rag", "quality"]},
    "all-minilm:latest": {"cat": "embedding", "desc": "All-MiniLM (leggero)", "use": "RAG leggero", "ram": 0.1, "tags": ["embedding", "light", "fast"]},
    "snowflake-arctic-embed:latest": {"cat": "embedding", "desc": "Snowflake Arctic Embed", "use": "RAG", "ram": 0.7, "tags": ["embedding", "rag"]},
    "bge-m3:latest": {"cat": "embedding", "desc": "BGE-M3 (multilingue)", "use": "RAG multilingue", "ram": 1.2, "tags": ["embedding", "rag", "multilingual"]},
    "bge-large:latest": {"cat": "embedding", "desc": "BGE Large", "use": "RAG alta qualità", "ram": 1.3, "tags": ["embedding", "rag"]},
    # === REASONING ===
    "deepseek-r1:1.5b": {"cat": "reasoning", "desc": "DeepSeek R1 piccolo (chain-of-thought)", "use": "reasoning leggero", "ram": 1.2, "tags": ["reasoning", "cot"]},
    "deepseek-r1:7b": {"cat": "reasoning", "desc": "DeepSeek R1 medio", "use": "reasoning + math", "ram": 4.5, "tags": ["reasoning", "cot", "math"]},
    "deepseek-r1:8b": {"cat": "reasoning", "desc": "DeepSeek R1 8B", "use": "reasoning avanzato", "ram": 4.7, "tags": ["reasoning", "cot"]},
    "deepseek-r1:14b": {"cat": "reasoning", "desc": "DeepSeek R1 14B", "use": "reasoning complesso", "ram": 9.0, "tags": ["reasoning", "cot", "heavy"]},
    "deepseek-r1:32b": {"cat": "reasoning", "desc": "DeepSeek R1 32B", "use": "produzione reasoning", "ram": 20.0, "tags": ["reasoning", "cot", "heavy"]},
    "deepseek-r1:70b": {"cat": "reasoning", "desc": "DeepSeek R1 70B", "use": "massima qualità reasoning", "ram": 40.0, "tags": ["reasoning", "cot", "heavy"]},
    "qwq:32b": {"cat": "reasoning", "desc": "QwQ (Qwen reasoning)", "use": "reasoning avanzato", "ram": 20.0, "tags": ["reasoning", "cot", "heavy"]},
    "marco-o1:7b": {"cat": "reasoning", "desc": "Marco-O1 (OpenReasoning)", "use": "reasoning", "ram": 4.0, "tags": ["reasoning", "cot"]},
    # === MATH ===
    "mathstral:7b": {"cat": "math", "desc": "Mathstral (Mistral math)", "use": "matematica, calcolo", "ram": 4.0, "tags": ["math"]},
    "wizard-math:7b": {"cat": "math", "desc": "WizardMath 7B", "use": "matematica", "ram": 4.0, "tags": ["math"]},
    "wizard-math:13b": {"cat": "math", "desc": "WizardMath 13B", "use": "matematica avanzata", "ram": 7.5, "tags": ["math"]},
    # === TRANSLATION ===
    "translategemma:4b": {"cat": "translation", "desc": "TranslateGemma 4B", "use": "traduzione multilingue", "ram": 3.3, "tags": ["translation", "multilingual"]},
    "translategemma:12b": {"cat": "translation", "desc": "TranslateGemma 12B", "use": "traduzione alta qualità", "ram": 7.0, "tags": ["translation", "multilingual"]},
    # === TOOLS / FUNCTION CALLING ===
    "firefunction-v2:70b": {"cat": "tools", "desc": "FireFunction V2 (function calling)", "use": "tool use, agenti", "ram": 40.0, "tags": ["tools", "function-calling", "heavy"]},
    "xlam:7b": {"cat": "tools", "desc": "xLAM (Salesforce) function calling", "use": "tool use", "ram": 4.0, "tags": ["tools", "function-calling"]},
    "xlam:8x7b": {"cat": "tools", "desc": "xLAM MoE", "use": "tool use avanzato", "ram": 26.0, "tags": ["tools", "function-calling", "moe", "heavy"]},
    "granite3.1-dense:8b": {"cat": "tools", "desc": "Granite 3.1 (IBM, tool use)", "use": "enterprise + tool use", "ram": 4.5, "tags": ["tools", "enterprise"]},
    # === LIGHTWEIGHT / EDGE ===
    "smollm:135m": {"cat": "light", "desc": "SmolLM 135M (ultra-edge)", "use": "edge, mobile", "ram": 0.1, "tags": ["light", "fast", "edge"]},
    "smollm:360m": {"cat": "light", "desc": "SmolLM 360M", "use": "edge", "ram": 0.3, "tags": ["light", "fast"]},
    "smollm:1.7b": {"cat": "light", "desc": "SmolLM 1.7B", "use": "edge, mobile", "ram": 1.2, "tags": ["light", "fast"]},
    "smollm2:135m": {"cat": "light", "desc": "SmolLM2 135M", "use": "edge", "ram": 0.1, "tags": ["light", "fast", "edge"]},
    "smollm2:360m": {"cat": "light", "desc": "SmolLM2 360M", "use": "edge", "ram": 0.3, "tags": ["light", "fast"]},
    "smollm2:1.7b": {"cat": "light", "desc": "SmolLM2 1.7B", "use": "edge, mobile", "ram": 1.2, "tags": ["light", "fast"]},
    "gemma:2b": {"cat": "light", "desc": "Gemma 2B (Google)", "use": "edge, mobile", "ram": 1.5, "tags": ["light", "fast"]},
    "phi3:mini": {"cat": "light", "desc": "Phi-3 Mini (già in coding)", "use": "edge + coding", "ram": 2.0, "tags": ["light", "code"]},
    "stablelm2:1.6b": {"cat": "light", "desc": "StableLM 2 1.6B", "use": "edge", "ram": 1.2, "tags": ["light", "fast"]},
    "olmo:1b": {"cat": "light", "desc": "OLMo 1B (Allen AI)", "use": "research, edge", "ram": 0.8, "tags": ["light", "research"]},
    "olmo:7b": {"cat": "light", "desc": "OLMo 7B", "use": "research", "ram": 4.0, "tags": ["light", "research"]},
}



# Licenze: famiglie con termini commerciali/restrittivi.
# Default: "open" (Apache/MIT/BSD-like). Override per famiglie note.
_LICENSE_OVERRIDES = {
    "llama": "restricted",      # Meta Llama Community License
    "gemma": "restricted",      # Google Gemma Terms of Use
    "phi": "restricted",        # Microsoft (research/commercial terms)
    "yi": "restricted",         # 01.AI (commerciale con limiti)
    "command-r": "restricted",  # Cohere (commerciale)
    "dolphin": "restricted",    # basato su Llama
    "vicuna": "restricted",     # basato su Llama
    "wizard": "restricted",     # basato su Llama/CodeLlama
    "orca": "restricted",       # basato su Llama
    "bakllava": "restricted",   # basato su Llama
    "llava": "restricted",      # basato su Llama/Vicuna
}


def _license_of(name: str) -> str:
    n = (name or "").lower()
    for fam, lic in _LICENSE_OVERRIDES.items():
        if fam in n:
            return lic
    return "open"


def is_open_weight(name: str) -> bool:
    """True se il modello è open-weight con licenza permissiva (open)."""
    return _license_of(name) == "open"


def open_weight_only() -> list[dict]:
    """Lista solo i modelli open-weight (licenza open)."""
    out = []
    for name, info in CATALOG.items():
        if is_open_weight(name):
            out.append({"name": name, "license": "open", **info})
    out.sort(key=lambda x: x["ram"])
    return out



def _normalize(name: str) -> str:
    return (name or "").strip().lower()


def lookup(name: str) -> Optional[dict]:
    """Cerca un modello nel catalogo (match esatto o prefisso)."""
    n = _normalize(name)
    if n in CATALOG:
        return {"name": n, "license": _license_of(n), **CATALOG[n]}
    # Match per prefisso (es. "qwen2.5-coder" → primo disponibile)
    for key, info in CATALOG.items():
        if key.startswith(n) or n.startswith(key.split(":")[0]):
            return {"name": key, **info}
    return None


def by_category(cat: str) -> list[dict]:
    """Lista i modelli di una categoria."""
    out = []
    for name, info in CATALOG.items():
        if info["cat"] == cat:
            out.append({"name": name, "license": _license_of(name), **info})
    out.sort(key=lambda x: x["ram"])
    return out


def categories() -> list[str]:
    return sorted(set(v["cat"] for v in CATALOG.values()))


def search(query: str) -> list[dict]:
    """Cerca modelli per keyword in nome/descrizione/tags."""
    q = (query or "").lower()
    out = []
    for name, info in CATALOG.items():
        haystack = (name + " " + info["desc"] + " " + info["use"] + " " +
                    " ".join(info.get("tags", []))).lower()
        if q in haystack:
            out.append({"name": name, **info})
    out.sort(key=lambda x: x["ram"])
    return out


def recommend(ram_gb: float, task: str = "chat") -> list[dict]:
    """Raccomanda modelli che entrano in `ram_gb` GB, filtrati per task."""
    task_map = {
        "chat": ["chat", "general"],
        "coding": ["coding", "code"],
        "vision": ["vision"],
        "reasoning": ["reasoning", "math"],
        "embedding": ["embedding"],
        "light": ["light", "fast"],
    }
    wanted = set(task_map.get(task, [task]))
    out = []
    for name, info in CATALOG.items():
        if info["ram"] <= ram_gb and (wanted & set(info.get("tags", [])) or info["cat"] in wanted):
            out.append({"name": name, "license": _license_of(name), **info})
    out.sort(key=lambda x: (-x["ram"], x["name"]))
    return out[:10]


def _cli() -> int:
    p = argparse.ArgumentParser(prog="python -m CORE.model_catalog")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_lookup = sub.add_parser("lookup", help="Info su un modello.")
    p_lookup.add_argument("name")
    p_lookup.set_defaults(func=lambda a: _cmd_lookup(a.name))

    p_list = sub.add_parser("list", help="Lista per categoria.")
    p_list.add_argument("--category", "-c", default=None)
    p_list.set_defaults(func=lambda a: _cmd_list(a.category))

    p_search = sub.add_parser("search", help="Cerca modelli.")
    p_search.add_argument("query")
    p_search.set_defaults(func=lambda a: _cmd_search(a.query))

    p_rec = sub.add_parser("recommend", help="Raccomanda per RAM e task.")
    p_rec.add_argument("--ram", type=float, required=True)
    p_rec.add_argument("--task", default="chat")
    p_rec.set_defaults(func=lambda a: _cmd_recommend(a.ram, a.task))

    p_cats = sub.add_parser("categories", help="Lista categorie.")
    p_cats.set_defaults(func=lambda a: _cmd_categories())
    p_ow = sub.add_parser("open-weight", help="Solo modelli open-weight (licenza permissiva).")
    p_ow.set_defaults(func=lambda a: _cmd_open_weight())

    args = p.parse_args()
    args.func(args)
    return 0


def _cmd_lookup(name: str) -> None:
    info = lookup(name)
    if not info:
        print(f"Modello '{name}' non nel catalogo.")
        return
    print(json.dumps(info, indent=2, ensure_ascii=False))


def _cmd_list(cat: Optional[str]) -> None:
    if cat:
        items = by_category(cat)
    else:
        items = [{"name": n, **v} for n, v in CATALOG.items()]
    for it in items:
        print(f"{it['name']:32s} {it['cat']:12s} {it['ram']:6.1f}GB  {it['desc']}")


def _cmd_search(q: str) -> None:
    for it in search(q):
        print(f"{it['name']:32s} {it['cat']:12s} {it['ram']:6.1f}GB  {it['desc']}")


def _cmd_recommend(ram: float, task: str) -> None:
    for it in recommend(ram, task):
        print(f"{it['name']:32s} {it['cat']:12s} {it['ram']:6.1f}GB  {it['desc']}")


def _cmd_categories() -> None:
    for c in categories():
        print(c)


def _cmd_open_weight() -> None:
    for it in open_weight_only():
        print(f"{it['name']:32s} {it['cat']:12s} {it['ram']:6.1f}GB  {it['license']:10s}  {it['desc']}")


if __name__ == "__main__":
    raise SystemExit(_cli())
