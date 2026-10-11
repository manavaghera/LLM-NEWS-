"""Spoken audio with edge-tts (Microsoft's free neural voices; no API key). Files are saved and reused."""
import uuid
from hashlib import sha256
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import edge_tts

from ..core.config import settings

# One natural voice per supported language (same English voice as the news pipeline)
VOICES = {
    "en": "en-US-AriaNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "ar": "ar-SA-ZariyahNeural",
    "pt": "pt-BR-FranciscaNeural",
    "hi": "hi-IN-SwaraNeural",
}

MAX_CHARS = 6000  # keeps a request from generating a very long recording


def audio_cache(*parts: str, text: str, lang: str = "en") -> Path:
    """A recording belongs to its spoken script, language and voice, not just its edition."""
    path = settings.CACHE_DIR.joinpath("audio", *parts)
    voice = VOICES.get(lang, VOICES["en"])
    version = sha256(f"{lang}\0{voice}\0{text[:MAX_CHARS]}".encode("utf-8")).hexdigest()[:20]
    return path.with_name(f"{path.stem}.{version}{path.suffix}")


async def speak(text: str, path: Path, lang: str = "en") -> Path:
    """Write text as an mp3 at path (skipped when it already exists)."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.part")  # never serve a half-written file
    try:
        await edge_tts.Communicate(text[:MAX_CHARS], VOICES.get(lang, VOICES["en"])).save(str(partial))
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return path


def _text_items(value) -> List[str]:
    """LLM output as plain lines: "text", ["a", "b"] or {"k": "v"}"""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [t for v in value for t in _text_items(v)]
    if isinstance(value, dict):
        return [t for v in value.values() for t in _text_items(v)]
    return []


def briefing_script(digest: Dict) -> str:
    """What the daily briefing says: the overview, then each highlight"""
    day = datetime.strptime(digest["date"], "%Y-%m-%d").strftime("%A, %d %B %Y")
    parts = [f"Your NewsSense briefing for {day}.", *_text_items(digest.get("digest"))]
    highlights = _text_items(digest.get("highlights"))
    if highlights:
        parts.append("Here are the highlights.")
        parts += [f"{n}. {text}" for n, text in enumerate(highlights, 1)]
    parts.append("That's the briefing. Every story on NewsSense links to its original sources.")
    return " ".join(parts)
