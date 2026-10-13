import os
from dotenv import load_dotenv
import sys
from urllib.parse import urlsplit
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from root directory
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_path = root_dir / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # API Configuration
    APP_NAME: str = "AI NewsSense API"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Provider keys/models live in core/providers.py; the Knowledge Graph is a separate DashScope app
    ALIBABA_LLM_KEY_KG: str = os.getenv('ALIBABA_LLM_KEY_KG', '')

    # CORS: comma-separated origins allowed to call the API from a browser
    ALLOWED_ORIGINS: list = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
    ALLOWED_HOSTS: list = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
    MAX_REQUEST_BYTES: int = max(1024, int(os.getenv("MAX_REQUEST_BYTES", "1048576")))
    SLOW_REQUEST_MS: int = max(100, int(os.getenv("SLOW_REQUEST_MS", "1500")))

    # Writable folder for generated translations, digests and audio (static/ is read-only in Docker)
    CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", "cache"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

    # Public address of the site, used in share previews and the RSS feed (e.g. https://news.example.com).
    # When empty, the address of the incoming request is used.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    @classmethod
    def production_issues(cls) -> list[str]:
        """Configuration mistakes that should block a public production launch."""
        issues = []
        if not cls.PUBLIC_BASE_URL.startswith("https://"):
            issues.append("PUBLIC_BASE_URL must use https://")
        if cls.ALLOWED_ORIGINS == ["*"]:
            issues.append("ALLOWED_ORIGINS must name the public site")
        if cls.ALLOWED_HOSTS == ["*"]:
            issues.append("ALLOWED_HOSTS must name the public host")
        if len(os.getenv("METRICS_TOKEN", "")) < 24:
            issues.append("METRICS_TOKEN must contain at least 24 characters")
        alert_webhook = os.getenv("ALERT_WEBHOOK_URL", "").strip()
        if alert_webhook and not alert_webhook.startswith("https://"):
            issues.append("ALERT_WEBHOOK_URL must use https:// when configured")
        sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
        if sentry_dsn and not sentry_dsn.startswith("https://"):
            issues.append("SENTRY_DSN must use https:// when configured")
        vapid_public = os.getenv("VAPID_PUBLIC_KEY", "").strip()
        vapid_private = os.getenv("VAPID_PRIVATE_KEY", "").strip()
        vapid_subject = os.getenv("VAPID_SUBJECT", "").strip()
        if any((vapid_public, vapid_private)) and not all((vapid_public, vapid_private)):
            issues.append("Both VAPID Web Push keys must be configured together")
        if os.getenv("OBJECT_STORAGE_BUCKET") and len(os.getenv("OBJECT_STORAGE_MANIFEST_KEY", "")) < 32:
            issues.append("OBJECT_STORAGE_MANIFEST_KEY must contain at least 32 characters")
        if (vapid_public or vapid_private) and not vapid_subject.startswith(("mailto:", "https://")):
            issues.append("VAPID_SUBJECT must use mailto: or https:// when Web Push is configured")
        email_enabled = os.getenv("EMAIL_DIGEST_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        if email_enabled and (
            not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM") or not os.getenv("DIGEST_EMAIL_TO")
        ):
            issues.append("SMTP_HOST, SMTP_FROM and DIGEST_EMAIL_TO are required for email digests")
        from .admin_accounts import has_users, owner_mfa_ready
        named_admins = has_users()
        if not named_admins and len(os.getenv("ADMIN_TOKEN", "")) < 24:
            issues.append("Create a named administrator or set a 24-character ADMIN_TOKEN")
        if named_admins and not owner_mfa_ready():
            issues.append("Every active owner account must enable MFA")
        if named_admins and os.getenv("ALLOW_LEGACY_ADMIN_TOKEN", "").strip().lower() == "true":
            issues.append("Disable ALLOW_LEGACY_ADMIN_TOKEN after creating named administrators")
        from .providers import PROVIDERS
        enabled_providers = [
            (provider_id, provider)
            for provider_id, provider in PROVIDERS.items()
            if os.getenv(provider.key_env)
        ]
        if enabled_providers:
            try:
                if float(os.getenv("AI_DAILY_SPEND_LIMIT_USD", "0")) <= 0:
                    issues.append("AI_DAILY_SPEND_LIMIT_USD must be greater than zero when AI is enabled")
                if float(os.getenv("AI_MONTHLY_SPEND_LIMIT_USD", "0")) <= 0:
                    issues.append("AI_MONTHLY_SPEND_LIMIT_USD must be greater than zero when AI is enabled")
            except ValueError:
                issues.append("AI spending limits must be valid USD amounts")
        for provider_id, provider in enabled_providers:
            if (
                not os.getenv(f"{provider_id}_INPUT_USD_PER_MTOK")
                or not os.getenv(f"{provider_id}_OUTPUT_USD_PER_MTOK")
            ):
                issues.append(f"{provider_id} token prices must be configured")
        if not cls.DATABASE_URL.startswith(("postgresql://", "postgres://")):
            issues.append("DATABASE_URL must use PostgreSQL")
        else:
            database_password = os.getenv("PGPASSWORD", "") or (urlsplit(cls.DATABASE_URL).password or "")
            if len(database_password) < 24:
                issues.append("PostgreSQL password must be at least 24 characters")
        if cls.PUBLIC_BASE_URL:
            host = urlsplit(cls.PUBLIC_BASE_URL).hostname
            if host and cls.ALLOWED_HOSTS != ["*"] and host not in cls.ALLOWED_HOSTS:
                issues.append("PUBLIC_BASE_URL host must be included in ALLOWED_HOSTS")
        return issues

settings = Settings()
