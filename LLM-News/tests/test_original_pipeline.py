"""Original pipeline regressions, using fake clients and data instead of ML dependencies."""
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self, content="A checked news summary.", error=None):
        self.content, self.error, self.calls = content, error, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def load_script(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_llm(monkeypatch):
    client = FakeClient()
    created = []

    def make_client(publisher):
        other = FakeClient()
        created.append((publisher, other))
        return other

    llm = ModuleType("llm_client")
    llm.LLMClient = make_client
    llm.LLM_PUBLISHER, llm.LLM_MODEL = "OPENROUTER", "configured-writer-model"
    llm.default_client = client
    llm.providers = SimpleNamespace(
        PROVIDERS=dict.fromkeys(["OPENAI", "PERPLEXITY", "ALIBABA", "GEMINI", "OPENROUTER", "NVIDIA"]),
        model_for=lambda provider: f"configured-{provider.lower()}-model",
    )
    monkeypatch.setitem(sys.modules, "llm_client", llm)
    return llm, created


@pytest.fixture
def summary(fake_llm):
    return load_script("deployment/summary/generate_summary.py", "summary_under_test")


def test_summary_uses_configured_default_provider_and_model(summary, fake_llm):
    llm, created = fake_llm
    assert summary.generate_llm_summary("Today's news") == "A checked news summary."
    assert llm.default_client.calls[0]["model"] == "configured-writer-model"
    assert not created


@pytest.mark.parametrize("provider", ["GEMINI", "OPENAI", "PERPLEXITY", "NVIDIA"])
def test_summary_override_routes_to_requested_provider(summary, fake_llm, provider):
    llm, created = fake_llm
    summary.generate_llm_summary("Today's news", provider.lower())
    assert created[0][0] == provider
    assert created[0][1].calls[0]["model"] == f"configured-{provider.lower()}-model"
    assert not llm.default_client.calls


@pytest.mark.parametrize("content", [None, "", "   ", {"invalid": "text"}])
def test_summary_rejects_empty_or_invalid_model_content(summary, fake_llm, content):
    fake_llm[0].default_client.content = content
    with pytest.raises(ValueError, match="no summary text"):
        summary.generate_llm_summary("Today's news")


def test_failed_summary_does_not_replace_published_speech(summary, fake_llm, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    articles = tmp_path / "data/output/article/2026-10-09"
    articles.mkdir(parents=True)
    (articles / "group_1.json").write_text(json.dumps({"headline": "A real story"}), encoding="utf-8")
    speech = tmp_path / "deployment/summary/resource/summary.txt"
    speech.parent.mkdir(parents=True)
    speech.write_text("Existing summary", encoding="utf-8")
    fake_llm[0].default_client.error = RuntimeError("Provider unavailable")
    monkeypatch.setattr(sys, "argv", ["generate_summary.py", "--date", "2026-10-09"])

    with pytest.raises(RuntimeError, match="Provider unavailable"):
        summary.main()
    assert speech.read_text(encoding="utf-8") == "Existing summary"


def test_summary_cli_accepts_shared_provider_and_model_override(summary, fake_llm, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    articles = tmp_path / "data/output/article/2026-10-09"
    articles.mkdir(parents=True)
    (articles / "group_1.json").write_text(json.dumps({"headline": "A real story"}), encoding="utf-8")
    (articles / "group_categories.json").write_text('{"group_1":"tech"}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["generate_summary.py", "--date", "2026-10-09",
                                      "--llm-provider", "gemini", "--model", "chosen-model"])
    assert len(summary.read_articles_from_directory("2026-10-09")) == 1
    summary.main()
    publisher, client = fake_llm[1][0]
    assert publisher == "GEMINI" and client.calls[0]["model"] == "chosen-model"
    assert (tmp_path / "deployment/summary/resource/summary.txt").read_text() == "A checked news summary."


def test_article_resume_preserves_dated_output_without_reading_sources(fake_llm, monkeypatch, tmp_path):
    class GroupIds(list):
        def __eq__(self, other):
            return True

    class Groups:
        iloc = [{"size": 1}]

        def __getitem__(self, key):
            return GroupIds([1]) if key == "group_id" else self

    reads = []

    def read_csv(path):
        reads.append(path)
        if path == "data/group/2026-10-09/group_result.csv":
            return Groups()
        raise AssertionError("A completed article must not read sources or call the model")

    pandas = ModuleType("pandas")
    pandas.read_csv = read_csv
    monkeypatch.setitem(sys.modules, "pandas", pandas)
    monkeypatch.syspath_prepend(str(ROOT / "generate_article"))
    monkeypatch.syspath_prepend(str(ROOT))
    article = load_script("generate_article/generate_article.py", "article_under_test")
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "data/output/article/2026-10-09/group_1.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"headline":"Already published"}', encoding="utf-8")

    article.generate_article("2026-10-09", "configured-writer-model")

    assert output.read_text(encoding="utf-8") == '{"headline":"Already published"}'
    assert reads == ["data/group/2026-10-09/group_result.csv"]
    assert not fake_llm[0].default_client.calls
