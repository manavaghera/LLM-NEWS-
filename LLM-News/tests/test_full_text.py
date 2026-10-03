"""Full-text rules (no network). Run from LLM-News: python -m pytest tests"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from full_text import FullTextFetcher, shorten  # noqa: E402

ALLOW = b"User-agent: *\nAllow: /\n"
DENY = b"User-agent: *\nDisallow: /news/\n"
PAGE = "<html><body>article</body></html>"


def fake_publisher(body: str):
    parser = SimpleNamespace(parse=lambda html, error_handling: {"body": body})
    return SimpleNamespace(parser=lambda crawl_date: parser)


def fetcher_with(robots: bytes, body: str = "The vote passed. It was close.", monkeypatch=None) -> FullTextFetcher:
    fetcher = FullTextFetcher("test-agent")
    fetcher.allowed = {"CBCNews": fake_publisher(body)}
    fetcher._get = lambda url, limit: robots if url.endswith("/robots.txt") else PAGE.encode()
    return fetcher


def test_publishers_that_opted_out_are_never_fetched():
    fetcher = FullTextFetcher("test-agent")
    # Real fundus flags: BBC and The Guardian disallow AI use, CBC does not
    assert fetcher.skipped.get("BBCNews") == "opted out of AI use"
    assert fetcher.skipped.get("TheGuardian") == "opted out of AI use"
    assert "CBCNews" in fetcher.allowed
    fetcher._get = lambda url, limit: (_ for _ in ()).throw(AssertionError("no request may be made"))
    assert fetcher.fetch("BBCNews", "https://www.bbc.co.uk/news/1") == ""


def test_fetches_only_when_robots_allow_and_over_https():
    assert fetcher_with(ALLOW).fetch("CBCNews", "https://www.cbc.ca/news/world/a") == "The vote passed. It was close."
    assert fetcher_with(DENY).fetch("CBCNews", "https://www.cbc.ca/news/world/a") == ""
    assert fetcher_with(ALLOW).fetch("CBCNews", "http://www.cbc.ca/news/world/a") == ""
    assert fetcher_with(ALLOW).fetch("NPR", "https://www.npr.org/a") == ""  # no parser: summary only


def test_unreadable_robots_means_no_fetch():
    fetcher = fetcher_with(ALLOW)
    fetcher._get = lambda url, limit: (_ for _ in ()).throw(TimeoutError("stalled"))
    assert fetcher.fetch("CBCNews", "https://www.cbc.ca/news/world/a") == ""


def test_shorten_cuts_at_a_sentence_end():
    text = "First sentence here. " * 200
    short = shorten(text, limit=100)
    assert len(short) <= 100 and short.endswith(".")
    assert shorten("  a   b  ") == "a b"
