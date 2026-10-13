"""Hourly updates: today's edition keeps growing with new stories, without repeating events it covers.

Used by quick_news.py --update (what is new) and daily_update.py --interval (when, and the status file
the website shows as "Updated 2:05 PM · next update in 34 min").
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STATUS_FILE = "update_status.json"  # in apps/static, next to articles/


def edition_files(out_dir: Path) -> List[Path]:
    return sorted(p for p in out_dir.glob("group_*.json") if p.name != "group_categories.json")


def covered_texts(out_dir: Path) -> List[str]:
    """What today's stories were written from (source titles and summaries; headline and lead for articles
    without source_items), in the same form as feed items so the two can be compared"""
    texts = []
    for path in edition_files(out_dir):
        try:
            article = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sources = article.get("source_items") or []
        texts += [f"{s.get('title', '')} {s.get('summary', '')}" for s in sources]
        if not sources:
            texts.append(f"{article.get('headline', '')} {article.get('lead', '')}")
    return [t for t in texts if t.strip()]


def drop_covered_events(items: List[Dict], covered: List[str], threshold: float) -> Tuple[List[Dict], int]:
    """New feed items minus those about an event today's stories already cover: a new link about the same
    event (a follow-up, another outlet) is as similar as items grouped into one story"""
    if not items or not covered:
        return items, 0
    texts = [f"{item['title']} {item['summary']}" for item in items]
    matrix = TfidfVectorizer(stop_words="english").fit_transform(texts + covered)
    similarity = cosine_similarity(matrix[:len(items)], matrix[len(items):])
    kept = [item for item, row in zip(items, similarity) if row.max() < threshold]
    return kept, len(items) - len(kept)


def write_status(static_dir: Path, date: str, interval_minutes: int, added: int, ok: bool,
                 now: Optional[datetime] = None) -> Dict:
    """Record this update and when the next one is due (times with the UTC offset, for browsers anywhere).
    A failed run that added nothing keeps the previous update time: the site's "Updated" stays true."""
    now = (now or datetime.now()).astimezone()
    last_update = now.isoformat(timespec="seconds")
    if not ok and not added:
        try:
            previous = json.loads((static_dir / STATUS_FILE).read_text(encoding="utf-8"))
            date, last_update = previous["date"], previous["last_update"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    status = {
        "date": date,
        "last_update": last_update,
        "next_update": (now + timedelta(minutes=interval_minutes)).isoformat(timespec="seconds"),
        "interval_minutes": interval_minutes,
        "added": added,
        "ok": ok,
    }
    static_dir.mkdir(parents=True, exist_ok=True)
    part = static_dir / f"{STATUS_FILE}.part"
    part.write_text(json.dumps(status, indent=2), encoding="utf-8")
    os.replace(part, static_dir / STATUS_FILE)  # readers never see a half-written file
    return status
