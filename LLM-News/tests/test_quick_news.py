"""Unit tests for pipeline/quick_news.py (no network or LLM calls). Run from LLM-News: python -m pytest tests"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import media  # noqa: E402
import quick_news as q  # noqa: E402


def item(title, summary="", publisher="BBCNews", region="uk", image="", n=0):
    return {"publisher": publisher, "region": region, "title": title, "summary": summary,
            "link": f"https://example.com/{publisher}/{n}", "image": image, "published": "2026-09-30"}


def test_group_items_joins_same_event_only():
    items = [
        item("UN extends Haiti gang suppression force mandate", "Security Council vote on Haiti force", n=1),
        item("Pop star surprises fans at Paris fashion week", "Singer appears on the runway", n=2),
        item("Security Council extends mandate of anti-gang force in Haiti", "UN vote keeps Haiti force", "CBCNews", "ca", n=3),
        item("New smartphone chip announced", "Chipmaker reveals processor", n=4),
    ]
    stories = q.group_items(items, threshold=0.2)
    assert sorted(stories["S1"]) == [1, 3]  # the Haiti items, largest story first
    assert all(len(numbers) == 1 for sid, numbers in stories.items() if sid != "S1")


def test_group_items_caps_story_size():
    items = [item("Election results announced tonight", "Final election results", n=i) for i in range(7)]
    stories = q.group_items(items, threshold=0.2)
    assert max(len(numbers) for numbers in stories.values()) <= q.MAX_STORY_ITEMS
    assert sorted(n for numbers in stories.values() for n in numbers) == list(range(1, 8))


def test_build_article_cites_only_its_own_story():
    items = [item("A", n=1), item("B", n=2), item("C", "", "NPR", "us", n=3)]
    draft = {
        "headline": "Headline",
        "body": [
            {"section": "One", "content": "Uses items 1 and 3.", "item_ids": [1, 3], "sentiment": 3},
            {"section": "Two", "content": "Only cites another story.", "item_ids": [3]},
        ],
    }
    article = q.build_article(draft, items, allowed={1, 2}, category="social", date="2026-09-30")
    assert [s["section"] for s in article["body"]] == ["One"]  # section two had no allowed source
    section = article["body"][0]
    assert section["sources"] == ["https://example.com/BBCNews/1"]
    assert section["content"].endswith("<a href='https://example.com/BBCNews/1'>[1]</a>")
    assert section["sentisement_from_the_content"] == 1.0  # clamped to [-1, 1]
    assert "fake_news_probability" not in section  # never invented


def test_build_article_needs_a_sourced_section():
    draft = {"headline": "Nothing sourced", "body": [{"section": "X", "content": "Y", "item_ids": [99]}]}
    assert q.build_article(draft, [item("A", n=1)], allowed={1}, category="tech", date="2026-09-30") is None


def test_resolve_story_falls_back_to_first_cited_item():
    stories = {"S1": [2], "S2": [1, 3]}
    assert q.resolve_story({"story_id": "s1"}, stories, 3) == "S1"
    assert q.resolve_story({"story_id": "S9", "body": [{"item_ids": ["3"]}]}, stories, 3) == "S2"
    assert q.resolve_story({"body": [{"item_ids": [42]}]}, stories, 3) is None


def test_best_image_skips_tracking_pixels_and_upsizes_bbc():
    npr = {"summary": "<img src='https://media.npr.org/include/images/tracking/npr-rss-pixel.png' />"
                      "<img src='undefined'/><img src='https://npr.brightspotcdn.com/photo.jpg'/>"}
    assert media.best_image(npr) == "https://npr.brightspotcdn.com/photo.jpg"
    bbc = {"media_thumbnail": [{"url": "https://ichef.bbci.co.uk/ace/standard/240/x.jpg", "width": "240"}]}
    assert media.best_image(bbc) == "https://ichef.bbci.co.uk/ace/standard/976/x.jpg"
    guardian = {"media_content": [{"url": "https://i.guim.co.uk/small", "width": "140"},
                                  {"url": "https://i.guim.co.uk/large", "width": "700"}]}
    assert media.best_image(guardian) == "https://i.guim.co.uk/large"


def test_download_image_rejects_non_web_urls(tmp_path):
    assert media.download_image("file:///etc/passwd", tmp_path, "group_1") == ""
    assert list(tmp_path.iterdir()) == []


def test_download_image_keeps_the_real_format(tmp_path, monkeypatch):
    class Response:
        headers = type("H", (), {"get_content_type": staticmethod(lambda: "image/webp")})()
        def read(self, n): return b"x" * 4096
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(media.urllib.request, "urlopen", lambda req, timeout: Response())
    assert media.download_image("https://img.example/a", tmp_path, "group_2") == "group_2.webp"
    assert (tmp_path / "group_2.webp").stat().st_size == 4096


def test_clean_text_strips_html_and_truncates():
    assert q.clean_text("<p>Hello &amp; <b>welcome</b></p>") == "Hello & welcome"
    assert q.clean_text("word " * 200, limit=20).endswith("...")


def test_make_thumbnail_is_a_small_webp(tmp_path):
    from PIL import Image
    big = tmp_path / "group_1.png"
    Image.new("RGB", (2000, 1200), (200, 30, 30)).save(big)
    assert media.make_thumbnail(big) == "group_1.thumb.webp"
    with Image.open(tmp_path / "group_1.thumb.webp") as thumb:
        assert thumb.format == "WEBP" and thumb.size == (800, 480)
    (tmp_path / "broken.jpg").write_bytes(b"not an image")
    assert media.make_thumbnail(tmp_path / "broken.jpg") == ""


def test_articles_without_a_finished_fact_check_are_held_back():
    checked = {"claim_check": {"checked": True, "removed": []}, "body": [{"content": "Supported."}]}
    assert q.held_back(checked) == ""
    assert q.held_back({"body": [{"content": "Never checked."}]}).startswith("held back")  # the check call failed
    assert q.held_back({**checked, "body": []}).startswith("dropped")                     # nothing was supported
