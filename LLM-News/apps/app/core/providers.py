"""AI providers, in one table shared by the backend and the news pipeline (llm_client.py).

Every provider speaks the OpenAI chat-completions API. Put its key in .env; override its model
with <ID>_MODEL (e.g. GEMINI_MODEL=gemini-3-flash-preview); prefer one with LLM_PUBLISHER=<ID>.
Keep this module free of app imports so the pipeline can load it on its own.
"""
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Provider:
    name: str      # display name
    key_env: str   # .env variable holding the API key
    base_url: str  # OpenAI-compatible endpoint
    model: str     # default model


# Order = preference when LLM_PUBLISHER isn't set
PROVIDERS = {
    "OPENROUTER": Provider("OpenRouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "qwen/qwen-plus"),
    "OPENAI": Provider("OpenAI", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
    "ALIBABA": Provider("Alibaba", "ALIBABA_LLM_KEY", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    "GEMINI": Provider("Gemini", "GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "PERPLEXITY": Provider("Perplexity", "PERPLEXITY_API_KEY", "https://api.perplexity.ai", "sonar"),
    # Free key at build.nvidia.com, for development and testing only (production needs NVIDIA AI Enterprise).
    # Free queues vary a lot: on 2026-10-03 DeepSeek, GLM, Kimi and Gemma timed out; Nemotron 3 Ultra was fast.
    "NVIDIA": Provider("NVIDIA", "NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3-ultra-550b-a55b"),
}


def model_for(provider_id: str) -> str:
    return os.getenv(f"{provider_id}_MODEL") or PROVIDERS[provider_id].model


def api_key_for(provider_id: str) -> str:
    return os.getenv(PROVIDERS[provider_id].key_env, "")


def configured() -> List[Tuple[str, Provider, str, str]]:
    """(id, provider, api_key, model) for each provider with a key; LLM_PUBLISHER's comes first."""
    preferred = (os.getenv("LLM_PUBLISHER") or "").upper()
    ids = sorted(PROVIDERS, key=lambda pid: pid != preferred)
    return [(pid, PROVIDERS[pid], api_key_for(pid), model_for(pid)) for pid in ids if api_key_for(pid)]


def first_configured() -> Optional[Tuple[str, Provider, str, str]]:
    found = configured()
    return found[0] if found else None
