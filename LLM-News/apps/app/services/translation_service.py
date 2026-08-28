import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

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


class TranslationService:
    def __init__(self):
        self._client = None

    def _get_llm_client(self):
        """Lazy-load the LLM client."""
        if self._client is None:
            import sys
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from llm_client import LLMClient
            self._client = LLMClient(publisher="OPENAI")
        return self._client

    def _translate_text(self, text: str, target_lang: str, source_lang: str = "en") -> str:
        """Translate text using LLM."""
        if not text or not text.strip():
            return text

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        client = self._get_llm_client()

        system_prompt = (
            f"You are a professional news translator. Translate the following news article "
            f"from {SUPPORTED_LANGUAGES.get(source_lang, source_lang)} to {lang_name}. "
            f"Preserve the tone, structure, and factual accuracy. "
            f"Only return the translated text, nothing else."
        )

        try:
            response = client.generate(
                prompt_content=text,
                system_content=system_prompt,
                temperature=0.2,
                model="gpt-4o-mini",
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Translation error ({target_lang}): {e}")
            return text

    def translate_article(self, article: Dict, target_lang: str, source_lang: str = "en") -> Dict:
        """Translate a full article to the target language."""
        if target_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {target_lang}. Supported: {list(SUPPORTED_LANGUAGES.keys())}")

        if target_lang == source_lang:
            return article

        translated = dict(article)

        # Translate headline
        if "headline" in translated:
            translated["headline"] = self._translate_text(translated["headline"], target_lang, source_lang)

        # Translate lead/summary
        if "lead" in translated:
            translated["lead"] = self._translate_text(translated["lead"], target_lang, source_lang)

        # Translate body sections
        if "body" in translated and isinstance(translated["body"], list):
            translated_body = []
            for section in translated["body"]:
                if isinstance(section, dict):
                    sec = dict(section)
                    if "section" in sec:
                        sec["section"] = self._translate_text(sec["section"], target_lang, source_lang)
                    if "content" in sec:
                        sec["content"] = self._translate_text(sec["content"], target_lang, source_lang)
                    translated_body.append(sec)
                else:
                    translated_body.append(section)
            translated["body"] = translated_body

        # Translate conclusion
        if "conclusion" in translated:
            translated["conclusion"] = self._translate_text(translated["conclusion"], target_lang, source_lang)

        # Add translation metadata
        translated["_translation"] = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "target_lang_name": SUPPORTED_LANGUAGES[target_lang],
        }

        return translated

    def translate_article_to_multiple(self, article: Dict, target_langs: List[str], source_lang: str = "en") -> Dict[str, Dict]:
        """Translate an article to multiple languages."""
        results = {}
        for lang in target_langs:
            try:
                results[lang] = self.translate_article(article, lang, source_lang)
            except Exception as e:
                logger.error(f"Failed to translate to {lang}: {e}")
                results[lang] = {"error": str(e)}
        return results

    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported languages."""
        return SUPPORTED_LANGUAGES
