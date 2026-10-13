"""Wake the free backend and ask it to pull the latest signed news manifest."""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    origin = os.environ.get("BACKEND_ORIGIN", "").strip().rstrip("/")
    token = os.environ.get("STORAGE_SYNC_TOKEN", "").strip()
    if not origin.startswith("https://") or len(token) < 32:
        print("BACKEND_ORIGIN and a 32+ character STORAGE_SYNC_TOKEN are required", file=sys.stderr)
        return 2

    request = urllib.request.Request(
        f"{origin}/api/storage/sync",
        data=b"",
        method="POST",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "NewsSense-Updater/1.0"},
    )
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                print(response.read().decode("utf-8", errors="replace"))
                return 0
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"Sync attempt {attempt}/5 failed: {type(exc).__name__}")
            if attempt < 5:
                time.sleep(attempt * 5)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
