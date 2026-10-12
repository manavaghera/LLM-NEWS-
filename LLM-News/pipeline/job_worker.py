"""Process durable digest, audio, email and notification jobs."""
import os
import subprocess
import sys
import time
import urllib.request
import json
from pathlib import Path

from apps.app.core import jobs
from apps.app.core.monitoring import alert, configure_logging
from apps.app.core.notifications import deliver as deliver_push


ROOT = Path(__file__).resolve().parents[1]
BACKEND = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")


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
    if job["kind"] == "warm_digest":
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
            print(f"job {job['id']} ({job['kind']}) failed: {type(exc).__name__}", flush=True)
            if jobs.fail(job["id"], exc):
                alert("worker", f"{job['kind']}_failed",
                      f"NewsSense background job {job['kind']} exhausted its retries.")
        else:
            jobs.complete(job["id"])


if __name__ == "__main__":
    main()
