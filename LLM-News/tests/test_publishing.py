"""Publication keeps the live edition intact until generation and all replacements succeed."""
import json
import sys
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import publishing
import quick_news as q
from apps.app.core import generation

DATE = "2026-10-09"


def seed(root):
    targets = [root / kind / DATE for kind in ("articles", "images", "audio")]
    for target in targets:
        target.mkdir(parents=True)
    (targets[0] / "group_1.json").write_text(json.dumps({"headline": "Original edition", "body": []}))
    (targets[0] / "group_categories.json").write_text(json.dumps({"group_1": "tech"}))
    (targets[1] / "group_1.jpg").write_bytes(b"original image")
    (targets[2] / "group_1.mp3").write_bytes(b"original audio")
    return targets


def contents(targets):
    return [{p.name: p.read_bytes() for p in target.iterdir()} for target in targets]


def test_generation_exception_leaves_live_article_and_media_untouched(tmp_path):
    targets = seed(tmp_path)
    original = contents(targets)
    with pytest.raises(RuntimeError):
        with publishing.EditionWriter(*targets) as edition:
            (edition.articles / "group_1.json").write_text("new draft")
            assert contents(targets) == original
            raise RuntimeError("provider failed")
    assert contents(targets) == original
    assert not list(targets[0].parent.glob(".edition-*"))


def test_media_and_articles_are_replaced_only_on_commit(tmp_path):
    targets = seed(tmp_path)
    with publishing.EditionWriter(*targets) as edition:
        for name in ("articles", "images", "audio"):
            (getattr(edition, name) / "replacement").write_text(name)
        edition.commit()
    assert [list(folder.iterdir())[0].read_text() for folder in targets] == ["articles", "images", "audio"]


def test_last_replacement_failure_rolls_back_articles_and_media(tmp_path, monkeypatch):
    targets = seed(tmp_path)
    original = contents(targets)
    replace = publishing.os.replace
    with publishing.EditionWriter(*targets) as edition:
        def fail_last(source, target):
            if Path(source) == edition.articles:
                raise OSError("simulated failure installing articles")
            replace(source, target)
        monkeypatch.setattr(publishing.os, "replace", fail_last)
        with pytest.raises(OSError):
            edition.commit()
        assert contents(targets) == original
    assert contents(targets) == original


def test_append_preserves_existing_articles_and_media(tmp_path):
    targets = seed(tmp_path)
    original = contents(targets)
    with publishing.EditionWriter(*targets, append=True) as edition:
        (edition.articles / "group_2.json").write_text("new article")
        edition.commit()
    assert (targets[0] / "group_2.json").read_text() == "new article"
    for old, folder in zip(original, targets):
        assert all((folder / name).read_bytes() == value for name, value in old.items())


def test_concurrent_changes_are_not_overwritten(tmp_path):
    targets = seed(tmp_path)
    with publishing.EditionWriter(*targets) as edition:
        (targets[0] / "group_2.json").write_text("newer publisher's article")
        with pytest.raises(RuntimeError, match="edition changed"):
            edition.commit()
    assert (targets[0] / "group_2.json").read_text() == "newer publisher's article"


def test_overlapping_append_commits_reject_stale_snapshot(tmp_path, monkeypatch):
    targets = seed(tmp_path)
    first_checked, second_checked = threading.Event(), threading.Event()
    original_signature = publishing.signature
    failures = {}

    def signature(folder):
        saved = original_signature(folder)
        if folder == targets[0].resolve():
            if threading.current_thread().name == "first-publication":
                first_checked.set()
                # Without a publication lock both commits inspect the same old article directory.
                # With the lock the second check waits until the first publication is installed.
                second_checked.wait(0.2)
            elif threading.current_thread().name == "second-publication":
                second_checked.set()
        return saved

    monkeypatch.setattr(publishing, "signature", signature)
    with publishing.EditionWriter(*targets, append=True) as first, publishing.EditionWriter(*targets, append=True) as second:
        (first.articles / "group_2.json").write_text("first update")
        (second.articles / "group_3.json").write_text("stale overlapping update")

        def commit(writer, name):
            try:
                writer.commit()
            except BaseException as exc:
                failures[name] = exc

        threads = [threading.Thread(target=commit, args=(first, "first"), name="first-publication"),
                   threading.Thread(target=commit, args=(second, "second"), name="second-publication")]
        threads[0].start()
        assert first_checked.wait(5)
        threads[1].start()
        for thread in threads:
            thread.join(15)
            assert not thread.is_alive()

        assert "first" not in failures
        assert isinstance(failures.get("second"), RuntimeError)
        assert "edition changed" in str(failures["second"])

    assert (targets[0] / "group_2.json").read_text() == "first update"
    assert not (targets[0] / "group_3.json").exists()
    assert (targets[1] / "group_1.jpg").read_bytes() == b"original image"
    assert (targets[2] / "group_1.mp3").read_bytes() == b"original audio"


