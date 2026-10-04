"""
Quick news: build website articles from public RSS feeds with one LLM call per category.

A lightweight alternative to the full pipeline: no Reddit, classifiers or trust scores.
Related feed items are grouped into stories (TF-IDF similarity) before the LLM writes, each
article gets the publisher's image, and its summary is read aloud with edge-tts.
Uses LLM_PUBLISHER / LLM_MODEL from .env (e.g. OPENROUTER / qwen/qwen-plus).

Usage:
    python pipeline/quick_news.py
    python pipeline/quick_news.py --date 2026-09-30 --per-category 3 --overwrite
    python pipeline/quick_news.py --no-images --no-audio

Output (served by the website):
    apps/static/articles/{date}/group_{n}.json, group_categories.json
    apps/static/images/{date}/group_{n}.jpg
    apps/static/audio/{date}/group_{n}.mp3
"""

import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import feedparser
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_client import default_client, CHECK_MODEL, LLM_PUBLISHER, LLM_MODEL
from news_checks import claim_check, compare_coverage
from full_text import FullTextFetcher
from media import best_image, download_image, make_audio, make_thumbnail
from reliability import ReliabilityScorer

STATIC_DIR = ROOT_DIR / "apps" / "static"
ARTICLES_DIR = STATIC_DIR / "articles"
IMAGES_DIR = STATIC_DIR / "images"
AUDIO_DIR = STATIC_DIR / "audio"

USER_AGENT = "Mozilla/5.0 (LLM-NewsHub quick_news)"
MAX_STORY_ITEMS = 4

