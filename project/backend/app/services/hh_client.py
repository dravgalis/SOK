from __future__ import annotations

import logging
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
        self.logger = logging.getLogger(__name__)

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

    async def get_vacancy_responses(self, access_token: str, vacancy_id: str, *, per_page: int = 100) -> list[dict[str, Any]]:
        result = await self.get_vacancy_responses_with_debug(access_token, vacancy_id, per_page=per_page)
        return result['items']

    async def get_vacancy_responses_with_debug(
        self,
        access_token: str,
        vacancy_id: str,
        *,
        per_page: int = 100,
    ) -> dict[str, Any]:
        all_items: list[dict[str, Any]] = []
        page = 0
        debug_calls: list[dict[str, Any]] = []
        hh_endpoint = f'{self.API_BASE_URL}/negotiations'

        while True:
            payload = await self._request(
                'GET',
                hh_endpoint,
                access_token=access_token,
                params={
                    'vacancy_id': str(vacancy_id),
                    'per_page': str(per_page),
                    'page': str(page),
                },
                allow_statuses={404},
                debug_context={
                    'operation': 'get_vacancy_responses',
                    'vacancy_id': str(vacancy_id),
                },
            )
            if isinstance(payload.get('_debug'), dict):
                debug_calls.append(payload['_debug'])

            if payload.get('_status_code') == 404:
                return {'items': [], 'debug': {'hh_endpoint': hh_endpoint, 'calls': debug_calls}}

            items = self._extract_response_items(payload)
            pages = payload.get('pages')

            if isinstance(items, list):
                all_items.extend(item for item in items if isinstance(item, dict))

            if not isinstance(pages, int):
                break

            page += 1
            if page >= pages:
                break

        return {'items': all_items, 'debug': {'hh_endpoint': hh_endpoint, 'calls': debug_calls}}

    def _extract_response_items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidate_keys = ('items', 'negotiations', 'responses', 'data')
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    async def _request(
        self,
        method: str,
        url: str,
        *,
        access_token: str | None = None,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        allow_statuses: set[int] | None = None,
        debug_context: dict[str, Any] | None = None,
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

        response_body_preview = response.text[:1000]
        safe_headers = dict(headers)
        if 'Authorization' in safe_headers:
            safe_headers['Authorization'] = 'Bearer ***'
        if debug_context:
            self.logger.warning(
                'HH DEBUG operation=%s vacancy_id=%s method=%s url=%s params=%s headers=%s status=%s body_preview=%s',
                debug_context.get('operation'),
                debug_context.get('vacancy_id'),
                method,
                url,
                params,
                safe_headers,
                response.status_code,
                response_body_preview,
            )

        if allow_statuses and response.status_code in allow_statuses:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if isinstance(payload, dict):
                payload['_status_code'] = response.status_code
                payload['_debug'] = {
                    'request_url': str(response.request.url),
                    'query_params': params or {},
                    'request_headers': safe_headers,
                    'status_code': response.status_code,
                    'response_body_preview': response_body_preview,
                }
                return payload
            return {
                '_status_code': response.status_code,
                '_debug': {
                    'request_url': str(response.request.url),
                    'query_params': params or {},
                    'request_headers': safe_headers,
                    'status_code': response.status_code,
                    'response_body_preview': response_body_preview,
                },
            }

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise HHClientError(f'HeadHunter API вернул ошибку: {detail}')

        try:
            payload = response.json()
        except ValueError as exc:
            raise HHClientError('HeadHunter API вернул некорректный ответ.') from exc

        if not isinstance(payload, dict):
            payload = {'raw': payload}
        payload['_debug'] = {
            'request_url': str(response.request.url),
            'query_params': params or {},
            'request_headers': safe_headers,
            'status_code': response.status_code,
            'response_body_preview': response_body_preview,
        }
        return payload
