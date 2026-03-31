from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from ..core.config import Settings


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

    def generate_state(self) -> str:
        payload = {'ts': int(time.time())}
        payload_raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        payload_b64 = base64.urlsafe_b64encode(payload_raw).decode('utf-8').rstrip('=')

        signature = hmac.new(
            self.settings.app_secret_key.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        return f'{payload_b64}.{signature}'

    def validate_state(self, state: str, max_age_seconds: int = 600) -> bool:
        try:
            payload_b64, signature = state.split('.', 1)
        except ValueError:
            return False

        expected_signature = hmac.new(
            self.settings.app_secret_key.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return False

        try:
            padded = payload_b64 + '=' * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode('utf-8'))
            ts = int(payload['ts'])
        except (KeyError, ValueError, json.JSONDecodeError):
            return False

        return int(time.time()) - ts <= max_age_seconds
