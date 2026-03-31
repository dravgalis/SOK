from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings


class HHClientError(Exception):
    pass


class HHClient:
    TOKEN_URL = 'https://hh.ru/oauth/token'

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.settings.hh_client_id,
            'client_secret': self.settings.hh_client_secret,
            'code': code,
            'redirect_uri': self.settings.hh_redirect_uri,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                )
        except httpx.HTTPError as exc:
            raise HHClientError('Не удалось связаться с HeadHunter OAuth API.') from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise HHClientError(f'HeadHunter OAuth вернул ошибку: {detail}')

        try:
            payload = response.json()
        except ValueError as exc:
            raise HHClientError('HeadHunter OAuth вернул некорректный ответ.') from exc

        if 'access_token' not in payload:
            raise HHClientError('В ответе HeadHunter OAuth отсутствует access_token.')

        return payload
