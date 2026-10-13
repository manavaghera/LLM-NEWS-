"""When the news was last updated and when the next update is due, as written by
pipeline/daily_update.py --interval (static/update_status.json). The website shows it as a countdown."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

NO_SCHEDULE = {"date": None, "last_update": None, "next_update": None, "interval_minutes": None,
               "added": 0, "ok": None, "stale": True, "minutes_since_update": None}


def read_update_status(static_dir: Path = Path("static"), now: datetime | None = None) -> Dict:
    """The saved status, checked field by field; NO_SCHEDULE when no updater has run (or the file is broken)"""
    try:
        saved = json.loads((static_dir / "update_status.json").read_text(encoding="utf-8"))
        last, upcoming = datetime.fromisoformat(saved["last_update"]), datetime.fromisoformat(saved["next_update"])
        if last.tzinfo is None or upcoming.tzinfo is None:
            raise ValueError("times need a UTC offset")
        interval = max(1, int(saved["interval_minutes"]))
        current = now or datetime.now(timezone.utc)
        stale_after = max(interval * 2, int(os.getenv("STALE_AFTER_MINUTES", str(interval * 2))))
        age_minutes = max(0, int((current - last.astimezone(timezone.utc)).total_seconds() // 60))
        return {
            "date": str(saved.get("date") or ""),
            "last_update": last.isoformat(),
            "next_update": upcoming.isoformat(),
            "interval_minutes": interval,
            "added": int(saved.get("added", 0)),
            "ok": saved.get("ok") if isinstance(saved.get("ok"), bool) else None,
            "stale": age_minutes > stale_after,
            "minutes_since_update": age_minutes,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return dict(NO_SCHEDULE)
