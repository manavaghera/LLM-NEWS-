"""Refresh the news: once, daily, or every N minutes. Afterwards the backend prepares the digest and
briefing audio so the first visitor doesn't wait. Optionally emails the digest (daily only).

    python pipeline/daily_update.py                       # once, now
    python pipeline/daily_update.py --every 07:00         # keep running, every day at 07:00
    python pipeline/daily_update.py --interval 60         # keep running, every hour: new stories only
    python pipeline/daily_update.py --interval 60 --once  # one hourly update (for Task Scheduler / cron)
    python pipeline/daily_update.py --email               # also send the digest email (see email_digest.py)
    python pipeline/daily_update.py --print-task          # show the Windows Task Scheduler command

With --interval the first run of a day writes the full edition; later runs add only stories about events
the edition doesn't cover yet (quick_news.py --update), and apps/static/update_status.json tells the
website when the next update is due. Any other options are passed to quick_news.py (e.g. --no-checks).
"""
import argparse
import os
import subprocess
import sys
import time
import socket
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Running ``python pipeline/daily_update.py`` puts only pipeline/ on sys.path.
    # Add the repository root so the documented cron/Task Scheduler command can
    # import the shared application services without requiring PYTHONPATH.
    sys.path.insert(0, str(ROOT))

from updates import edition_files, write_status
from apps.app.core.generation import acquire_update_lease, release_update_lease
from apps.app.core.object_storage import push as push_object_storage
from apps.app.core import jobs
from apps.app.core.monitoring import alert, configure_logging

STATIC_DIR = ROOT / "apps" / "static"
DEFAULT_BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
UPDATE_ALREADY_RUNNING = 75
enqueue = jobs.enqueue  # stable seam used by tests and small deployments


def report_manual_progress(**values) -> None:
    raw_job_id = os.getenv("NEWS_UPDATE_JOB_ID", "").strip()
    if not raw_job_id:
        return
    try:
        jobs.update_progress(int(raw_job_id), values)
    except Exception:
        return


def alert_failure(date: str) -> None:
    delivered = alert("updater", "update_failed",
                      f"NewsSense updater failed for {date}. The previous edition was preserved.")
    if delivered:
        print("  sent deduplicated failure alert")


def warm(backend_url: str, path: str) -> None:
    """Ask the backend for a page so it generates and saves it now"""
    try:
        with urllib.request.urlopen(backend_url.rstrip("/") + path, timeout=300) as response:
            print(f"  prepared {path} (HTTP {response.status})")
    except Exception as e:
        print(f"  could not prepare {path}: {e}")


def run_once(backend_url: str, email: bool, news_args: list, update: bool = False) -> Tuple[int, int, str]:
    """Write the news; with update, add to today's edition when it exists. Returns (exit code, new articles, date)."""
    date = datetime.now().strftime("%Y-%m-%d")
    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
    try:
        ttl = max(60, min(86_400, int(os.getenv("UPDATE_LOCK_SECONDS", "7200"))))
    except ValueError:
        ttl = 7200
    if not acquire_update_lease(owner, ttl):
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Another updater owns the generation lease; skipping this run")
        return UPDATE_ALREADY_RUNNING, 0, date
    try:
        return _run_once_locked(date, backend_url, email, news_args, update)
    finally:
        try:
            release_update_lease(owner)
        except Exception as exc:
            # The lease expires by itself. Do not turn a successfully published edition into a failed run
            # merely because operational storage was briefly unavailable during cleanup.
            print(f"  could not release updater lease immediately: {type(exc).__name__}")


def _run_once_locked(date: str, backend_url: str, email: bool, news_args: list,
                     update: bool = False) -> Tuple[int, int, str]:
    edition = STATIC_DIR / "articles" / date
    before = len(edition_files(edition))
    mode = ["--update"] if update and before else []
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] {'Looking for new stories' if mode else 'Writing the news'} for {date}")
    script = ROOT / "pipeline" / "quick_news.py"
    code = subprocess.run([sys.executable, str(script), "--date", date, *mode, *news_args], cwd=ROOT).returncode
    added = len(edition_files(edition)) - before
    if code != 0:
        print("The news script failed; nothing else was done.")
        return code, added, date
    try:
        uploaded = push_object_storage(STATIC_DIR)
        if uploaded:
            print(f"  persisted {uploaded} changed files to object storage")
    except Exception as exc:
        print(f"Object-storage publication failed: {type(exc).__name__}")
        return 74, added, date
    if backend_url and added:
        enqueue("warm_digest", {"date": date})
        enqueue("warm_audio", {"date": date})
        enqueue("deliver_notifications", {"date": date, "event": "edition_updated", "added": added})
    if email or (before == 0 and os.getenv("EMAIL_DIGEST_ENABLED", "").lower() == "true"):
        enqueue("email_digest", {"date": date})
    return 0, added, date


