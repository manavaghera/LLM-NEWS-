"""Topic extraction for Trends: names and multi-word phrases ("Supreme Court", "UN"), not single words.

Pure functions, no NLP dependencies. Capitalised words at the start of a sentence are ambiguous
("Five men...", "Police said..."), so a lone one only counts when it also appears mid-sentence.
"""
import re
from typing import Dict, Iterable, Set

# A name token: Capitalised word (incl. inner capitals like MacArthur/OpenAI and hyphen/apostrophe parts),
# ACRONYM, or dotted acronym (U.S.)
UPPER, LOWER = "A-ZÀ-ÖØ-Þ", "a-zß-öø-ÿ"  # Latin letters incl. accents (González, Zürich)
NAME = (rf"(?:[{UPPER}][{LOWER}]+(?:[{UPPER}][{LOWER}]*)*(?:['’][{UPPER}][{LOWER}]+)?(?:-[{UPPER}][{LOWER}]+)*"
        rf"|[A-Z]{{2,5}}s?|(?:[A-Z]\.){{2,}})")
PHRASE = re.compile(rf"(?<![\w.]){NAME}(?:\s+(?:of\s+(?:the\s+)?)?{NAME}){{0,4}}(?![\w-])")  # up to 5-word names
SENTENCE_START = re.compile(r"(?:^\s*|[.!?:;]\s+|[\"“‘(]\s*)$")

# Capitalised words that are not topics
STOP = {
    "The", "A", "An", "In", "On", "At", "To", "For", "From", "By", "With", "Of", "And", "But", "Or",
    "This", "That", "These", "Those", "It", "Its", "He", "She", "They", "We", "His", "Her", "Their", "Our",
    "If", "As", "After", "Before", "While", "During", "Despite", "According", "Meanwhile", "However",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December", "New", "Mr", "Mrs", "Ms", "Dr", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten", "Some", "Many", "Several", "More", "Most", "Other", "Such", "Both",
}


def clean_text(text: str) -> str:
    """Drop citation markup and URLs (article text carries <a href='https://...'>[1]</a>)"""
    text = re.sub(r"<[^>]*>", " ", text or "")
    return re.sub(r"https?://\S+", " ", text)


def normalise(phrase: str) -> str:
    phrase = re.sub(r"['’]s$", "", phrase.strip())
    words = phrase.split()
    while words and words[0] in STOP:
        words.pop(0)
    while words and words[-1] in STOP:
        words.pop()
    if not words:
        return ""
    joined = " ".join(words)
    return joined.replace(".", "") if re.fullmatch(r"(?:[A-Z]\.){2,}", joined) else joined


def extract_topics(text: str) -> Set[str]:
    """Distinct topics mentioned in one piece of text"""
    text = clean_text(text)
    found: Set[str] = set()
    mid_sentence: Set[str] = set()
    of_at_start: Set[str] = set()  # "Shares of AMD" opening a sentence
    for match in PHRASE.finditer(text):
        topic = normalise(match.group(0))
        if not topic or len(topic) < 2:
            continue
        if not SENTENCE_START.search(text[:match.start()]):
            mid_sentence.add(topic)
        elif re.match(r"\S+\s+of\s", topic):
            of_at_start.add(topic)
        elif " " in topic or re.fullmatch(r"[A-Z]{2,5}s?", topic):
            found.add(topic)  # multi-word names and acronyms are unambiguous even at a sentence start
        # a lone capitalised word at a sentence start is only a name if it also appears mid-sentence
    for topic in of_at_start:
        tail = normalise(re.sub(r"^\S+\s+of\s+(?:the\s+)?", "", topic))
        found.add(topic if topic in mid_sentence else tail)
    return {t for t in found | mid_sentence if t}


def article_text(article: Dict) -> str:
    """Sentence-case text only: headlines and section titles are Title Case, which would make every word look like a name"""
    parts = [article.get("subheadline", ""), article.get("lead", "")]
    parts += [str(s.get("content", "")) for s in article.get("body", []) if isinstance(s, dict)]
    return ". ".join(p for p in parts if p)


def publisher_names(publisher_ids: Iterable[str]) -> Set[str]:
    """How publishers appear in text: "BBCNews" -> {"BBC News", "BBC"}, "TheGuardian" -> {"The Guardian", "Guardian"}"""
    names: Set[str] = set()
    for pid in publisher_ids:
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", str(pid)))
        words = spaced.split()
        names.add(spaced)
        if len(words) > 1 and words[0] == "The":
            names.add(" ".join(words[1:]))
        if len(words) > 1 and re.fullmatch(r"[A-Z]{2,5}", words[0]):
            names.add(words[0])
    return names


def article_topics(articles: Iterable[Dict]) -> Dict[str, int]:
    """How many of the articles mention each topic. The outlets that reported the stories ("according to
    BBC News") are sources, not topics, so they are left out."""
    articles = list(articles)
    outlets = publisher_names(
        p for a in articles for s in a.get("body", []) if isinstance(s, dict) for p in s.get("Publishers", []) or []
    )
    counts: Dict[str, int] = {}
    for article in articles:
        for topic in extract_topics(article_text(article)) - outlets:
            counts[topic] = counts.get(topic, 0) + 1
    return counts
