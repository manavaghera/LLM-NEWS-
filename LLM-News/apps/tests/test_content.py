"""Translation, saved digests and audio, with a fake LLM and fake voice. Run from LLM-News/apps: python -m pytest tests"""
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import audio_service, translation_service
from app.services.digest_service import DigestService
from conftest import write_article

client = TestClient(app)
DATE = "2026-01-01"


class FakeLLM:
    """Records prompts and answers with a fixed reply"""
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def generate(self, prompt_content, system_content, **kwargs):
        self.prompts.append(prompt_content)
        content = self.reply(prompt_content) if callable(self.reply) else self.reply
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def cited_article(root):
    path = write_article(root, DATE, "group_1", "UN vote")
    article = json.loads(path.read_text(encoding="utf-8"))
    article["body"] = [
        {"section": "Vote", "content": "The UN voted.<a href='https://a.example/1'>[1]</a> More.<a href='https://b.example/2'>[2]</a>",
         "sources": ["https://a.example/1", "https://b.example/2"]},
    ]
    article["summary_speech"] = "The UN voted."
    path.write_text(json.dumps(article), encoding="utf-8")
    return path


def spanish(prompt):
    data = json.loads(prompt)
    content = data["sections"][0]["content"]
    assert "⟦1⟧" in content and "<a" not in content  # links are hidden from the model
    return json.dumps({"headline": "Votación de la ONU", "lead": "Plomo",
                       "sections": [{"section": "Votación", "content": "La ONU votó.⟦1⟧ Más."}],  # ⟦2⟧ dropped
                       "summary_speech": "La ONU votó."})


def test_article_translation_is_one_call_keeps_citations_and_is_saved(static_root, monkeypatch):
    from app.api.endpoints import translate
    path = cited_article(static_root)
    fake = FakeLLM(spanish)
    monkeypatch.setattr(translate.translation_service, "_client", fake)

    body = {"date": DATE, "group_id": "group_1", "target_languages": ["es"]}
    result = client.post("/api/translate/article", json=body).json()["translation"]
    assert len(fake.prompts) == 1
    assert result["headline"] == "Votación de la ONU"
    content = result["body"][0]["content"]
    assert "La ONU votó.<a href='https://a.example/1'>[1]</a> Más." in content
    assert content.endswith("<a href='https://b.example/2'>[2]</a>")  # dropped marker re-attached
    assert result["_translation"]["target_lang"] == "es"

    client.post("/api/translate/article", json=body)
    assert len(fake.prompts) == 1  # served from the saved translation

    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))  # article changed
    client.post("/api/translate/article", json=body)
    assert len(fake.prompts) == 2


def test_translation_errors_are_reported_not_hidden(static_root, monkeypatch):
    from app.api.endpoints import translate
    cited_article(static_root)
    monkeypatch.setattr(translate.translation_service, "_client", FakeLLM("not json"))
    response = client.post("/api/translate/article", json={"date": DATE, "group_id": "group_1", "target_languages": ["fr"]})
    assert response.status_code == 502
    assert client.post("/api/translate/article", json={"date": DATE, "group_id": "group_1", "target_languages": ["xx"]}).status_code == 400


def test_digest_is_saved_and_survives_restart(static_root, monkeypatch):
    write_article(static_root, DATE, "group_1", "Story")
    builds = []

    def build(self, date, max_articles=20):
        builds.append(date)
        return {"date": date, "total_articles": 1, "digest": "Overview", "highlights": ["One"], "error": False}

    monkeypatch.setattr(DigestService, "_build_daily_digest", build)
    assert DigestService().generate_daily_digest(DATE)["digest"] == "Overview"
    assert DigestService().generate_daily_digest(DATE)["digest"] == "Overview"  # a "restarted" service
    assert builds == [DATE]

    write_article(static_root, DATE, "group_2", "Another story")
    DigestService().generate_daily_digest(DATE)
    assert builds == [DATE, DATE]


class FakeVoice:
    spoken = []

    def __init__(self, text, voice):
        self.text, self.voice = text, voice

    async def save(self, path):
        FakeVoice.spoken.append((self.voice, self.text))
        with open(path, "wb") as f:
            f.write(b"ID3fake")


def test_translated_audio_needs_translation_then_uses_native_voice(static_root, monkeypatch):
    monkeypatch.setattr(audio_service.edge_tts, "Communicate", FakeVoice)
    cited_article(static_root)
    url = f"/api/audio/article/{DATE}/group_1/es"
    assert client.get(url).status_code == 404  # not translated yet

    from app.api.endpoints import audio
    monkeypatch.setattr(audio.translation_service, "cached_translation",
                        lambda d, g, lang: {"summary_speech": "La ONU votó."})
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert FakeVoice.spoken[-1] == ("es-ES-ElviraNeural", "La ONU votó.")
    assert client.get(f"/api/audio/article/{DATE}/group_1/xx").status_code == 400
    assert client.get(f"/api/audio/article/{DATE}/group_9/en").status_code == 404


