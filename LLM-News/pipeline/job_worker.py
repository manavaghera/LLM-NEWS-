"""Process durable digest, audio, email and notification jobs."""
import os
import subprocess
import sys
import time
import urllib.request
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Direct script execution puts pipeline/ on sys.path, not the repository root.
    sys.path.insert(0, str(ROOT))

from apps.app.core import jobs
from apps.app.core.monitoring import alert, configure_logging
from apps.app.core.notifications import deliver as deliver_push


BACKEND = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")


def run_news_update(job: dict) -> None:
    """Run the normal updater while keeping the durable job lease alive."""
    command = [
        sys.executable, str(ROOT / "pipeline" / "daily_update.py"),
        "--interval", os.getenv("UPDATE_MINUTES", "60"), "--once",
    ]
    fast = os.getenv("MANUAL_UPDATE_MODE", "fast").strip().lower() != "full"
    if fast:
        # The button is for a quick breaking-news refresh. The scheduled updater
        # still performs the full multi-category, full-text, verified edition.
        command.extend([
            "--categories", os.getenv("MANUAL_UPDATE_CATEGORIES", "ai_models"),
            "--per-category", os.getenv("MANUAL_UPDATE_PER_CATEGORY", "1"),
            "--per-feed", os.getenv("MANUAL_UPDATE_PER_FEED", "3"),
            "--no-full-text", "--no-images", "--no-audio", "--no-checks", "--source-briefs",
        ])
    elif os.getenv("MANUAL_UPDATE_AUDIO", "false").lower() != "true":
        command.append("--no-audio")
    environment = os.environ.copy()
    environment["NEWS_UPDATE_JOB_ID"] = str(job["id"])
    if fast:
        environment.setdefault("UPDATE_ESTIMATE_SECONDS_PER_CATEGORY", "150")
    jobs.update_progress(job["id"], {"phase": "starting", "percent": 1})
    process = subprocess.Popen(command, cwd=ROOT, env=environment)
    timeout = max(600, int(os.getenv("NEWS_UPDATE_TIMEOUT_SECONDS", "21600")))
    heartbeat_seconds = max(2, int(os.getenv("JOB_HEARTBEAT_SECONDS", "5")))
    started = time.monotonic()
    while process.poll() is None:
        if time.monotonic() - started > timeout:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
            raise TimeoutError("News update exceeded its time limit")
        try:
            jobs.heartbeat(job["id"])
        except Exception:
            print(f"job {job['id']} heartbeat temporarily unavailable", flush=True)
        time.sleep(heartbeat_seconds)
    if process.returncode:
        raise RuntimeError("News update command failed")


def request(path: str) -> None:
    with urllib.request.urlopen(BACKEND + path, timeout=300) as response:
        if response.status >= 400:
            raise RuntimeError(f"Backend returned HTTP {response.status}")


def fetch(path: str):
    with urllib.request.urlopen(BACKEND + path, timeout=300) as response:
        return json.load(response)


def execute(job: dict) -> None:
    payload = job["payload"]
    date = str(payload.get("date", ""))
    if job["kind"] == "news_update":
        run_news_update(job)
    elif job["kind"] == "warm_digest":
        request(f"/api/digest/daily/{date}")
    elif job["kind"] == "warm_audio":
        request(f"/api/digest/daily/{date}/audio")
    elif job["kind"] == "email_digest":
        result = subprocess.run(
            [sys.executable, str(ROOT / "pipeline" / "email_digest.py"), "--date", date,
             "--backend-url", BACKEND], cwd=ROOT, timeout=600,
        )
        if result.returncode:
            raise RuntimeError("Email digest command failed")
    elif job["kind"] == "deliver_notifications":
        date = str(payload.get("date", ""))
        articles = fetch(f"/api/news?date={date}") if date else []
        deliver_push(articles)
        # An external provider can consume the same durable event when configured.
        endpoint = os.getenv("NOTIFICATION_DELIVERY_WEBHOOK", "").strip()
        if endpoint:
            body = __import__("json").dumps(payload).encode()
            req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30):
                pass


def main() -> None:
    configure_logging()
    interval = max(1, int(os.getenv("JOB_POLL_SECONDS", "5")))
    while True:
        job = jobs.claim()
        if not job:
            time.sleep(interval)
            continue
        try:
            execute(job)
        except Exception as exc:
            if job["kind"] == "news_update":
                jobs.update_progress(job["id"], {"phase": "failed", "estimated_seconds_remaining": 0})
            print(f"job {job['id']} ({job['kind']}) failed: {type(exc).__name__}", flush=True)
            if jobs.fail(job["id"], exc):
                alert("worker", f"{job['kind']}_failed",
                      f"NewsSense background job {job['kind']} exhausted its retries.")
        else:
            jobs.complete(job["id"])


if __name__ == "__main__":
    main()
