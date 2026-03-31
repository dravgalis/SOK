from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / '.env')


class Settings(BaseModel):
    app_name: str = os.getenv('APP_NAME', 'HH SaaS Backend')
    app_env: str = os.getenv('APP_ENV', 'development')

    hh_client_id: str = os.getenv('HH_CLIENT_ID', '')
    hh_client_secret: str = os.getenv('HH_CLIENT_SECRET', '')
    hh_redirect_uri: str = os.getenv('HH_REDIRECT_URI', 'http://localhost:8000/api/auth/hh/callback')

    frontend_app_url: str = os.getenv('FRONTEND_APP_URL', 'http://localhost:5173')
    app_secret_key: str = os.getenv('APP_SECRET_KEY', 'change-me-in-production')

    cors_origins_raw: str = os.getenv('CORS_ORIGINS', 'http://localhost:5173')

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(',') if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