@pytest.fixture
def writer(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    targets = seed(tmp_path / "static")
    for kind, target in zip(("ARTICLES_DIR", "IMAGES_DIR", "AUDIO_DIR"), targets):
        monkeypatch.setattr(q, kind, target.parent)
    monkeypatch.setattr(q, "fetch_items", Mock(return_value=[]))
    monkeypatch.setattr(sys, "argv", ["quick_news.py", "--date", DATE, "--overwrite", "--categories", "tech",
                                    "--no-images", "--no-audio", "--no-full-text"])
    return targets


def fake_item():
    return {"title": "Council extends mission", "summary": "The mandate runs six months.",
            "publisher": "Outlet", "region": "us", "link": "https://example.com/mission", "image": "",
            "published": DATE, "text_basis": "summary"}


def fake_draft():
    return {"story_id": "S1", "headline": "Council extends mission",
            "body": [{"section": "Vote", "content": "The mandate runs six months.", "item_ids": [1]}]}


def test_empty_feeds_cannot_erase_the_published_edition(writer):
    original = contents(writer)
    with pytest.raises(SystemExit):
        q.main()
    assert contents(writer) == original
    assert generation.recent_runs()[0]["status"] == "failed"


def test_total_feed_outage_fails_an_append_instead_of_reporting_success(writer, monkeypatch):
    original = contents(writer)
    monkeypatch.setattr(q, "fetch_items", Mock(return_value=q.FeedItems([], attempted_feeds=4, successful_feeds=0)))
    monkeypatch.setattr(sys, "argv", ["quick_news.py", "--date", DATE, "--update", "--categories", "tech",
                                     "--no-images", "--no-audio", "--no-full-text"])
    with pytest.raises(SystemExit, match="News generation failed"):
        q.main()
    assert contents(writer) == original
    assert generation.recent_runs()[0]["status"] == "failed"


def test_one_failed_category_does_not_discard_other_categories(writer, monkeypatch):
    monkeypatch.setattr(q, "fetch_items", Mock(side_effect=[
        q.FeedItems([], attempted_feeds=2, successful_feeds=0),
        q.FeedItems([fake_item()], attempted_feeds=2, successful_feeds=1),
    ]))
    monkeypatch.setattr(q, "write_articles", Mock(return_value=[fake_draft()]))
    monkeypatch.setattr(q, "enrich", lambda article, cited: article.update(claim_check={"checked": True}) or [])
    monkeypatch.setattr(sys, "argv", ["quick_news.py", "--date", DATE, "--update",
                                     "--categories", "tech,entertainment",
                                     "--no-images", "--no-audio", "--no-full-text"])
    q.main()
    assert (writer[0] / "group_2.json").exists()
    assert generation.recent_runs()[0]["status"] == "success"


def test_failed_model_cannot_erase_the_published_edition(writer, monkeypatch):
    original = contents(writer)
    monkeypatch.setattr(q, "fetch_items", Mock(return_value=[fake_item()]))
    monkeypatch.setattr(q, "write_articles", Mock(side_effect=RuntimeError("provider unavailable")))
    with pytest.raises(SystemExit):
        q.main()
    assert contents(writer) == original


def test_successful_overwrite_publishes_checked_replacement(writer, monkeypatch):
    monkeypatch.setattr(q, "fetch_items", Mock(return_value=[fake_item()]))
    monkeypatch.setattr(q, "write_articles", Mock(return_value=[fake_draft()]))
    def check(article, cited):
        article["claim_check"] = {"checked": True, "removed": []}
        return []
    monkeypatch.setattr(q, "enrich", check)
    q.main()
    assert json.loads((writer[0] / "group_1.json").read_text())["headline"] == "Council extends mission"
    assert json.loads((writer[0] / "group_categories.json").read_text()) == {"group_1": "tech"}
    assert not list(writer[1].iterdir()) and not list(writer[2].iterdir())
    assert generation.recent_runs()[0]["added"] == 1


def test_verified_update_replaces_pending_brief_in_place(writer, monkeypatch):
    pending = {
        "headline": "Pending brief", "verification_status": "source_brief",
        "body": [{"content": "Pending", "sources": ["https://example.com/mission"]}],
        "source_items": [{"title": "Council extends mission", "summary": "The mandate runs six months."}],
    }
    (writer[0] / "group_1.json").write_text(json.dumps(pending), encoding="utf-8")
    monkeypatch.setattr(q, "fetch_items", Mock(return_value=[fake_item()]))
    monkeypatch.setattr(q, "write_articles", Mock(return_value=[fake_draft()]))

    def check(article, cited):
        article["claim_check"] = {"checked": True, "removed": [], "evidence": []}
        return []

    monkeypatch.setattr(q, "enrich", check)
    monkeypatch.setattr(sys, "argv", ["quick_news.py", "--date", DATE, "--update", "--categories", "tech",
                                     "--no-images", "--no-audio", "--no-full-text"])
    q.main()
    saved = json.loads((writer[0] / "group_1.json").read_text())
    assert saved["headline"] == "Council extends mission"
    assert saved["verification_status"] == "verified"
    assert not (writer[0] / "group_2.json").exists()


def test_rejected_replacement_keeps_original_and_records_held_back(writer, monkeypatch):
    original = contents(writer)
    monkeypatch.setattr(q, "fetch_items", Mock(return_value=[fake_item()]))
    monkeypatch.setattr(q, "write_articles", Mock(return_value=[fake_draft()]))
    monkeypatch.setattr(q, "enrich", Mock(return_value=["check failed"]))
    with pytest.raises(SystemExit):
        q.main()
    assert contents(writer) == original
    assert generation.recent_runs()[0]["held_back"] == 1
    assert generation.held_stories()[0]["headline"] == "Council extends mission"
    assert "fact-check failed" in generation.held_stories()[0]["reason"]


def test_partial_category_replacement_is_not_published(writer, monkeypatch):
    original = contents(writer)
    sys.argv.extend(["--categories", "tech,entertainment"])
    monkeypatch.setattr(q, "fetch_items", Mock(side_effect=[[fake_item()], []]))
    monkeypatch.setattr(q, "write_articles", Mock(return_value=[fake_draft()]))
    monkeypatch.setattr(q, "enrich", lambda article, cited: article.update(claim_check={"checked": True}) or [])
    with pytest.raises(SystemExit):
        q.main()
    assert contents(writer) == original
