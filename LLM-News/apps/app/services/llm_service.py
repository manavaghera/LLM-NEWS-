import asyncio
import json
import logging
import os
from typing import AsyncIterator, Dict, List, Optional, Tuple

import aiohttp

from ..core import providers
from ..core.config import settings
from ..core.limits import ai_budget

# Add dashscope import with error handling
try:
    import dashscope
    from dashscope import Application
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    logging.warning("dashscope library not available. Knowledge Graph features will be disabled.")

logger = logging.getLogger(__name__)

KNOWLEDGE_GRAPH = "knowledge-graph"


class AIServiceSlow(RuntimeError):
    """The provider stopped sending (busy free tiers can leave a request hanging)."""


class HTTPLLMClient:
    """Async client for one OpenAI-compatible provider."""

    # Give up after 60s without any data (thinking models send progress chunks while they think,
    # so only a stalled request trips it) or 3 minutes in all
    timeout = aiohttp.ClientTimeout(total=180, sock_connect=15, sock_read=60)

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def stream(self, messages: List[Dict], model: str, temperature: float = 0.7) -> AsyncIterator[str]:
        """Yield text chunks from an OpenAI-compatible streaming chat completion (server-sent events)."""
        ai_budget.consume()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1000,
            "stream": True
        }
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"API error {response.status}: {error_text}")
                    async for raw_line in response.content:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line.startswith("data:"):
                            continue  # blank lines and keep-alive comments
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            choices = json.loads(data).get("choices") or []
                        except ValueError:
                            continue
                        # Thinking models send reasoning_content first; only the answer is shown
                        text = choices[0].get("delta", {}).get("content") if choices else None
                        if text:
                            yield text
        except asyncio.TimeoutError:
            raise AIServiceSlow("The AI service is taking too long to answer (it may be busy). Please try again.")


class LLMService:
    """The chat assistant's models: one per provider with a key in .env (see core/providers.py)."""

    def __init__(self):
        # (provider name, client, model), preferred provider first
        self.clients: List[Tuple[str, HTTPLLMClient, str]] = [
            (provider.name, HTTPLLMClient(provider.base_url, api_key), model)
            for _, provider, api_key, model in providers.configured()
        ]
        for name, _, model in self.clients:
            logger.info(f"Chat provider ready: {name} ({model})")
        self.knowledge_graph_available = bool(
            DASHSCOPE_AVAILABLE and settings.ALIBABA_LLM_KEY_KG and os.getenv("ALIBABA_KG_APP_ID")
        )

    def get_available_models(self) -> List[Dict]:
        """Only models that can actually answer: configured providers, plus the Knowledge Graph if set up"""
        models = [{"name": f"{model} ({name})", "value": model, "provider": name} for name, _, model in self.clients]
        if self.knowledge_graph_available:
            models.append({"name": "Knowledge Graph", "value": KNOWLEDGE_GRAPH, "provider": "Knowledge"})
        return models

    def get_default_model(self) -> Optional[Dict]:
        models = self.get_available_models()
        return models[0] if models else None

    def pick_client(self, preferred_model: Optional[str] = None) -> Optional[Tuple[str, HTTPLLMClient, str]]:
        """(provider, client, model) for the preferred model, else the first configured provider"""
        for entry in self.clients:
            if entry[2] == preferred_model:
                return entry
        return self.clients[0] if self.clients else None

    async def ask_knowledge_graph(self, query: str) -> str:
        """Answer from the Alibaba Cloud Knowledge Graph application (DashScope)."""
        ai_budget.consume()
        dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
        response = await asyncio.to_thread(
            Application.call,
            api_key=settings.ALIBABA_LLM_KEY_KG,
            app_id=os.getenv('ALIBABA_KG_APP_ID', ''),
            prompt=query,
            parameters={"temperature": 0.8, "max_tokens": 1024},
        )
        text = response.get("output", {}).get("text") if isinstance(response, dict) else None
        if not text:
            logger.error(f"Unexpected Knowledge Graph response: {response}")
            raise RuntimeError("The Knowledge Graph returned an unexpected response.")
        return text

    def get_health_status(self) -> Dict[str, bool]:
        """Which providers have a key configured"""
        configured = {pid for pid, *_ in providers.configured()}
        status = {pid.lower(): pid in configured for pid in providers.PROVIDERS}
        status["knowledge_graph"] = self.knowledge_graph_available
        return status
