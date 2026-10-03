import importlib.util
import os
from pathlib import Path
from openai import OpenAI
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# One provider table (keys, URLs, models) shared with the backend: apps/app/core/providers.py
_spec = importlib.util.spec_from_file_location(
    "newssense_providers", Path(__file__).resolve().parent / "apps" / "app" / "core" / "providers.py"
)
providers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(providers)

class LLMClient:
    def __init__(self, publisher: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.publisher = publisher.upper()
        provider = providers.PROVIDERS.get(self.publisher)
        if not provider:
            raise ValueError(f"Unsupported publisher: {self.publisher}")
        self.api_key = api_key or os.getenv(provider.key_env)
        if not self.api_key:
            raise ValueError(f"API key not found. Please set {provider.key_env} environment variable or pass it directly.")
        self.base_url = base_url or provider.base_url

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=300  # Default 3 minutes timeout for all requests
        )

    def generate(
        self,
        prompt_content: str,
        system_content: str = 'You are a helpful assistant.',
        temperature: float = 0, # next need to be 0
        top_p: float = 0.5, # 
        model: str = 'gpt-4o-mini',  
        **kwargs
    ) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': system_content},
                    {'role': 'user', 'content': prompt_content}
                ],
                temperature=temperature,
                top_p=top_p,
                **kwargs
            )
            return completion
        except Exception as e:
            raise RuntimeError(f"Error generating response from {self.publisher}: {str(e)}")

class _LazyClient:
    """Builds the LLMClient on first use, so a missing key only fails the step that needs it."""
    def __init__(self, publisher: str):
        self._publisher = publisher
        self._client = None

    def __getattr__(self, name):
        if self._client is None:
            self._client = LLMClient(publisher=self._publisher)
        return getattr(self._client, name)

# Provider/model for the article and event-card steps; override with LLM_PUBLISHER / LLM_MODEL in .env
LLM_PUBLISHER = (os.getenv('LLM_PUBLISHER') or 'ALIBABA').upper()
LLM_MODEL = os.getenv('LLM_MODEL') or (providers.model_for(LLM_PUBLISHER) if LLM_PUBLISHER in providers.PROVIDERS else '')
# Model for the fact-check and coverage comparison (same provider). A different model from the writer
# catches more of the writer's mistakes; defaults to LLM_MODEL.
CHECK_MODEL = os.getenv('CHECK_MODEL') or LLM_MODEL

openai_client = _LazyClient('OPENAI')
perplexity_client = _LazyClient('PERPLEXITY')
alibaba_client = _LazyClient('ALIBABA')
gemini_client = _LazyClient('GEMINI')
openrouter_client = _LazyClient('OPENROUTER')
default_client = _LazyClient(LLM_PUBLISHER)