import os
from dotenv import load_dotenv
import sys
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

    # Writable folder for generated translations, digests and audio (static/ is read-only in Docker)
    CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", "cache"))

    # Public address of the site, used in share previews and the RSS feed (e.g. https://news.example.com).
    # When empty, the address of the incoming request is used.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

settings = Settings()
