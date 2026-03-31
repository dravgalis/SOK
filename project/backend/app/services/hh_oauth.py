from urllib.parse import urlencode

from app.core.config import Settings


class HHOAuthService:
    AUTHORIZE_URL = 'https://hh.ru/oauth/authorize'

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def build_authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                'response_type': 'code',
                'client_id': self.settings.hh_client_id,
                'redirect_uri': self.settings.hh_redirect_uri,
                'state': state,
            }
        )
        return f'{self.AUTHORIZE_URL}?{query}'