# category -> [(publisher, region, feed url)]; categories match the website's tabs
FEEDS = {
    "social": [
        ("BBCNews", "uk", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("TheGuardian", "uk", "https://www.theguardian.com/world/rss"),
        ("NPR", "us", "https://feeds.npr.org/1004/rss.xml"),
        ("AlJazeera", "qa", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("CBCNews", "ca", "https://www.cbc.ca/webfeed/rss/rss-world"),
    ],
    "tech": [
        ("BBCNews", "uk", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("TheGuardian", "uk", "https://www.theguardian.com/technology/rss"),
        ("ArsTechnica", "us", "https://feeds.arstechnica.com/arstechnica/index"),
        ("TheVerge", "us", "https://www.theverge.com/rss/index.xml"),
    ],
    "entertainment": [
        ("BBCNews", "uk", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
        ("TheGuardian", "uk", "https://www.theguardian.com/culture/rss"),
        ("NPR", "us", "https://feeds.npr.org/1008/rss.xml"),
    ],
}

SYSTEM_PROMPT = (
    "You are a careful news editor. You only state facts found in the provided items "
    "and always reply with valid JSON."
)

PROMPT_TEMPLATE = """Below are {story_count} recent {category} news stories. Each story groups feed items that cover the same event; items are numbered [1]..[{item_count}].

{stories}

Pick the {per_category} most newsworthy stories (prefer stories reported by several publishers). Write one news article per story, using ONLY the items inside that story.

Rules:
- Use ONLY facts stated in the story's items. Do not invent quotes, numbers, names or dates.
- Write in your own words. Quote at most one short phrase per section; never copy sentences from the items.
- Every body section must list the item numbers it is based on in "item_ids" (items of that story only).
- When a story has several items, use and cite all of them so readers see every publisher's reporting.
- "sentiment" is the tone of that section, from -1.0 (very negative) to 1.0 (very positive).
- Timeline keys are dates (YYYY-MM-DD) taken from the items' published dates.
- If an item looks back at past events (a retrospective, book excerpt, review or anniversary piece), say so in the
  headline (e.g. "Book excerpt: ...") instead of presenting the past events as new.

Reply with JSON exactly in this shape:
{{"articles": [{{
  "story_id": "S1",
  "headline": "...",
  "subheadline": "one sentence",
  "lead": "2-3 sentence summary",
  "body": [{{"section": "section title", "content": "1-2 paragraphs", "item_ids": [1, 2], "sentiment": 0.0}}],
  "conclusion": "1-2 sentences",
  "timeline": {{"YYYY-MM-DD": "what happened"}},
  "summary_speech": "3-4 sentences suitable for reading aloud"
}}]}}"""


def clean_text(raw: str, limit: int = 500) -> str:
    """Strip HTML tags/entities from feed text and truncate it."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rsplit(" ", 1)[0] + "..." if len(text) > limit else text


def fetch_items(category: str, per_feed: int, seen_links: set, fetcher=None) -> list:
    """Newest items from each feed of a category, skipping links in seen_links (and adding new ones)."""
    items = []
    for publisher, region, url in FEEDS[category]:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20) as response:
                feed = feedparser.parse(response.read())
        except Exception as e:
            print(f"  {publisher}: skipped ({e})")
            continue

        added = 0
        for entry in feed.entries[:per_feed]:
            link = entry.get("link", "")
            title = clean_text(entry.get("title", ""), 200)
            if not link or not title or link in seen_links:
                continue
            seen_links.add(link)
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            items.append({
                "publisher": publisher,
                "region": region,
                "title": title,
                "summary": clean_text(entry.get("summary", "")),
                "link": link,
                "image": best_image(entry),
                "published": datetime(*published[:6]).strftime("%Y-%m-%d") if published else "",
            })
            # The article itself where the publisher allows it (see full_text.py); else the RSS summary
            full = fetcher.fetch(publisher, link) if fetcher else ""
            items[-1].update(text=full or items[-1]["summary"], text_basis="full article" if full else "summary")
            added += 1
        full_count = sum(1 for item in items if item["publisher"] == publisher and item["text_basis"] == "full article")
        print(f"  {publisher}: {added} items" + (f" ({full_count} with full text)" if full_count else ""))
    return items


def previously_covered_links(date: str, include_date: bool = False) -> set:
    """Source links used by articles on other dates (and on this date when appending), so stories aren't repeated."""
    links = set()
    for path in ARTICLES_DIR.glob("*/group_*.json"):
        if (path.parent.name == date and not include_date) or path.name == "group_categories.json":
            continue
        try:
            with open(path, encoding="utf-8") as f:
                article = json.load(f)
        except (OSError, ValueError):
            continue
        for section in article.get("body", []):
            links.update(section.get("sources", []))
    return links


def group_items(items: list, threshold: float) -> dict:
    """Group items about the same event by TF-IDF cosine similarity. Returns {"S1": [item numbers]}."""
    texts = [f"{item['title']} {item['summary']}" for item in items]
    similarity = cosine_similarity(TfidfVectorizer(stop_words="english").fit_transform(texts))
    pairs = sorted(
        ((similarity[i, j], i, j) for i in range(len(items)) for j in range(i + 1, len(items))
         if similarity[i, j] >= threshold),
        reverse=True,
    )
    group_of = list(range(len(items)))
    members = {i: [i] for i in range(len(items))}
    for _, i, j in pairs:  # most similar pairs merge first; groups are capped in size
        gi, gj = group_of[i], group_of[j]
        if gi == gj or len(members[gi]) + len(members[gj]) > MAX_STORY_ITEMS:
            continue
        for k in members[gj]:
            group_of[k] = gi
        members[gi].extend(members.pop(gj))
    ordered = sorted(members.values(), key=len, reverse=True)
    return {f"S{n}": sorted(i + 1 for i in group) for n, group in enumerate(ordered, 1)}


def write_articles(category: str, items: list, stories: dict, per_category: int) -> list:
    """Ask the LLM to pick the top stories and draft one article per story."""
    blocks = []
    for story_id, numbers in stories.items():
        lines = [f"Story {story_id} ({len(numbers)} item{'s' if len(numbers) > 1 else ''}):"]
        for n in numbers:
            item = items[n - 1]
            lines.append(
                f"[{n}] {item['publisher']} ({item['region']}), published {item['published'] or 'unknown'}\n"
                f"Title: {item['title']}\n{'Article' if item.get('text_basis') == 'full article' else 'Summary'}: "
                f"{item.get('text') or item['summary']}"
            )
        blocks.append("\n".join(lines))
    prompt = PROMPT_TEMPLATE.format(
        story_count=len(stories), category=category, item_count=len(items),
        stories="\n\n".join(blocks), per_category=per_category,
    )
    for attempt in (1, 2):  # smaller/free models sometimes return broken JSON; one retry usually fixes it
        response = default_client.generate(
            prompt_content=prompt,
            system_content=SYSTEM_PROMPT,
            model=LLM_MODEL,
            temperature=0.3,
            max_tokens=6000,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        try:
            return json.loads(match.group(0) if match else content).get("articles", [])
        except (ValueError, AttributeError) as e:
            if attempt == 2:
                raise
            print(f"  the AI returned invalid JSON ({e}); retrying once")


def to_number(value, count: int):
    """A 1-based item number from the LLM, or None if invalid."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= count else None


def clamp_sentiment(value) -> float:
    try:
        return round(max(-1.0, min(1.0, float(value))), 2)
    except (TypeError, ValueError):
        return 0.0


def resolve_story(draft: dict, stories: dict, item_count: int):
    """The story a draft belongs to: its story_id, else the story of its first valid item."""
    story_id = str(draft.get("story_id", "")).strip().upper()
    if story_id in stories:
        return story_id
    for section in draft.get("body", []):
        for value in section.get("item_ids", []):
            number = to_number(value, item_count)
            if number:
                return next(sid for sid, numbers in stories.items() if number in numbers)
    return None


def build_article(draft: dict, items: list, allowed: set, category: str, date: str):
    """Convert an LLM draft into the website's article format with real source links."""
    citation_numbers = {}
    body = []
    for section in draft.get("body", []):
        numbers = [to_number(v, len(items)) for v in section.get("item_ids", [])]
        cited = [items[n - 1] for n in numbers if n in allowed]
        if not cited or not section.get("content"):
            continue  # never publish a section without a real source from its own story
        links = list(dict.fromkeys(item["link"] for item in cited))
        refs = "".join(
            f"<a href='{html.escape(link)}'>[{citation_numbers.setdefault(link, len(citation_numbers) + 1)}]</a>"
            for link in links
        )
        body.append({
            "section": section.get("section", ""),
            "content": section["content"].strip() + refs,
            "sources": links,
            "sentisement_from_the_content": clamp_sentiment(section.get("sentiment")),
            "date": date,
            "Publisher_region_diversity": sorted({item["region"] for item in cited}),
            "Publishers": sorted({item["publisher"] for item in cited}),
        })

    if not body or not draft.get("headline"):
        return None
    timeline = draft.get("timeline")
    return {
        "category": category,
        "headline": draft["headline"],
        "subheadline": draft.get("subheadline", ""),
        "lead": draft.get("lead", ""),
        "body": body,
        "conclusion": draft.get("conclusion", ""),
        "timeline": timeline if isinstance(timeline, dict) else {},
        "summary_speech": draft.get("summary_speech", ""),
        "generated_by": f"quick_news ({LLM_PUBLISHER} / {LLM_MODEL})",
    }


# Kept with each article for transparency (the full text itself is never stored)
SOURCE_FIELDS = ("publisher", "region", "title", "summary", "link", "published", "text_basis")


def enrich(article: dict, cited: list) -> list:
    """Claim check, then the coverage comparison for multi-outlet stories. Returns notes for the log."""
    notes = []
    try:
        record = claim_check(article, cited, default_client, CHECK_MODEL)
        article["claim_check"] = record
        notes.append(f"claims checked, {len(record['removed'])} removed")
    except Exception as e:
        notes.append(f"claim check failed ({str(e)[:60]})")
    try:
        coverage = compare_coverage(cited, default_client, CHECK_MODEL)
        if coverage:
            article["coverage"] = coverage
            notes.append(f"{len(coverage['perspectives'])} outlets compared")
    except Exception as e:
        notes.append(f"coverage comparison failed ({str(e)[:60]})")
    return notes


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(description="Build website articles from RSS feeds with one LLM.")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--per-category", type=int, default=3, help="articles per category (default 3)")
    parser.add_argument("--per-feed", type=int, default=6, help="newest items read from each feed (default 6)")
    parser.add_argument("--similarity", type=float, default=0.2,
                        help="how similar items must be to count as one story, 0-1 (default 0.2)")
    parser.add_argument("--no-images", action="store_true", help="don't download article images")
    parser.add_argument("--no-audio", action="store_true", help="don't generate audio summaries")
    parser.add_argument("--no-full-text", action="store_true", help="only use RSS summaries, never fetch articles")
    parser.add_argument("--no-checks", action="store_true",
                        help="skip the claim check and coverage comparison (2 fewer AI calls per article)")
    parser.add_argument("--overwrite", action="store_true", help="replace articles already made for this date")
    parser.add_argument("--append", action="store_true", help="add to this date's articles instead of replacing them")
    parser.add_argument("--categories", default=",".join(FEEDS),
                        help=f"comma-separated categories to write (default: {','.join(FEEDS)})")
    args = parser.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        sys.exit(f"Invalid --date '{args.date}', expected YYYY-MM-DD")

    chosen = [c.strip() for c in args.categories.split(",") if c.strip()]
    unknown = [c for c in chosen if c not in FEEDS]
    if unknown or not chosen:
        sys.exit(f"Unknown category {unknown}; choose from {', '.join(FEEDS)}")

    out_dir = ARTICLES_DIR / args.date
    categories_file = out_dir / "group_categories.json"
    categories = {}
    if any(out_dir.glob("group_*.json")) and not (args.overwrite or args.append):
        sys.exit(f"{out_dir} already has articles. Use --append to add to them or --overwrite to replace them.")
    if args.append and categories_file.exists():
        categories = json.loads(categories_file.read_text(encoding="utf-8"))
    else:
        for folder in (out_dir, IMAGES_DIR / args.date, AUDIO_DIR / args.date):
            for path in folder.glob("group_*"):
                path.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    next_number = max((int(g.split("_")[1]) for g in categories), default=0) + 1

    print(f"Date: {args.date} | LLM: {LLM_PUBLISHER} / {LLM_MODEL}")
    scorer = ReliabilityScorer(ROOT_DIR)
    print(scorer.status())
    if not args.no_checks:
        same = " (same as the writer: set CHECK_MODEL to a different model for a stronger check)" if CHECK_MODEL == LLM_MODEL else ""
        print(f"Fact-check model: {CHECK_MODEL}{same}")
    fetcher = None if args.no_full_text else FullTextFetcher(USER_AGENT)
    if fetcher:
        print(fetcher.status())
    seen_links = previously_covered_links(args.date, include_date=args.append)
    if seen_links:
        print(f"Skipping {len(seen_links)} links already covered on earlier dates")

    for category in chosen:
        print(f"\n[{category}] fetching feeds...")
        items = fetch_items(category, args.per_feed, seen_links, fetcher)
        if not items:
            print(f"[{category}] no new items, skipping")
            continue

        stories = group_items(items, args.similarity)
        multi = sum(len(numbers) > 1 for numbers in stories.values())
        print(f"[{category}] {len(items)} items -> {len(stories)} stories ({multi} with 2+ sources); writing...")
        try:
            drafts = write_articles(category, items, stories, args.per_category)
        except Exception as e:
            print(f"[{category}] LLM step failed: {e}")
            continue

        used_stories = set()
        for draft in drafts:
            if len(used_stories) >= args.per_category:
                break
            story_id = resolve_story(draft, stories, len(items))
            if not story_id or story_id in used_stories:
                continue
            article = build_article(draft, items, set(stories[story_id]), category, args.date)
            if not article:
                continue
            used_stories.add(story_id)

            by_link = {item["link"]: item for item in items}
            cited = [by_link[link] for link in dict.fromkeys(l for s in article["body"] for l in s["sources"])]
            # What the article was written from, kept for transparency and later re-checks
            article["source_items"] = [{k: it[k] for k in SOURCE_FIELDS} for it in cited]
            notes = []
            if not args.no_checks:
                notes += enrich(article, cited)
                if not article["body"]:
                    print(f"  dropped (no sentence was supported by its sources): {article['headline']}")
                    continue
            for section in article["body"]:
                section.update(scorer.score_section(section["content"], section["sources"]))
            group_id = f"group_{next_number}"
            next_number += 1

            sources = list(dict.fromkeys(link for section in article["body"] for link in section["sources"]))
            image_note = "no image"
            for link in ([] if args.no_images else sources):  # first source whose image downloads
                item = by_link[link]
                image_file = item["image"] and download_image(item["image"], IMAGES_DIR / args.date, group_id)
                if image_file:
                    article["image_file"] = image_file
                    article["image_thumb"] = make_thumbnail(IMAGES_DIR / args.date / image_file) or None
                    article["image_credit"] = item["publisher"]
                    article["image_source"] = item["link"]
                    image_note = f"image: {item['publisher']}"
                    break

            with open(out_dir / f"{group_id}.json", "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            categories[group_id] = category

            audio_note = "no audio"
            if not args.no_audio and article["summary_speech"]:
                if make_audio(article["summary_speech"], AUDIO_DIR / args.date / f"{group_id}.mp3"):
                    audio_note = "audio"
            details = ", ".join([story_id, f"{len(sources)} sources", image_note, audio_note, *notes])
            print(f"  {group_id} ({details}): {article['headline']}")

    if not categories:
        if not any(out_dir.iterdir()):
            out_dir.rmdir()
        sys.exit("\nNo articles were written. Check your API key / LLM_PUBLISHER in .env and the errors above.")

    with open(categories_file, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2)
    print(f"\nDone: {len(categories)} articles saved to {out_dir}")
    print("Refresh http://localhost:3000 to see them.")


if __name__ == "__main__":
    main()
