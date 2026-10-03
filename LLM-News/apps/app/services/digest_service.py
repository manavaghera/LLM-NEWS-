import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from ..core.config import settings
from .completion_client import CompletionClient

logger = logging.getLogger(__name__)


class DigestService:
    def __init__(self):
        self._client = None

    def cache_path(self, date: str) -> Path:
        return settings.CACHE_DIR / "digests" / f"{date}.json"

    def cached_digest(self, date: str, max_articles: int = 20) -> Optional[Dict]:
        """The saved digest, if it was written from the articles currently on disk"""
        path = self.cache_path(date)
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if saved.get("signature") == self._signature(date) and saved.get("max_articles") == max_articles:
            return saved.get("digest")
        return None

    def _signature(self, date: str) -> List[List]:
        files = Path(f"static/articles/{date}").glob("group_*.json")
        return sorted([p.name, p.stat().st_mtime_ns] for p in files)

    def generate_daily_digest(self, date: str, max_articles: int = 20) -> Dict:
        """Daily digest. Written once per set of article files (each generation is an LLM call) and
        saved to disk, so restarts don't pay for it again."""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
            raise ValueError(f"Invalid date '{date}', expected YYYY-MM-DD")
        cached = self.cached_digest(date, max_articles)
        if cached:
            return cached
        digest = self._build_daily_digest(date, max_articles)
        if not digest.get("error") and digest.get("total_articles"):
            path = self.cache_path(date)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"signature": self._signature(date), "max_articles": max_articles,
                                        "digest": digest}, ensure_ascii=False), encoding="utf-8")
        return digest

    def _get_llm_client(self):
        """Lazy-load the LLM client (first provider with an API key)."""
        if self._client is None:
            self._client = CompletionClient()
        return self._client

    def _load_articles_for_date(self, date: str) -> List[Dict]:
        """Load all articles for a given date."""
        articles_dir = Path(f"static/articles/{date}")
        if not articles_dir.exists():
            return []

        articles = []
        categories = {}
        categories_file = articles_dir / "group_categories.json"
        if categories_file.exists():
            try:
                with open(categories_file, "r", encoding="utf-8") as f:
                    categories = json.load(f)
            except Exception:
                pass

        for article_file in articles_dir.glob("group_*.json"):
            if article_file.name == "group_categories.json":
                continue
            try:
                with open(article_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    gid = article_file.stem
                    data["group_id"] = gid
                    data["category"] = categories.get(gid, "general")
                    articles.append(data)
            except Exception as e:
                logger.error(f"Error loading {article_file}: {e}")
        return articles

    def _extract_article_summary(self, article: Dict) -> str:
        """Extract a concise summary from an article for digest generation."""
        parts = []
        headline = article.get("headline", "")
        if headline:
            parts.append(f"Headline: {headline}")

        lead = article.get("lead", "")
        if lead:
            parts.append(f"Lead: {lead[:300]}")

        category = article.get("category", "general")
        parts.append(f"Category: {category}")

        # Add body section titles
        body = article.get("body", [])
        if body and isinstance(body, list):
            section_titles = [s.get("section", "") for s in body if isinstance(s, dict) and s.get("section")]
            if section_titles:
                parts.append(f"Sections: {', '.join(section_titles[:5])}")

        return "\n".join(parts)

    def _build_daily_digest(self, date: str, max_articles: int = 20) -> Dict:
        """Generate a smart daily news digest for a given date."""
        articles = self._load_articles_for_date(date)
        if not articles:
            return {
                "date": date,
                "total_articles": 0,
                "digest": "No articles available for this date.",
                "category_breakdown": {},
                "highlights": [],
            }

        # Group by category
        by_category: Dict[str, List[Dict]] = defaultdict(list)
        for article in articles[:max_articles]:
            cat = article.get("category", "general")
            by_category[cat].append(article)

        category_breakdown = {}
        for cat, cat_articles in by_category.items():
            category_breakdown[cat] = {
                "count": len(cat_articles),
                "headlines": [a.get("headline", "Untitled") for a in cat_articles[:5]],
            }

        # Build digest prompt
        article_summaries = []
        for i, article in enumerate(articles[:max_articles]):
            summary = self._extract_article_summary(article)
            article_summaries.append(f"[Article {i + 1}]\n{summary}")

        all_summaries = "\n\n".join(article_summaries)

        system_prompt = (
            "You are a professional news editor. Given a list of today's news articles, "
            "create a concise daily news digest. Include:\n"
            "1. A 2-3 sentence overview of today's news landscape\n"
            "2. Top 5 key highlights (one sentence each)\n"
            "3. A brief category-wise summary\n"
            "4. Notable trends or patterns\n"
            "Return the output as JSON with keys: overview, highlights (list), category_summary (dict), trends."
        )

        error = False
        try:
            client = self._get_llm_client()
            response = client.generate(
                prompt_content=f"Today's Date: {date}\n\nArticles:\n{all_summaries}",
                system_content=system_prompt,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            # Parse JSON from response
            try:
                digest_data = json.loads(raw)
            except json.JSONDecodeError:
                # Try extracting JSON from markdown block
                if "```json" in raw:
                    start = raw.find("{")
                    end = raw.rfind("}") + 1
                    if start != -1 and end > start:
                        digest_data = json.loads(raw[start:end])
                    else:
                        digest_data = {"overview": raw, "highlights": [], "category_summary": {}, "trends": ""}
                else:
                    digest_data = {"overview": raw, "highlights": [], "category_summary": {}, "trends": ""}
        except Exception as e:
            logger.error(f"LLM digest generation failed: {e}")
            error = True
            digest_data = {
                "overview": f"Digest generation failed: {str(e)}",
                "highlights": [],
                "category_summary": {},
                "trends": "",
            }

        return {
            "date": date,
            "total_articles": len(articles),
            "digest": digest_data.get("overview", ""),
            "highlights": digest_data.get("highlights", []),
            "category_summary": digest_data.get("category_summary", {}),
            "trends": digest_data.get("trends", ""),
            "category_breakdown": category_breakdown,
            "error": error,
        }

    def generate_category_digest(self, date: str, category: str) -> Dict:
        """Generate a digest for a specific category."""
        articles = self._load_articles_for_date(date)
        cat_articles = [a for a in articles if a.get("category", "general").lower() == category.lower()]

        if not cat_articles:
            return {
                "date": date,
                "category": category,
                "total_articles": 0,
                "digest": f"No articles found for category '{category}' on {date}.",
            }

        summaries = []
        for i, article in enumerate(cat_articles[:15]):
            summaries.append(f"[Article {i + 1}]\n{self._extract_article_summary(article)}")

        all_summaries = "\n\n".join(summaries)

        system_prompt = (
            f"You are a news editor specializing in {category} news. "
            "Create a focused digest of today's articles in this category. "
            "Include: overview (2-3 sentences), top highlights (3-5 items), and key takeaways. "
            "Return as JSON with keys: overview, highlights (list), key_takeaways."
        )

        client = self._get_llm_client()
        try:
            response = client.generate(
                prompt_content=f"Date: {date}, Category: {category}\n\nArticles:\n{all_summaries}",
                system_content=system_prompt,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            try:
                digest_data = json.loads(raw)
            except json.JSONDecodeError:
                digest_data = {"overview": raw, "highlights": [], "key_takeaways": ""}
        except Exception as e:
            logger.error(f"Category digest generation failed: {e}")
            digest_data = {"overview": f"Generation failed: {str(e)}", "highlights": [], "key_takeaways": ""}

        return {
            "date": date,
            "category": category,
            "total_articles": len(cat_articles),
            "digest": digest_data.get("overview", ""),
            "highlights": digest_data.get("highlights", []),
            "key_takeaways": digest_data.get("key_takeaways", ""),
            "articles": [{"headline": a.get("headline", ""), "group_id": a.get("group_id", "")} for a in cat_articles],
        }
