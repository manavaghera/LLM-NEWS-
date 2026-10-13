"""Identify a published story independently of its factual edits, media and correction history."""
import json
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def story_identity(article: dict) -> str:
    links = set()
    for section in article.get("body", []):
        if not isinstance(section, dict):
            continue
        for link in section.get("sources", []) or []:
            try:
                url = urlsplit(str(link).strip())
                if url.scheme.lower() not in ("https", "http") or not url.netloc:
                    continue
                query = sorted((k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
                               if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid"))
                links.add(urlunsplit((url.scheme.lower(), url.netloc.lower(), url.path or "/", urlencode(query), "")))
            except ValueError:
                continue
    identity = {"sources": sorted(links)} if links else {
        "headline": " ".join(str(article.get("headline", "")).lower().split())}
    return sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
