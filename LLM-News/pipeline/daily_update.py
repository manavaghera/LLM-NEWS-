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
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

from updates import edition_files, write_status

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "apps" / "static"
DEFAULT_BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


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
    if backend_url and added:
        warm(backend_url, f"/api/digest/daily/{date}")
        warm(backend_url, f"/api/digest/daily/{date}/audio")
    if email:
        emailer = ROOT / "pipeline" / "email_digest.py"
        subprocess.run([sys.executable, str(emailer), "--date", date, "--backend-url", backend_url], cwd=ROOT)
    return 0, added, date


def run_every(minutes: int, backend_url: str, news_args: list, once: bool) -> int:
    """Update now and then every `minutes` (counted from each start), recording each run for the website"""
    while True:
        started = datetime.now()
        code, added, date = run_once(backend_url, False, news_args, update=True)
        status = write_status(STATIC_DIR, date, minutes, added, ok=code == 0, now=started)
        print(f"  {added} new stories; next update at {status['next_update'][11:16]}")
        if once:
            return code
        time.sleep(max(0.0, (started + timedelta(minutes=minutes) - datetime.now()).total_seconds()))


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
