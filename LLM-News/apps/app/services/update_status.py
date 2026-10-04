"""When the news was last updated and when the next update is due, as written by
pipeline/daily_update.py --interval (static/update_status.json). The website shows it as a countdown."""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

NO_SCHEDULE = {"date": None, "last_update": None, "next_update": None, "interval_minutes": None, "added": 0}


def read_update_status(static_dir: Path = Path("static")) -> Dict:
    """The saved status, checked field by field; NO_SCHEDULE when no updater has run (or the file is broken)"""
    try:
        saved = json.loads((static_dir / "update_status.json").read_text(encoding="utf-8"))
        last, upcoming = datetime.fromisoformat(saved["last_update"]), datetime.fromisoformat(saved["next_update"])
        if last.tzinfo is None or upcoming.tzinfo is None:
            raise ValueError("times need a UTC offset")
        return {
            "date": str(saved.get("date") or ""),
            "last_update": last.isoformat(),
            "next_update": upcoming.isoformat(),
            "interval_minutes": int(saved["interval_minutes"]),
            "added": int(saved.get("added", 0)),
        }
    except (OSError, ValueError, KeyError, TypeError):
        return dict(NO_SCHEDULE)
