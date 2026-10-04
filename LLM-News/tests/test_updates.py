"""Hourly updates (no network, no AI). Run from LLM-News: python -m pytest tests"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import daily_update  # noqa: E402
from updates import covered_texts, drop_covered_events, write_status  # noqa: E402


def item(title, summary, link="https://example.com/x"):
    return {"title": title, "summary": summary, "link": link}


def write(folder: Path, name: str, data):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


def test_covered_texts_reads_sources_and_falls_back_to_headline(tmp_path):
    write(tmp_path, "group_1.json", {"source_items": [{"title": "G7 to release oil", "summary": "100 million barrels"}]})
    write(tmp_path, "group_2.json", {"headline": "Chip launch", "lead": "A faster processor."})
    write(tmp_path, "group_categories.json", {"group_1": "social"})
    assert covered_texts(tmp_path) == ["G7 to release oil 100 million barrels", "Chip launch A faster processor."]


def test_new_links_about_a_covered_event_are_dropped():
    covered = ["G7 agrees to release 100 million barrels of oil reserves to ease diesel prices"]
    follow_up = item("G7 oil reserve release begins", "The G7 started releasing oil reserves and diesel", "https://b/1")
    other = item("Storm hits Florida coast", "Hurricane winds knock out power for thousands", "https://b/2")
    kept, dropped = drop_covered_events([follow_up, other], covered, threshold=0.2)
    assert kept == [other] and dropped == 1
    assert drop_covered_events([other], [], 0.2) == ([other], 0)  # nothing covered yet: keep everything


def test_status_says_when_the_next_update_is_due(tmp_path):
    now = datetime(2026, 10, 4, 14, 5, tzinfo=timezone.utc)
    status = write_status(tmp_path, "2026-10-04", 60, added=2, ok=True, now=now)
    saved = json.loads((tmp_path / "update_status.json").read_text(encoding="utf-8"))
    assert saved == status
    # local time with its UTC offset (19:35+05:30 is 14:05 UTC), so browsers anywhere read it right
    assert datetime.fromisoformat(saved["last_update"]) == now
    assert datetime.fromisoformat(saved["next_update"]) == now + timedelta(hours=1)
    assert not list(tmp_path.glob("*.part"))


def test_hourly_run_writes_the_edition_first_then_only_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_update, "STATIC_DIR", tmp_path)
    edition = tmp_path / "articles" / datetime.now().strftime("%Y-%m-%d")
    calls = []

    def fake_news_script(command, cwd):
        calls.append(command)
        write(edition, f"group_{len(list(edition.glob('group_*.json'))) + 1}.json", {})  # one new story per run
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(daily_update.subprocess, "run", fake_news_script)
    assert daily_update.run_every(60, "", [], once=True) == 0
    assert daily_update.run_every(60, "", ["--no-audio"], once=True) == 0
    assert "--update" not in calls[0]                      # no edition yet: the full edition
    assert calls[1][-2:] == ["--update", "--no-audio"]    # then new stories only
    status = json.loads((tmp_path / "update_status.json").read_text(encoding="utf-8"))
    assert status["added"] == 1 and status["ok"] and status["interval_minutes"] == 60


def test_scheduled_task_for_hourly_updates():
    command = daily_update.task_command("07:00", interval=60)
    assert "-RepetitionInterval (New-TimeSpan -Minutes 60)" in command
    assert "--interval 60 --once'" in command
