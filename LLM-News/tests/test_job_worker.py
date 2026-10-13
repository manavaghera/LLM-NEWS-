"""Manual update worker behavior without running the network or AI pipeline."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import job_worker  # noqa: E402


def test_manual_update_runs_once_and_keeps_job_alive(monkeypatch):
    saved = {"command": None, "environment": None, "progress": [], "heartbeats": []}

    class Process:
        returncode = 0

        def __init__(self):
            self.polls = 0

        def poll(self):
            self.polls += 1
            return None if self.polls == 1 else 0

    def popen(command, cwd, env):
        saved["command"] = command
        saved["environment"] = env
        return Process()

    monkeypatch.setattr(job_worker.subprocess, "Popen", popen)
    monkeypatch.setattr(job_worker.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(job_worker.time, "monotonic", iter((0.0, 1.0)).__next__)
    monkeypatch.setattr(job_worker.jobs, "update_progress", lambda job_id, progress: saved["progress"].append((job_id, progress)))
    monkeypatch.setattr(job_worker.jobs, "heartbeat", lambda job_id: saved["heartbeats"].append(job_id))
    monkeypatch.delenv("MANUAL_UPDATE_AUDIO", raising=False)

    job_worker.run_news_update({"id": 17})

    assert saved["command"][0] == sys.executable
    assert saved["command"][-3:] == ["60", "--once", "--no-audio"]
    assert saved["environment"]["NEWS_UPDATE_JOB_ID"] == "17"
    assert saved["progress"] == [(17, {"phase": "starting", "percent": 1})]
    assert saved["heartbeats"] == [17]
    assert os.environ.get("NEWS_UPDATE_JOB_ID") is None
