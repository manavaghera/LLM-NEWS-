"""Synchronous OpenAI-compatible client for the digest, translation and audio features."""
import logging

from openai import OpenAI

from ..core import generation, providers
from ..core.limits import ai_budget


logger = logging.getLogger(__name__)


def record_call_finish(call_id, response=None, failed=False):
    """Usage-recording failures must not replace a provider result or its original exception."""
    try:
        generation.finish_call(call_id, response=response, failed=failed)
    except Exception:
        logger.warning("Could not finish recording AI usage", exc_info=True)


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
        call_id = generation.start_call(self.provider, self.model, scope="website")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt_content},
                ],
                temperature=temperature,
                **kwargs,
            )
        except BaseException:
            record_call_finish(call_id, failed=True)
            raise
        record_call_finish(call_id, response=response)
        return response