def test_briefing_audio_reads_the_digest(static_root, monkeypatch):
    monkeypatch.setattr(audio_service.edge_tts, "Communicate", FakeVoice)
    write_article(static_root, DATE, "group_1", "Story")
    monkeypatch.setattr(DigestService, "_build_daily_digest", lambda self, d, m=20: {
        "date": d, "total_articles": 1, "digest": "Calm day.", "highlights": ["Rates held."], "error": False})
    response = client.get(f"/api/digest/daily/{DATE}/audio")
    assert response.status_code == 200
    voice, text = FakeVoice.spoken[-1]
    assert voice == "en-US-AriaNeural"
    assert text.startswith("Your NewsSense briefing for Thursday, 01 January 2026. Calm day.")
    assert "1. Rates held." in text


def test_briefing_audio_refreshes_with_the_digest(static_root, monkeypatch):
    monkeypatch.setattr(audio_service.edge_tts, "Communicate", FakeVoice)
    path = write_article(static_root, DATE, "group_1", "Original story")
    monkeypatch.setattr(DigestService, "_build_daily_digest", lambda self, d, m=20: {
        "date": d, "total_articles": 1, "digest": json.loads(path.read_text())["headline"], "error": False})
    before = len(FakeVoice.spoken)
    url = f"/api/digest/daily/{DATE}/audio"
    assert client.get(url).status_code == 200
    version = path.stat().st_mtime_ns
    article = json.loads(path.read_text())
    path.write_text(json.dumps({**article, "headline": "Updated story"}))
    os.utime(path, ns=(version + 1_000_000_000, version + 1_000_000_000))
    assert client.get(url).status_code == 200
    assert "Updated story" in FakeVoice.spoken[-1][1]
    assert client.get(url).status_code == 200
    assert len(FakeVoice.spoken) == before + 2  # same updated script reuses its recording


def test_article_audio_refreshes_and_stale_translation_needs_refresh(static_root, monkeypatch):
    from app.api.endpoints import translate
    monkeypatch.setattr(audio_service.edge_tts, "Communicate", FakeVoice)
    path = cited_article(static_root)
    fake = FakeLLM(lambda p: json.dumps({"summary_speech": json.loads(p)["summary_speech"] + " ES"}))
    monkeypatch.setattr(translate.translation_service, "_client", fake)
    payload = {"date": DATE, "group_id": "group_1", "target_languages": ["es"]}
    url = f"/api/audio/article/{DATE}/group_1/es"
    assert client.post("/api/translate/article", json=payload).status_code == 200
    assert client.get(url).status_code == 200
    version = path.stat().st_mtime_ns
    article = json.loads(path.read_text())
    path.write_text(json.dumps({**article, "summary_speech": "Updated speech."}))
    os.utime(path, ns=(version + 1_000_000_000, version + 1_000_000_000))
    assert client.get(url).status_code == 404  # a saved translation must match its original
    assert client.post("/api/translate/article", json=payload).status_code == 200
    assert client.get(url).status_code == 200
    assert FakeVoice.spoken[-1] == ("es-ES-ElviraNeural", "Updated speech. ES")


def test_article_audio_skips_pipeline_recording_older_than_article(static_root, monkeypatch):
    monkeypatch.setattr(audio_service.edge_tts, "Communicate", FakeVoice)
    article = cited_article(static_root)
    pipeline = static_root / "static" / "audio" / DATE / "group_1.mp3"
    pipeline.parent.mkdir(parents=True)
    pipeline.write_bytes(b"old recording")
    old = article.stat().st_mtime_ns - 1_000_000_000
    os.utime(pipeline, ns=(old, old))
    assert client.get(f"/api/audio/article/{DATE}/group_1/en").content == b"ID3fake"


def test_audio_cache_tracks_voice_and_language(monkeypatch):
    first = audio_service.audio_cache("test.mp3", text="Same text")
    assert first != audio_service.audio_cache("test.mp3", text="Same text", lang="es")
    monkeypatch.setitem(audio_service.VOICES, "en", "another-voice")
    assert first != audio_service.audio_cache("test.mp3", text="Same text")


def test_failed_speech_never_leaves_partial_recordings(static_root, monkeypatch):
    cited_article(static_root)

    class BrokenVoice(FakeVoice):
        async def save(self, path):
            Path(path).write_bytes(b"half an mp3")
            raise RuntimeError("fake TTS failure")

    monkeypatch.setattr(audio_service.edge_tts, "Communicate", BrokenVoice)
    url = f"/api/audio/article/{DATE}/group_1/en"
    assert client.get(url).status_code == 502
    assert list((static_root / "cache" / "audio").rglob("*.*")) == []
    monkeypatch.setattr(audio_service.edge_tts, "Communicate", FakeVoice)
    assert client.get(url).content == b"ID3fake"


def simultaneously(call):
    barrier = threading.Barrier(2)

    def start(_):
        barrier.wait(timeout=5)
        return call()

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(start, range(2)))


