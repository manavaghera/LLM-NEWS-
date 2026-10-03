"""Second-pass AI checks for quick_news articles.

claim_check:      verifies every sentence against the feed items it was written from and removes the
                  ones they don't support (the article records what was removed and why).
compare_coverage: for stories reported by several outlets, describes how each one framed it.

Both work only from the items' headlines and summaries, and say so in their output.
"""
import json
import re
from typing import Dict, List, Optional, Tuple

CITATION = re.compile(r"<a\s[^>]*?href\s*=\s*(['\"])(.*?)\1[^>]*>\s*\[\d+\]\s*</a>", re.IGNORECASE)
# Possible sentence end: . ! ? (+ closing quotes), any citation links after it, space, then a capital/quote/digit
BOUNDARY = re.compile(r"[.!?]+[\"”’)]*(?:\s*<a\s[^>]*>\s*\[\d+\]\s*</a>)*\s+(?=[A-Z\"“‘0-9])")
# ...unless the period ends an abbreviation: U.S., Mr., Gov.
ABBREVIATION = re.compile(r"(?:\b[A-Z]|\b(?:Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|No|Gov|Sen|Rep|Gen|Lt|Col|Inc|Ltd|Co|Corp))\.$")


def split_sentences(text: str) -> List[str]:
    """Sentences with their trailing citation links attached; "".join(result) == text"""
    text = text or ""
    sentences, start = [], 0
    for match in BOUNDARY.finditer(text):
        if ABBREVIATION.search(text[:match.start() + 1]):
            continue
        sentences.append(text[start:match.end()])
        start = match.end()
    if start < len(text):
        sentences.append(text[start:])
    return sentences


def plain(sentence: str) -> str:
    return re.sub(r"\s+", " ", CITATION.sub("", sentence)).strip()


def _ask_json(client, model: str, system: str, prompt: str) -> Dict:
    for attempt in (1, 2):  # one retry: smaller/free models sometimes return broken JSON
        response = client.generate(prompt_content=prompt, system_content=system, model=model,
                                   temperature=0, max_tokens=4000, response_format={"type": "json_object"})
        raw = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            result = json.loads(match.group(0) if match else raw)
            if isinstance(result, dict):
                return result
            raise ValueError("unexpected JSON shape")
        except ValueError:
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


def _items_block(items: List[Dict]) -> str:
    return "\n".join(f"[{i}] {it['publisher']}: {it['title']} — {it.get('text') or it['summary']}" for i, it in enumerate(items, 1))


def claim_check(article: Dict, items: List[Dict], client, model: str) -> Dict:
    """Remove sentences the source items don't support. Mutates article; returns the claim_check record."""
    statements: Dict[str, str] = {}
    parts: Dict[str, List[str]] = {}

    def register(prefix: str, text: str):
        sentences = split_sentences(text)
        parts[prefix] = sentences
        for n, sentence in enumerate(sentences, 1):
            if plain(sentence):
                statements[f"{prefix}.{n}"] = plain(sentence)

    register("L", article.get("lead", ""))
    register("C", article.get("conclusion", ""))
    for i, section in enumerate(article.get("body", []), 1):
        register(f"S{i}", section.get("content", ""))
    timeline = article.get("timeline") or {}
    for i, (day, event) in enumerate(timeline.items(), 1):
        statements[f"T{i}"] = f"On {day}: {event}"

    result = _ask_json(
        client, model,
        "You are a meticulous fact-checker for a news site. Reply with JSON only.",
        f"SOURCE ITEMS (headline — summary):\n{_items_block(items)}\n\n"
        "STATEMENTS:\n" + "\n".join(f"{sid}: {text}" for sid, text in statements.items()) + "\n\n"
        "A statement is UNSUPPORTED if it contains a fact, number, name, quote, date or cause that the source "
        "items do not contain or imply. Paraphrase and neutral framing are fine.\n"
        'Return {"unsupported": [{"id": "<statement id>", "reason": "<short reason>"}]} '
        "(an empty list if every statement is supported).",
    )
    flagged = {str(u.get("id")): str(u.get("reason", "")) for u in result.get("unsupported", []) if isinstance(u, dict)}
    flagged = {sid: reason for sid, reason in flagged.items() if sid in statements}

    removed = [{"text": statements[sid], "reason": reason} for sid, reason in flagged.items()]
    keep = lambda prefix: "".join(s for n, s in enumerate(parts[prefix], 1) if f"{prefix}.{n}" not in flagged).strip()
    article["lead"] = keep("L")
    article["conclusion"] = keep("C")
    body = []
    for i, section in enumerate(article.get("body", []), 1):
        content = keep(f"S{i}")
        if plain(content):
            body.append({**section, "content": content})
    article["body"] = body
    article["timeline"] = {day: event for i, (day, event) in enumerate(timeline.items(), 1) if f"T{i}" not in flagged}

    full = any(it.get("text_basis") == "full article" for it in items)
    return {"checked": True, "statements": len(statements), "removed": removed, "model": model,
            "basis": "the source articles" if full else "the source headlines and summaries"}


def compare_coverage(items: List[Dict], client, model: str) -> Optional[Dict]:
    """How each outlet framed a story it shared with others (None when fewer than two outlets)."""
    by_publisher: Dict[str, List[Dict]] = {}
    for item in items:
        by_publisher.setdefault(item["publisher"], []).append(item)
    if len(by_publisher) < 2:
        return None

    reports = "\n\n".join(
        f"OUTLET: {publisher}\n" + "\n".join(f"- {it['title']} — {it.get('text') or it['summary']}" for it in group)
        for publisher, group in by_publisher.items()
    )
    result = _ask_json(
        client, model,
        "You are a media analyst comparing news coverage. Use only the text given. Reply with JSON only.",
        f"These outlets reported the same story (headline — summary):\n\n{reports}\n\n"
        "For each outlet give: angle (one sentence: what it leads with), tone (-1.0 negative to 1.0 positive), "
        "emphasis (what it stresses), not_mentioned (facts other outlets include that this outlet's text does not; "
        "may be empty). Then common_ground (what all agree on) and differences (one or two sentences).\n"
        'Return {"perspectives": [{"publisher": "...", "angle": "...", "tone": 0.0, "emphasis": "...", '
        '"not_mentioned": ["..."]}], "common_ground": "...", "differences": "..."}',
    )

    perspectives = []
    for p in result.get("perspectives", []):
        if not isinstance(p, dict) or p.get("publisher") not in by_publisher:
            continue  # only outlets that are actually in the story
        try:
            tone = max(-1.0, min(1.0, float(p.get("tone", 0))))
        except (TypeError, ValueError):
            tone = 0.0
        perspectives.append({
            "publisher": p["publisher"],
            "region": by_publisher[p["publisher"]][0]["region"],
            "angle": str(p.get("angle", "")),
            "tone": round(tone, 2),
            "emphasis": str(p.get("emphasis", "")),
            "not_mentioned": [str(x) for x in p.get("not_mentioned", []) if x][:4],
            "links": [it["link"] for it in by_publisher[p["publisher"]]],
        })
    if len(perspectives) < 2:
        return None
    return {"perspectives": perspectives, "common_ground": str(result.get("common_ground", "")),
            "differences": str(result.get("differences", "")), "model": model,
            "basis": "each outlet's headline and summary"}
