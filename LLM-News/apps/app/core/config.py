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
        if len(os.getenv("ADMIN_TOKEN", "")) < 24:
            issues.append("ADMIN_TOKEN must be at least 24 characters")
        if cls.PUBLIC_BASE_URL:
            host = urlsplit(cls.PUBLIC_BASE_URL).hostname
            if host and cls.ALLOWED_HOSTS != ["*"] and host not in cls.ALLOWED_HOSTS:
                issues.append("PUBLIC_BASE_URL host must be included in ALLOWED_HOSTS")
        return issues

settings = Settings()