def test_concurrent_digest_requests_only_generate_once(static_root, monkeypatch):
    write_article(static_root, DATE, "group_1", "Story")
    calls = []

    def build(self, date, max_articles=20):
        calls.append(date)
        time.sleep(0.1)  # overlap the two cache misses
        return {"date": date, "total_articles": 1, "digest": "Overview", "error": False}

    monkeypatch.setattr(DigestService, "_build_daily_digest", build)
    responses = simultaneously(lambda: client.get(f"/api/digest/daily/{DATE}"))
    assert [r.status_code for r in responses] == [200, 200]
    assert calls == [DATE]


def test_concurrent_translation_requests_only_generate_once(static_root, monkeypatch):
    from app.api.endpoints import translate
    cited_article(static_root)

    def slow_reply(prompt):
        time.sleep(0.1)
        return spanish(prompt)

    fake = FakeLLM(slow_reply)
    monkeypatch.setattr(translate.translation_service, "_client", fake)
    payload = {"date": DATE, "group_id": "group_1", "target_languages": ["es"]}
    responses = simultaneously(lambda: client.post("/api/translate/article", json=payload))
    assert [r.status_code for r in responses] == [200, 200]
    assert len(fake.prompts) == 1


def test_failed_translation_releases_waiters_and_does_not_cache_failure(static_root, monkeypatch):
    from app.api.endpoints import translate
    cited_article(static_root)
    attempts = []

    def retryable_reply(prompt):
        attempts.append(prompt)
        if len(attempts) == 1:
            time.sleep(0.1)
            raise RuntimeError("fake provider failure")
        return spanish(prompt)

    monkeypatch.setattr(translate.translation_service, "_client", FakeLLM(retryable_reply))
    payload = {"date": DATE, "group_id": "group_1", "target_languages": ["es"]}
    responses = simultaneously(lambda: client.post("/api/translate/article", json=payload))
    assert sorted(r.status_code for r in responses) == [200, 502]
    assert len(attempts) == 2
    assert client.post("/api/translate/article", json=payload).status_code == 200
    assert len(attempts) == 2
    from app.services.generation_cache import _pending
    assert _pending == {}


def test_atomic_cache_write_preserves_previous_file_on_failure(static_root, monkeypatch):
    from app.services.generation_cache import write_json
    path = static_root / "cache" / "saved.json"
    write_json(path, {"old": True})
    original_replace = Path.replace

    def fail_replace(source, destination):
        if source.suffix == ".tmp":
            raise OSError("fake disk error")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="fake disk error"):
        write_json(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}
    assert list(path.parent.glob("*.tmp")) == []


def test_digest_source_change_during_generation_is_not_cached(static_root, monkeypatch):
    path = write_article(static_root, DATE, "group_1", "Original")

    def build(self, date, max_articles=20):
        write_article(static_root, DATE, "group_2", "Arrived during generation")
        return {"date": date, "total_articles": 1, "digest": "Original only", "error": False}

    monkeypatch.setattr(DigestService, "_build_daily_digest", build)
    service = DigestService()
    assert service.generate_daily_digest(DATE)["digest"] == "Original only"
    assert service.cached_digest(DATE) is None


@pytest.mark.parametrize("score,expected", [(0.8, "0.80"), (None, "N/A")])
def test_article_research_includes_publisher_analysis(static_root, score, expected):
    from app.services.news_service import NewsService
    path = static_root / "static" / "resources" / DATE / "group_1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"events": [{"publisher": "Example", "publisher_country": "IN",
                                           "credibility_score": score, "event_description": "Supporting fact"}]}))
    context = NewsService().get_rag_context("group_1", DATE, "Question")
    assert "Supporting fact" in context
    assert f"Average Credibility Score: {expected}" in context


def test_translation_loaded_before_lock_cannot_be_cached_as_newer_source(static_root, monkeypatch):
    from app.api.endpoints import translate
    path = cited_article(static_root)
    fake = FakeLLM(lambda prompt: json.dumps({"summary_speech": json.loads(prompt)["summary_speech"] + " ES"}))
    monkeypatch.setattr(translate.translation_service, "_client", fake)
    original_lock = translation_service.generation_lock
    changed = []

    @contextmanager
    def update_source_before_lock(cache):
        with original_lock(cache):
            if not changed:
                article = json.loads(path.read_text())
                version = path.stat().st_mtime_ns
                path.write_text(json.dumps({**article, "summary_speech": "New factual summary."}))
                os.utime(path, ns=(version + 1_000_000_000, version + 1_000_000_000))
                changed.append(True)
            yield

    monkeypatch.setattr(translation_service, "generation_lock", update_source_before_lock)
    payload = {"date": DATE, "group_id": "group_1", "target_languages": ["es"]}
    assert client.post("/api/translate/article", json=payload).status_code == 200
    assert translation_service.TranslationService().cached_translation(DATE, "group_1", "es") is None
    current = client.post("/api/translate/article", json=payload).json()["translation"]
    assert current["summary_speech"] == "New factual summary. ES"
    assert len(fake.prompts) == 2
    assert translation_service.TranslationService().cached_translation(DATE, "group_1", "es")["summary_speech"] == current["summary_speech"]
