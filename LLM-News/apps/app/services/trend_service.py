import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import re

from .topics import article_topics

logger = logging.getLogger(__name__)


class TrendService:
    def __init__(self):
        self.trends_cache: Dict[str, Dict] = {}

    def _load_all_articles(self) -> Dict[str, List[Dict]]:
        """Load articles from all available dates."""
        static_dir = Path("static/articles")
        if not static_dir.exists():
            return {}

        all_articles: Dict[str, List[Dict]] = {}
        for date_dir in sorted(static_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            date_str = date_dir.name
            articles = []
            for article_file in date_dir.glob("group_*.json"):
                if article_file.name == "group_categories.json":
                    continue
                try:
                    with open(article_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["group_id"] = article_file.stem
                        data["date"] = date_str
                        articles.append(data)
                except Exception as e:
                    logger.error(f"Error loading {article_file}: {e}")
            if articles:
                all_articles[date_str] = articles

        return all_articles

    def get_trending_topics(self, days: int = 7, top_n: int = 10) -> Dict:
        """Identify trending topics across recent dates."""
        all_articles = self._load_all_articles()
        if not all_articles:
            return {"trending_topics": [], "total_dates": 0}

        sorted_dates = sorted(all_articles.keys(), reverse=True)[:days]

        # Number of stories mentioning each name/phrase, per day
        keyword_by_date: Dict[str, Counter] = {
            date_str: Counter(article_topics(all_articles[date_str])) for date_str in sorted_dates
        }

        # Aggregate across all dates
        total_counts: Counter = Counter()
        for counter in keyword_by_date.values():
            total_counts.update(counter)

        # Detect growth: compare recent vs older
        recent_dates = sorted_dates[: max(1, len(sorted_dates) // 2)]
        older_dates = sorted_dates[max(1, len(sorted_dates) // 2):]

        recent_counts: Counter = Counter()
        older_counts: Counter = Counter()
        for d in recent_dates:
            recent_counts.update(keyword_by_date.get(d, Counter()))
        for d in older_dates:
            older_counts.update(keyword_by_date.get(d, Counter()))

        trending = []
        for word, count in total_counts.items():
            recent = recent_counts.get(word, 0)
            older = older_counts.get(word, 0)
            growth = ((recent - older) / max(older, 1)) * 100
            trending.append({
                "keyword": word,
                "total_count": count,
                "recent_count": recent,
                "older_count": older,
                "growth_pct": round(growth, 1),
            })

        # Most-covered first; growth and longer (more specific) names break ties
        trending.sort(key=lambda x: (-x["total_count"], -x["growth_pct"], -len(x["keyword"].split()), x["keyword"]))
        trending = trending[:top_n]

        return {
            "trending_topics": trending,
            "total_dates": len(sorted_dates),
            "date_range": {"from": sorted_dates[-1] if sorted_dates else "", "to": sorted_dates[0] if sorted_dates else ""},
        }

    def get_category_trends(self, days: int = 7) -> Dict:
        """Get article count trends per category over time."""
        all_articles = self._load_all_articles()
        if not all_articles:
            return {"category_trends": [], "total_dates": 0}

        sorted_dates = sorted(all_articles.keys(), reverse=True)[:days]
        category_trends: Dict[str, List[Dict]] = defaultdict(list)

        for date_str in sorted(sorted_dates):
            cat_counts: Counter = Counter()
            for article in all_articles[date_str]:
                cat = article.get("category", "general")
                cat_counts[cat] += 1
            for cat, count in cat_counts.items():
                category_trends[cat].append({"date": date_str, "count": count})

        return {
            "category_trends": dict(category_trends),
            "total_dates": len(sorted_dates),
        }

    def get_sentiment_over_time(self, days: int = 7) -> Dict:
        """Track average sentiment per category over time."""
        all_articles = self._load_all_articles()
        if not all_articles:
            return {"sentiment_trends": [], "total_dates": 0}

        sorted_dates = sorted(all_articles.keys(), reverse=True)[:days]
        sentiment_by_date: List[Dict] = []

        for date_str in sorted(sorted_dates):
            cat_sentiments: Dict[str, List[float]] = defaultdict(list)
            for article in all_articles[date_str]:
                cat = article.get("category", "general")
                for section in article.get("body", []):
                    if isinstance(section, dict):
                        try:
                            score = float(section.get("sentisement_from_the_content", 0))
                            if score != 0:
                                cat_sentiments[cat].append(score)
                        except (ValueError, TypeError):
                            pass

            date_entry = {"date": date_str, "categories": {}}
            for cat, scores in cat_sentiments.items():
                if scores:
                    date_entry["categories"][cat] = {
                        "avg_sentiment": round(sum(scores) / len(scores), 3),
                        "article_count": len(scores),
                    }
            sentiment_by_date.append(date_entry)

        return {
            "sentiment_trends": sentiment_by_date,
            "total_dates": len(sorted_dates),
        }

    def get_publisher_diversity(self, date: Optional[str] = None) -> Dict:
        """Analyze publisher and regional diversity for a date."""
        all_articles = self._load_all_articles()
        if not all_articles:
            return {"publishers": [], "regions": [], "total_articles": 0}

        if not date:
            date = max(all_articles.keys())

        articles = all_articles.get(date, [])
        publisher_counter: Counter = Counter()
        region_counter: Counter = Counter()

        for article in articles:
            for section in article.get("body", []):
                if isinstance(section, dict):
                    pubs = section.get("Publishers", [])
                    if isinstance(pubs, list):
                        for p in pubs:
                            if p:
                                publisher_counter[str(p)] += 1
                    regions = section.get("Publisher_region_diversity", [])
                    if isinstance(regions, list):
                        for r in regions:
                            if r:
                                region_counter[str(r)] += 1

        return {
            "date": date,
            "publishers": [{"name": k, "count": v} for k, v in publisher_counter.most_common(20)],
            "regions": [{"name": k, "count": v} for k, v in region_counter.most_common(20)],
            "total_articles": len(articles),
            "unique_publishers": len(publisher_counter),
            "unique_regions": len(region_counter),
        }

    def get_accuracy(self, days: int = 30) -> Dict:
        """Fact-check results per day and per writer/checker model pair: how many of the article
        statements the second AI pass could not match to the sources (and removed)."""
        all_articles = self._load_all_articles()
        dates = sorted(all_articles.keys(), reverse=True)[:days]
        by_day, by_models = [], {}
        for date_str in sorted(dates):
            day = {"date": date_str, "articles": len(all_articles[date_str]), "checked": 0, "statements": 0, "removed": 0}
            for article in all_articles[date_str]:
                check = article.get("claim_check") or {}
                if not check.get("checked"):
                    continue
                statements, removed = int(check.get("statements") or 0), len(check.get("removed") or [])
                day["checked"] += 1
                day["statements"] += statements
                day["removed"] += removed
                writer = writer_model(article.get("generated_by", ""))
                pair = by_models.setdefault((writer, check.get("model") or writer),
                                            {"articles": 0, "statements": 0, "removed": 0})
                pair["articles"] += 1
                pair["statements"] += statements
                pair["removed"] += removed
            day["removed_pct"] = round(100 * day["removed"] / day["statements"], 1) if day["statements"] else None
            by_day.append(day)
        models = [
            {"writer": writer, "checker": checker, **counts,
             "removed_pct": round(100 * counts["removed"] / counts["statements"], 1) if counts["statements"] else None}
            for (writer, checker), counts in by_models.items()
        ]
        return {"days": by_day, "models": sorted(models, key=lambda m: -m["articles"])}


def writer_model(generated_by: str) -> str:
    """"quick_news (OPENROUTER / qwen/qwen-plus)" -> "qwen/qwen-plus"; "unknown" for older articles"""
    match = re.search(r"\(([^)]*)\)", generated_by or "")
    parts = match.group(1).split(" / ", 1) if match else []
    return parts[1] if len(parts) == 2 else "unknown"
