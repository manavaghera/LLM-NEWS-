"""Website AI accounting with fake providers; no model or external HTTP calls."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from app.core import generation
from app.services import completion_client, llm_service


def completion(create):
    client = completion_client.CompletionClient.__new__(completion_client.CompletionClient)
    client.provider, client.model = "Fake provider", "fake-model"
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client


def test_completion_records_website_tokens_without_using_pipeline_allowance():
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=31, completion_tokens=13))
    result = completion(lambda **kwargs: response).generate("private prompt", "private instructions")
    assert result is response
    summary = generation.usage_summary()
    assert summary["pipeline_calls"] == 0
    assert summary["models"] == [{"provider": "Fake provider", "model": "fake-model", "calls": 1,
                                  "failed": 0, "prompt_tokens": 31, "completion_tokens": 13,
                                  "unpriced_calls": 1, "spent_usd": 0.0}]


def test_provider_error_is_recorded_and_preserved():
    def fail(**kwargs):
        raise RuntimeError("original provider error")

    with pytest.raises(RuntimeError, match="original provider error"):
        completion(fail).generate("private prompt", "private instructions")
    assert generation.usage_summary()["models"][0]["failed"] == 1


def test_usage_recording_error_does_not_mask_provider_error(monkeypatch):
    def provider_error(**kwargs):
        raise RuntimeError("original provider error")

    def storage_error(*args, **kwargs):
        raise OSError("fake recording failure")

    monkeypatch.setattr(generation, "finish_call", storage_error)
    with pytest.raises(RuntimeError, match="original provider error"):
        completion(provider_error).generate("private prompt", "private instructions")


def test_reservation_failure_prevents_provider_call(monkeypatch):
    called = []

    def storage_error(*args, **kwargs):
        raise OSError("fake reservation failure")

    monkeypatch.setattr(generation, "start_call", storage_error)
    with pytest.raises(OSError, match="fake reservation failure"):
        completion(lambda **kwargs: called.append(kwargs)).generate("private prompt", "private instructions")
    assert called == []


class FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def content(self):
        async def lines():
            for chunk in ({"choices": [{"delta": {"content": "Hello"}}]},
                          {"choices": [], "usage": {"prompt_tokens": 8, "completion_tokens": 2}}):
                yield f"data: {json.dumps(chunk)}\n".encode()
            yield b"data: [DONE]\n"
        return lines()

    async def text(self):
        return "fake provider unavailable"


class FakeSession(FakeResponse):
    def __init__(self, response):
        self.response = response

    def post(self, *args, **kwargs):
        return self.response


def collect_stream(client):
    async def collect():
        return [part async for part in client.stream([{"role": "user", "content": "private prompt"}], "fake-model")]
    return asyncio.run(collect())


def test_stream_records_optional_usage_and_real_provider_name(monkeypatch):
    monkeypatch.setattr(llm_service.aiohttp, "ClientSession", lambda **kwargs: FakeSession(FakeResponse()))
    client = llm_service.HTTPLLMClient("https://unused.invalid", "fake-secret", "Fake provider")
    assert collect_stream(client) == ["Hello"]
    model = generation.usage_summary()["models"][0]
    assert (model["provider"], model["failed"], model["prompt_tokens"], model["completion_tokens"]) == (
        "Fake provider", 0, 8, 2)


def test_stream_records_failed_provider_response(monkeypatch):
    response = FakeResponse()
    response.status = 503
    monkeypatch.setattr(llm_service.aiohttp, "ClientSession", lambda **kwargs: FakeSession(response))
    with pytest.raises(RuntimeError, match="API error 503"):
        collect_stream(llm_service.HTTPLLMClient("https://unused.invalid", "fake-secret", "Fake provider"))
    assert generation.usage_summary()["models"][0]["failed"] == 1


def test_knowledge_graph_records_website_usage(monkeypatch):
    monkeypatch.setattr(llm_service, "dashscope", SimpleNamespace(), raising=False)
    monkeypatch.setattr(llm_service, "Application", SimpleNamespace(call=lambda **kwargs: {
        "output": {"text": "A fake answer"}, "usage": {"prompt_tokens": 5, "completion_tokens": 2}
    }), raising=False)
    service = llm_service.LLMService.__new__(llm_service.LLMService)
    assert asyncio.run(service.ask_knowledge_graph("private query")) == "A fake answer"
    summary = generation.usage_summary()
    assert summary["pipeline_calls"] == 0
    assert summary["models"][0]["provider"] == "Alibaba Knowledge Graph"