def run_every(minutes: int, backend_url: str, news_args: list, once: bool) -> int:
    """Update now, then wait `minutes` after completion before starting the next run."""
    while True:
        started = datetime.now()
        code, added, date = run_once(backend_url, False, news_args, update=True)
        if code == UPDATE_ALREADY_RUNNING:
            if once:
                return code if os.getenv("NEWS_UPDATE_JOB_ID") else 0
            time.sleep(max(0.0, (started + timedelta(minutes=minutes) - datetime.now()).total_seconds()))
            continue
        # A provider call can take longer than the requested interval. Record when publication
        # actually completed so a successful long run does not immediately look overdue.
        completed = datetime.now()
        status = write_status(STATIC_DIR, date, minutes, added, ok=code == 0, now=completed)
        print(f"  {added} new stories; next update at {status['next_update'][11:16]}")
        if code != 0:
            report_manual_progress(phase="failed", estimated_seconds_remaining=0)
            alert_failure(date)
        else:
            report_manual_progress(phase="completed", percent=100, estimated_seconds_remaining=0,
                                   category="", updated_at=completed.astimezone().isoformat(timespec="seconds"))
        if once:
            return code
        time.sleep(max(0.0, (completed + timedelta(minutes=minutes) - datetime.now()).total_seconds()))


def seconds_until(hh_mm: str) -> float:
    hour, minute = (int(part) for part in hh_mm.split(":"))
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def task_command(at: str, interval: int = 0) -> str:
    script = Path(__file__).resolve()
    if interval:
        name, argument = "NewsSense news updates", f'"{script}" --interval {interval} --once'
        trigger = f"New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes {interval})"
    else:
        name, argument = "NewsSense daily news", f'"{script}"'
        trigger = f"New-ScheduledTaskTrigger -Daily -At {at}"
    return (f'Register-ScheduledTask -TaskName "{name}" -Trigger ({trigger}) '
            f"-Action (New-ScheduledTaskAction -Execute '{sys.executable}' -Argument '{argument}' "
            f"-WorkingDirectory '{ROOT}')")


def main():
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    when = parser.add_mutually_exclusive_group()
    when.add_argument("--every", metavar="HH:MM", help="keep running and refresh every day at this time")
    when.add_argument("--interval", type=int, metavar="MINUTES", help="keep running and add new stories every N minutes")
    parser.add_argument("--once", action="store_true", help="with --interval: one update, then exit")
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND, help=f"running backend (default {DEFAULT_BACKEND}); '' to skip")
    parser.add_argument("--email", action="store_true", help="email the digest afterwards (not with --interval)")
    parser.add_argument("--print-task", action="store_true", help="print the Windows Task Scheduler command and exit")
    args, news_args = parser.parse_known_args()

    if args.interval is not None and not 10 <= args.interval <= 24 * 60:
        sys.exit("--interval must be between 10 and 1440 minutes")
    if args.interval and args.email:
        sys.exit("--email sends the daily digest; use it with --every, not --interval")
    if args.print_task:
        print(task_command(args.every or "07:00", args.interval or 0))
        return
    if args.interval:
        sys.exit(run_every(args.interval, args.backend_url, news_args, args.once))
    if not args.every:
        sys.exit(run_once(args.backend_url, args.email, news_args)[0])
    seconds_until(args.every)  # validate HH:MM before looping
    while True:
        wait = seconds_until(args.every)
        print(f"Next refresh at {args.every} (in {wait / 3600:.1f} hours)")
        time.sleep(wait)
        run_once(args.backend_url, args.email, news_args)


if __name__ == "__main__":
    main()
