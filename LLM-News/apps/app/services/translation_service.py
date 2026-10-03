import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.config import settings
from .completion_client import CompletionClient

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "pt": "Portuguese",
    "hi": "Hindi",
}

CITATION = re.compile(r"<a\s[^>]*?href\s*=\s*(['\"])(.*?)\1[^>]*>\s*\[\d+\]\s*</a>", re.IGNORECASE)
MARKER = "⟦{}⟧"
SAFE_ID = re.compile(r"\d{4}-\d{2}-\d{2}/group_\d+")


def protect_citations(content: str) -> Tuple[str, List[str]]:
    """Swap citation links for ⟦n⟧ markers so the translator can't mangle them"""
    links: List[str] = []

    def keep(match: re.Match) -> str:
        links.append(match.group(0))
        return MARKER.format(len(links))

    return CITATION.sub(keep, content), links


def restore_citations(content: str, links: List[str]) -> str:
    """Put the links back; any marker the model dropped is re-attached at the end"""
    for n, link in enumerate(links, 1):
        marker = MARKER.format(n)
        content = content.replace(marker, link, 1) if marker in content else content + link
    return content


class TranslationService:
    def __init__(self):
        self._client = None

    def _get_llm_client(self):
        """Lazy-load the LLM client (first provider with an API key)."""
        if self._client is None:
            self._client = CompletionClient()
        return self._client

    def _translate_text(self, text: str, target_lang: str, source_lang: str = "en") -> str:
        """Translate plain text with one LLM call (raises on failure instead of returning the original)"""
        if not text or not text.strip():
            return text
        response = self._get_llm_client().generate(
            prompt_content=text,
            system_content=(
                f"You are a professional news translator. Translate the following text from "
                f"{SUPPORTED_LANGUAGES.get(source_lang, source_lang)} to {SUPPORTED_LANGUAGES.get(target_lang, target_lang)}. "
                "Preserve the tone and factual accuracy. Only return the translated text, nothing else."
            ),
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()

    def _cache_path(self, date: Optional[str], group_id: Optional[str], lang: str) -> Optional[Path]:
        if not date or not group_id or not SAFE_ID.fullmatch(f"{date}/{group_id}"):
            return None
        return settings.CACHE_DIR / "translations" / date / f"{group_id}.{lang}.json"

    def translate_article(self, article: Dict, target_lang: str, source_lang: str = "en",
                          date: Optional[str] = None, group_id: Optional[str] = None) -> Dict:
        """Translate a whole article with one LLM call; saved and reused until the article changes."""
        if target_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {target_lang}. Supported: {list(SUPPORTED_LANGUAGES.keys())}")
        if target_lang == source_lang:
            return article

        cache = self._cache_path(date, group_id, target_lang)
        source_file = Path(f"static/articles/{date}/{group_id}.json")
        source_version = source_file.stat().st_mtime_ns if cache and source_file.exists() else None
        if cache and cache.exists():
            try:
                saved = json.loads(cache.read_text(encoding="utf-8"))
                if saved.get("source_version") == source_version:
                    return saved["article"]
            except (OSError, ValueError, KeyError):
                pass

        sections = [s for s in article.get("body", []) if isinstance(s, dict)]
        protected = [protect_citations(str(s.get("content", ""))) for s in sections]
        payload = {
            "headline": article.get("headline", ""),
            "subheadline": article.get("subheadline", ""),
            "lead": article.get("lead", ""),
            "sections": [{"section": s.get("section", ""), "content": text} for s, (text, _) in zip(sections, protected)],
            "conclusion": article.get("conclusion", ""),
            "timeline": article.get("timeline") or {},
            "summary_speech": article.get("summary_speech", ""),
        }
        response = self._get_llm_client().generate(
            prompt_content=json.dumps(payload, ensure_ascii=False),
            system_content=(
                f"You are a professional news translator. Translate every text value in this JSON from "
                f"{SUPPORTED_LANGUAGES.get(source_lang, source_lang)} to {SUPPORTED_LANGUAGES[target_lang]}. "
                "Keep the same keys and structure (timeline keys are dates: keep them unchanged). "
                "Keep markers like ⟦1⟧ exactly as they are, in the matching place. "
                "Preserve tone and factual accuracy. Return only the JSON."
            ),
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            result = json.loads(match.group(0) if match else raw)
        except ValueError as e:  # the model's fault, not a bad request
            raise RuntimeError("The AI returned a translation that couldn't be read") from e
        if not isinstance(result, dict):
            raise RuntimeError("The AI returned a translation in an unexpected shape")

        translated = dict(article)
        for key in ("headline", "subheadline", "lead", "conclusion", "summary_speech"):
            if isinstance(result.get(key), str) and article.get(key):
                translated[key] = result[key]
        if isinstance(result.get("timeline"), dict) and article.get("timeline"):
            translated["timeline"] = {k: str(v) for k, v in result["timeline"].items()}

        out_sections = result.get("sections") if isinstance(result.get("sections"), list) else []
        body = []
        for i, (section, (_, links)) in enumerate(zip(sections, protected)):
            new = dict(section)
            done = out_sections[i] if i < len(out_sections) and isinstance(out_sections[i], dict) else {}
            if isinstance(done.get("section"), str):
                new["section"] = done["section"]
            content = done.get("content") if isinstance(done.get("content"), str) else protected[i][0]
            new["content"] = restore_citations(content, links)
            body.append(new)
        translated["body"] = body
        translated["_translation"] = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "target_lang_name": SUPPORTED_LANGUAGES[target_lang],
        }

        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"source_version": source_version, "article": translated}, ensure_ascii=False),
                             encoding="utf-8")
        return translated

    def cached_translation(self, date: str, group_id: str, lang: str) -> Optional[Dict]:
        """A saved translation, if one exists (used for translated audio)"""
        cache = self._cache_path(date, group_id, lang)
        if not cache or not cache.exists():
            return None
        try:
            return json.loads(cache.read_text(encoding="utf-8"))["article"]
        except (OSError, ValueError, KeyError):
            return None

    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported languages."""
        return SUPPORTED_LANGUAGES
