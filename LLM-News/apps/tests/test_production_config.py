"""Production readiness requires configured features without forcing optional paid services."""
from app.core import admin_accounts
from app.core.config import Settings
from app.core.providers import PROVIDERS


def configure_minimal_free_launch(monkeypatch):
    monkeypatch.setattr(Settings, "PUBLIC_BASE_URL", "https://news.example.test")
    monkeypatch.setattr(Settings, "ALLOWED_ORIGINS", ["https://news.example.test"])
    monkeypatch.setattr(Settings, "ALLOWED_HOSTS", ["news.example.test"])
    database_url = "postgresql://news:long-database-password-for-production@db.example.test/news"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr(Settings, "DATABASE_URL", database_url)
    monkeypatch.setenv("ADMIN_TOKEN", "long-administrator-bootstrap-token")
    monkeypatch.setenv("METRICS_TOKEN", "long-metrics-access-token-value")
    monkeypatch.setattr(admin_accounts, "has_users", lambda: False)
    for name in (
        "ALERT_WEBHOOK_URL", "SENTRY_DSN", "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY",
        "SMTP_HOST", "SMTP_FROM", "DIGEST_EMAIL_TO", "OBJECT_STORAGE_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMAIL_DIGEST_ENABLED", "false")
    for provider in PROVIDERS.values():
        monkeypatch.delenv(provider.key_env, raising=False)


def test_free_launch_does_not_require_disabled_integrations(monkeypatch):
    configure_minimal_free_launch(monkeypatch)
    assert Settings.production_issues() == []


def test_partially_enabled_integrations_fail_readiness(monkeypatch):
    configure_minimal_free_launch(monkeypatch)
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public-only")
    monkeypatch.setenv("EMAIL_DIGEST_ENABLED", "true")

    issues = Settings.production_issues()

    assert "Both VAPID Web Push keys must be configured together" in issues
    assert "SMTP_HOST, SMTP_FROM and DIGEST_EMAIL_TO are required for email digests" in issues


def test_enabled_ai_requires_currency_limits_and_prices(monkeypatch):
    configure_minimal_free_launch(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "configured")
    monkeypatch.setenv("AI_DAILY_SPEND_LIMIT_USD", "0")
    monkeypatch.setenv("AI_MONTHLY_SPEND_LIMIT_USD", "0")

    issues = Settings.production_issues()

    assert any("AI_DAILY_SPEND_LIMIT_USD" in issue for issue in issues)
    assert any("AI_MONTHLY_SPEND_LIMIT_USD" in issue for issue in issues)
    assert "OPENAI token prices must be configured" in issues
