"""Translation, saved digests and audio, with a fake LLM and fake voice. Run from LLM-News/apps: python -m pytest tests"""
import json
import os
from types import SimpleNamespace

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
