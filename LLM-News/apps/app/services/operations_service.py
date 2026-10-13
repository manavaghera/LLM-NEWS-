"""Owner-facing update health and generation usage, without model prompts or provider errors."""
from ..core import analytics, generation, jobs, monitoring, notifications
from .update_status import read_update_status


def usage_snapshot() -> dict:
    saved = generation.usage_summary()
    usage = {key: saved.get(key) for key in (
        "date", "month", "pipeline_calls", "pipeline_limit", "remaining",
        "monthly_calls", "monthly_limit", "monthly_remaining", "daily_spent_usd",
        "daily_spend_limit_usd", "daily_spend_remaining_usd", "monthly_spent_usd",
        "monthly_spend_limit_usd", "monthly_spend_remaining_usd",
    )}
    usage["models"] = [
        {key: model.get(key) for key in
         ("provider", "model", "calls", "failed", "prompt_tokens", "completion_tokens",
          "spent_usd", "unpriced_calls")}
        for model in saved.get("models", [])
    ]
    return usage


def operations_snapshot() -> dict:
    feeds = []
    for saved in generation.feed_statuses():
        feed = {key: saved.get(key) for key in
                ("publisher", "url", "category", "ok", "items", "full_text_items", "last_checked")}
        feed["error"] = "Feed fetch failed." if saved.get("error") else None
        feeds.append(feed)

    runs = []
    for saved in generation.recent_runs():
        run = {key: saved.get(key) for key in
               ("started_at", "finished_at", "date", "status", "added", "held_back")}
        run["error"] = "Update failed." if saved.get("error") else None
        runs.append(run)

    update = read_update_status()
    latest_status = runs[0].get("status") if runs else None
    update["ok"] = (True if latest_status in {"ok", "success", "completed"} else
                    False if latest_status in {"error", "failed"} else None)
    held_stories = [
        {key: saved.get(key) for key in ("date", "category", "headline", "reason", "created_at")}
        for saved in generation.held_stories()
    ]
    return {"update": update, "feeds": feeds, "runs": runs, "held_stories": held_stories,
            "usage": usage_snapshot(), "analytics": analytics.snapshot(), "jobs": jobs.summary(),
            "events": monitoring.recent_events(), "notifications": notifications.summary(),
            "news_update": jobs.latest("news_update")}


def update_pipeline_budget(daily_call_limit: int, monthly_call_limit: int | None = None) -> dict:
    if monthly_call_limit is None:
        generation.set_pipeline_limit(daily_call_limit)
    else:
        generation.set_pipeline_limits(daily_call_limit, monthly_call_limit)
    return usage_snapshot()


def update_spending_budget(daily_usd, monthly_usd) -> dict:
    generation.set_spending_limits(daily_usd, monthly_usd)
    return usage_snapshot()


def update_model_price(provider: str, model: str, input_usd_per_mtok, output_usd_per_mtok) -> dict:
    generation.set_model_price(provider, model, input_usd_per_mtok, output_usd_per_mtok)
    return usage_snapshot()
