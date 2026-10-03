"""Features that look across every edition: archive search and earlier coverage of a story."""
import re
from typing import Dict, List

from .news_service import NewsService, group_number
from .topics import shared_story_score, topics_of


def search_archive(news: NewsService, query: str, limit: int = 40) -> List[Dict]:
    """Stories from every edition whose text contains all the query's words, newest first;
    headline matches rank first within an edition"""
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1]
    if not words:
        return []
    results = []
    for date in news.available_dates():
        matches = []
        for group_id, article in news.load_articles_for_date(date).items():
            body = " ".join(
                f"{s.get('section', '')} {s.get('content', '')} {' '.join(map(str, s.get('Publishers', []) or []))}"
                for s in article.get("body", []) if isinstance(s, dict)
            )
            headline = article.get("headline", "").lower()
            text = re.sub(r"<[^>]*>", " ", f"{headline} {article.get('subheadline', '')} {article.get('lead', '')} {body}").lower()
            if all(w in text for w in words):
                matches.append((-sum(w in headline for w in words), group_number(group_id), group_id, article))
        for *_, group_id, article in sorted(matches, key=lambda m: m[:2]):
            results.append(news.news_item(date, group_id, article))
            if len(results) >= limit:
                return results
    return results


def related_articles(news: NewsService, date: str, group_id: str, limit: int = 5, days: int = 30) -> List[Dict]:
    """Earlier coverage of the same running story: articles from previous editions (up to `days`
    back) sharing named topics with this one; strongest match first, then the most recent"""
    article = news.get_article(date, group_id)
    if not article:
        return []
    target = topics_of(article)
    matches = []
    for earlier in [d for d in news.available_dates() if d < date][:days]:
        for other_id, other in news.load_articles_for_date(earlier).items():
            other_topics = topics_of(other)
            score = shared_story_score(target, other_topics)
            if score:
                shared = sorted(target & other_topics, key=lambda t: (-len(t.split()), t))
                matches.append((score, earlier, other_id, other, shared))
    matches.sort(key=lambda m: m[1], reverse=True)  # newest first...
    matches.sort(key=lambda m: -m[0])                # ...within equal scores
    return [{**news.news_item(d, gid, a), "shared_topics": shared[:4]} for _, d, gid, a, shared in matches[:limit]]
