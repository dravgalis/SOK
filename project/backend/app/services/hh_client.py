from __future__ import annotations

from typing import Any

import httpx

from ..core.config import Settings


class HHClientError(Exception):
    pass


class HHClient:
    TOKEN_URL = 'https://hh.ru/oauth/token'
    API_BASE_URL = 'https://api.hh.ru'

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def exchange_code(self, code: str) -> str:
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.settings.hh_client_id,
            'client_secret': self.settings.hh_client_secret,
            'code': code,
            'redirect_uri': self.settings.hh_redirect_uri,
        }
        payload = await self._request('POST', self.TOKEN_URL, data=data)

        access_token = payload.get('access_token')
        if not isinstance(access_token, str) or not access_token:
            raise HHClientError('В ответе HeadHunter OAuth отсутствует access_token.')

        return access_token

    async def get_current_user(self, access_token: str) -> dict[str, Any]:
        return await self._request('GET', f'{self.API_BASE_URL}/me', access_token=access_token)

    async def get_employer(self, access_token: str, employer_id: str) -> dict[str, Any]:
        return await self._request('GET', f'{self.API_BASE_URL}/employers/{employer_id}', access_token=access_token)

    async def get_vacancies(
        self,
        access_token: str,
        *,
        per_page: int = 100,
        archived: bool = False,
    ) -> list[dict[str, Any]]:
        all_items: list[dict[str, Any]] = []
        page = 0

        while True:
            payload = await self._request(
                'GET',
                f'{self.API_BASE_URL}/vacancies',
                access_token=access_token,
                params={
                    'per_page': str(per_page),
                    'page': str(page),
                    'archived': 'true' if archived else 'false',
                },
            )

            items = payload.get('items')
            pages = payload.get('pages')

            if isinstance(items, list):
                all_items.extend(item for item in items if isinstance(item, dict))

            if not isinstance(pages, int):
                break

            page += 1
            if page >= pages:
                break

        return all_items

    async def _request(
        self,
        method: str,
        url: str,
        *,
        access_token: str | None = None,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {'User-Agent': 'SOK-HH-MVP/1.0'}
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'

        request_kwargs: dict[str, Any] = {'headers': headers, 'params': params}
        if data is not None:
            request_kwargs['data'] = data

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(method, url, **request_kwargs)
        except httpx.HTTPError as exc:
            raise HHClientError('Не удалось связаться с HeadHunter API.') from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise HHClientError(f'HeadHunter API вернул ошибку: {detail}')

        try:
            return response.json()
        except ValueError as exc:
            raise HHClientError('HeadHunter API вернул некорректный ответ.') from exc
