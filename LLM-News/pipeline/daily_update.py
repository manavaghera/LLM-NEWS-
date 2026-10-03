"""Daily refresh: write today's news, then have the backend prepare the digest and briefing audio
so the first visitor doesn't wait. Optionally emails the digest.

    python pipeline/daily_update.py                  # once, now
    python pipeline/daily_update.py --every 07:00    # keep running, every day at 07:00
    python pipeline/daily_update.py --email          # also send the digest email (see email_digest.py)
    python pipeline/daily_update.py --print-task     # show the Windows Task Scheduler command

Any other options are passed to quick_news.py (e.g. --no-checks, --per-category 4).
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def warm(backend_url: str, path: str) -> None:
    """Ask the backend for a page so it generates and saves it now"""
    try:
        with urllib.request.urlopen(backend_url.rstrip("/") + path, timeout=300) as response:
            print(f"  prepared {path} (HTTP {response.status})")
    except Exception as e:
        print(f"  could not prepare {path}: {e}")


def run_once(backend_url: str, email: bool, news_args: list) -> int:
    date = datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] Writing the news for {date}")
    script = ROOT / "pipeline" / "quick_news.py"
    if subprocess.run([sys.executable, str(script), "--date", date, *news_args], cwd=ROOT).returncode != 0:
        print("The news script failed; nothing else was done.")
        return 1
    if backend_url:
        warm(backend_url, f"/api/digest/daily/{date}")
        warm(backend_url, f"/api/digest/daily/{date}/audio")
    if email:
        emailer = ROOT / "pipeline" / "email_digest.py"
        subprocess.run([sys.executable, str(emailer), "--date", date, "--backend-url", backend_url], cwd=ROOT)
    return 0


def seconds_until(hh_mm: str) -> float:
    hour, minute = (int(part) for part in hh_mm.split(":"))
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def task_command(at: str) -> str:
    return (f'Register-ScheduledTask -TaskName "NewsSense daily news" '
            f'-Trigger (New-ScheduledTaskTrigger -Daily -At {at}) '
            f"-Action (New-ScheduledTaskAction -Execute '{sys.executable}' -Argument '\"{Path(__file__).resolve()}\"' "
            f"-WorkingDirectory '{ROOT}')")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--every", metavar="HH:MM", help="keep running and refresh every day at this time")
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND, help=f"running backend (default {DEFAULT_BACKEND}); '' to skip")
    parser.add_argument("--email", action="store_true", help="email the digest afterwards")
    parser.add_argument("--print-task", action="store_true", help="print the Windows Task Scheduler command and exit")
    args, news_args = parser.parse_known_args()

    if args.print_task:
        print(task_command(args.every or "07:00"))
        return
    if not args.every:
        sys.exit(run_once(args.backend_url, args.email, news_args))
    seconds_until(args.every)  # validate HH:MM before looping
    while True:
        wait = seconds_until(args.every)
        print(f"Next refresh at {args.every} (in {wait / 3600:.1f} hours)")
        time.sleep(wait)
        run_once(args.backend_url, args.email, news_args)


if __name__ == "__main__":
    main()
