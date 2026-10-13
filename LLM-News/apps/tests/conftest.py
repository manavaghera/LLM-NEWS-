import json
import sys
from pathlib import Path

import pytest

# Make the `app` package importable when running `python -m pytest tests` from apps/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def fresh_rate_limits(monkeypatch, tmp_path):
    """Each test starts with fresh visitor counters; limit tests can replace them explicitly."""
    from app.core import limits
    from app.api.endpoints import reports

    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    for name in ("ai_rate_limiter", "ai_visitor_daily_limiter"):
        previous = getattr(limits, name)
        monkeypatch.setattr(limits, name, limits.RateLimiter(previous.limit, previous.window, previous.reason))
    monkeypatch.setattr(reports, "report_limiter", limits.RateLimiter(5))


@pytest.fixture
def static_root(tmp_path, monkeypatch):
    """Run a test against an empty static/ folder: the backend resolves static/ from the working directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "static" / "articles").mkdir(parents=True)
    return tmp_path


def write_article(root: Path, date: str, group_id: str, headline: str, category: str = "tech") -> Path:
    """Write one article in the pipeline's format and register its category."""
    folder = root / "static" / "articles" / date
    folder.mkdir(parents=True, exist_ok=True)
    article = {
        "headline": headline,
        "lead": f"Lead for {headline}",
        "body": [{"section": "Section", "content": "Content", "sources": ["https://example.com/a"]}],
    }
    path = folder / f"{group_id}.json"
    path.write_text(json.dumps(article), encoding="utf-8")

    categories_file = folder / "group_categories.json"
    categories = json.loads(categories_file.read_text()) if categories_file.exists() else {}
    categories[group_id] = category
    categories_file.write_text(json.dumps(categories))
    return path
