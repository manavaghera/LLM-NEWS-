"""Synchronous OpenAI-compatible client for the digest, translation and audio features."""
from openai import OpenAI

from ..core import providers
from ..core.limits import ai_budget


class CompletionClient:
    """Uses the preferred configured provider (core/providers.py); generate() mirrors llm_client.LLMClient."""

    def __init__(self):
        found = providers.first_configured()
        if not found:
            raise RuntimeError(
                "No LLM API key configured. Set OPENROUTER_API_KEY, OPENAI_API_KEY or another provider key in .env"
            )
        _, provider, api_key, model = found
        self.provider = provider.name
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=provider.base_url, timeout=120)

    def generate(self, prompt_content: str, system_content: str, temperature: float = 0.3, **kwargs):
        ai_budget.consume()
        return self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt_content},
            ],
            temperature=temperature,
            **kwargs,
        )
