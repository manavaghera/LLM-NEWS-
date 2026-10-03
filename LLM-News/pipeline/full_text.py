"""Full article text for feed items, only where the publisher allows it.

A page is fetched only when all of these hold:
- fundus has a parser for the publisher,
- the publisher has not opted out of AI use (fundus' disallows_training flag; BBC and The Guardian have),
- the site's robots.txt allows our user agent to fetch the page.
Everything else keeps using its RSS headline and summary. The text is only given to the writing model
and the fact-check; it is never stored or republished.
"""
import re
import urllib.request
import urllib.robotparser
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse

# Feed publisher name (quick_news FEEDS) -> fundus PublisherCollection region and attribute
FUNDUS_PUBLISHERS = {"BBCNews": ("uk", "BBC"), "TheGuardian": ("uk", "TheGuardian"), "CBCNews": ("ca", "CBCNews")}
MAX_CHARS = 3000
MAX_PAGE_BYTES = 3 * 1024 * 1024


def shorten(text: str, limit: int = MAX_CHARS) -> str:
    """Collapse whitespace and cut at the last sentence end before the limit"""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0] + "…"


class FullTextFetcher:
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self.allowed: Dict[str, object] = {}  # feed publisher -> fundus publisher
        self.skipped: Dict[str, str] = {}     # feed publisher -> why it only gets summaries
        self._robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        try:
            from fundus import PublisherCollection
        except Exception as e:  # not installed, or a broken dependency
            self.skipped = {name: f"fundus unavailable ({str(e)[:60]})" for name in FUNDUS_PUBLISHERS}
            return
        for name, (region, attr) in FUNDUS_PUBLISHERS.items():
            publisher = getattr(getattr(PublisherCollection, region, None), attr, None)
            if publisher is None:
                self.skipped[name] = "not supported by fundus"
            elif publisher.disallows_training:
                self.skipped[name] = "opted out of AI use"
            else:
                self.allowed[name] = publisher

    def status(self) -> str:
        allowed = ", ".join(self.allowed) or "none"
        skipped = "; ".join(f"{name} ({why})" for name, why in self.skipped.items())
        return f"Full text: {allowed}" + (f". Summaries only: {skipped}" if skipped else "")

    def _get(self, url: str, limit: int) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read(limit)

    def robots_allow(self, url: str) -> bool:
        """robots.txt check, fetched with our user agent and a timeout (Python's RobotFileParser.read()
        has neither, and some sites stall unknown agents). Unreadable robots.txt = don't fetch."""
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in self._robots:
            try:
                rules = urllib.robotparser.RobotFileParser()
                rules.parse(self._get(f"{origin}/robots.txt", 512 * 1024).decode("utf-8", "replace").splitlines())
                self._robots[origin] = rules
            except Exception:
                self._robots[origin] = None
        rules = self._robots[origin]
        return bool(rules and rules.can_fetch(self.user_agent, url))

    def fetch(self, publisher: str, url: str) -> str:
        """The article's text (shortened), or "" when not allowed or not readable"""
        parser_owner = self.allowed.get(publisher)
        if not parser_owner or not url.startswith("https://") or not self.robots_allow(url):
            return ""
        try:
            html = self._get(url, MAX_PAGE_BYTES).decode("utf-8", "replace")
            parsed = parser_owner.parser(datetime.now()).parse(html, error_handling="suppress")
        except Exception as e:
            print(f"    full text skipped ({str(e)[:80]})")
            return ""
        return shorten(str(parsed.get("body") or ""))
