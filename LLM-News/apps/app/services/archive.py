"""Features that look across every edition: archive search and earlier coverage of a story."""
import re
from typing import Dict, List, Set

from .news_service import NewsService, group_number
from .topics import broad_topics, shared_story_score, topics_of


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


def headline_names(article: Dict, topics: Set[str], broad: Set[str]) -> Set[str]:
    """The article's single-word names that are also in its headline, i.e. its own subject ("G7" in
    "G7 agrees to release oil"), unless several stories of an edition mention them ("US")"""
    words = set(re.findall(r"\w+", article.get("headline", "")))
    return {t for t in topics if t in words and t not in broad}


def with_headline_names(article: Dict, topics: Set[str], other_topics: Set[str]) -> Set[str]:
    """Adds the other article's single-word names that this headline mentions. The body may only use them
    at a sentence start, where they look ambiguous ("Brazil's presidential election ..." after a full stop)."""
    words = set(re.findall(r"\w+", article.get("headline", "")))
    return topics | {t for t in other_topics if " " not in t and t in words}


def related_articles(news: NewsService, date: str, group_id: str, limit: int = 5, days: int = 30) -> List[Dict]:
    """Earlier coverage of the same running story: articles from previous editions (up to `days`
    back) sharing named topics with this one; strongest match first, then the most recent"""
    article = news.get_article(date, group_id)
    if not article:
        return []
    target = topics_of(article)
    earlier = {
        d: {gid: (a, topics_of(a)) for gid, a in news.load_articles_for_date(d).items()}
        for d in [d for d in news.available_dates() if d < date][:days]
    }
    today = [topics_of(a) for a in news.load_articles_for_date(date).values()]
    broad = broad_topics([today] + [[t for _, t in stories.values()] for stories in earlier.values()])
    matches = []
    for d, stories in earlier.items():
        for other_id, (other, other_topics) in stories.items():
            mine, theirs = with_headline_names(article, target, other_topics), with_headline_names(other, other_topics, target)
            strong = headline_names(article, mine, broad) & headline_names(other, theirs, broad)
            score = shared_story_score(mine, theirs, strong)
            if score:
                shared = sorted(mine & theirs, key=lambda t: (t not in strong and " " not in t, -len(t.split()), t))
                matches.append((score, d, other_id, other, shared))
    matches.sort(key=lambda m: m[1], reverse=True)  # newest first...
    matches.sort(key=lambda m: -m[0])                # ...within equal scores
    return [{**news.news_item(d, gid, a), "shared_topics": shared[:4]} for _, d, gid, a, shared in matches[:limit]]
