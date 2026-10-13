"""Hourly updates (no network, no AI). Run from LLM-News: python -m pytest tests"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import daily_update  # noqa: E402
from updates import covered_texts, drop_covered_events, write_status  # noqa: E402


def test_documented_updater_command_imports_without_pythonpath():
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(root / "pipeline" / "daily_update.py"), "--help"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


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


def test_a_failed_update_keeps_the_last_update_time(tmp_path):
    first = datetime(2026, 10, 4, 14, 5, tzinfo=timezone.utc)
    write_status(tmp_path, "2026-10-04", 60, added=2, ok=True, now=first)
    failed = write_status(tmp_path, "2026-10-04", 60, added=0, ok=False, now=first + timedelta(hours=1))
    assert datetime.fromisoformat(failed["last_update"]) == first          # the site keeps saying "Updated 14:05"
    assert datetime.fromisoformat(failed["next_update"]) == first + timedelta(hours=2) and not failed["ok"]
    partly = write_status(tmp_path, "2026-10-04", 60, added=1, ok=False, now=first + timedelta(hours=2))
    assert datetime.fromisoformat(partly["last_update"]) == first + timedelta(hours=2)  # stories changed: it did update


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


def test_hourly_status_uses_publication_completion_time(tmp_path, monkeypatch):
    started = datetime(2026, 10, 13, 1, 0, tzinfo=timezone.utc)
    completed = started + timedelta(minutes=102)
    times = iter((started, completed))

    monkeypatch.setattr(daily_update, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(daily_update, "datetime", SimpleNamespace(now=lambda: next(times)))
    monkeypatch.setattr(
        daily_update, "run_once", lambda *args, **kwargs: (0, 29, "2026-10-13")
    )

    assert daily_update.run_every(60, "", [], once=True) == 0
    status = json.loads((tmp_path / "update_status.json").read_text(encoding="utf-8"))
    assert datetime.fromisoformat(status["last_update"]) == completed
    assert datetime.fromisoformat(status["next_update"]) == completed + timedelta(hours=1)


def test_overlapping_hourly_run_does_not_change_status_or_start_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_update, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(daily_update, "acquire_update_lease", lambda owner, ttl: False)
    monkeypatch.setattr(daily_update.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not generate"))
    assert daily_update.run_every(60, "", [], once=True) == 0
    assert not (tmp_path / "update_status.json").exists()


def test_lease_cleanup_failure_does_not_hide_a_successful_update(monkeypatch):
    monkeypatch.setattr(daily_update, "acquire_update_lease", lambda owner, ttl: True)
    monkeypatch.setattr(daily_update, "_run_once_locked", lambda *args, **kwargs: (0, 2, "2026-10-11"))

    def fail_to_release(owner):
        raise OSError("operations database temporarily unavailable")

    monkeypatch.setattr(daily_update, "release_update_lease", fail_to_release)
    assert daily_update.run_once("", False, []) == (0, 2, "2026-10-11")


def test_scheduled_task_for_hourly_updates():
    command = daily_update.task_command("07:00", interval=60)
    assert "-RepetitionInterval (New-TimeSpan -Minutes 60)" in command
    assert "--interval 60 --once'" in command


def test_first_cloud_edition_queues_enabled_email_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_update, "STATIC_DIR", tmp_path)
    monkeypatch.setenv("EMAIL_DIGEST_ENABLED", "true")
    queued = []

    def generate(*_args, **_kwargs):
        edition = tmp_path / "articles" / "2026-10-12"
        edition.mkdir(parents=True)
        (edition / "group_1.json").write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(daily_update.subprocess, "run", generate)
    monkeypatch.setattr(daily_update, "push_object_storage", lambda _: 0)
    monkeypatch.setattr(daily_update, "enqueue", lambda kind, payload: queued.append((kind, payload)))
    assert daily_update._run_once_locked("2026-10-12", "", False, []) == (0, 1, "2026-10-12")
    assert queued == [("email_digest", {"date": "2026-10-12"})]
