from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
import os

BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / '.env')


class Settings(BaseModel):
    app_name: str = os.getenv('APP_NAME', 'HH SaaS Backend')
    app_env: str = os.getenv('APP_ENV', 'development')
    hh_client_id: str = os.getenv('HH_CLIENT_ID', '')
    hh_client_secret: str = os.getenv('HH_CLIENT_SECRET', '')
    hh_redirect_uri: str = os.getenv('HH_REDIRECT_URI', 'http://localhost:5173/auth/hh/callback')


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
