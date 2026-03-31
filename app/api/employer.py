from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

HH_API_BASE = 'https://api.hh.ru'
logger = logging.getLogger(__name__)


@router.get('/me')
async def get_me(request: Request) -> dict[str, str | None]:
    access_token = _require_access_token(request)

    async with httpx.AsyncClient(timeout=20.0) as client:
        me_payload = await _hh_get(client, '/me', access_token=access_token)

        manager_id = _extract_manager_id(me_payload)
        employer_id = _extract_employer_id(me_payload)

        company_name: str | None = None
        company_logo_url: str | None = None

        if employer_id:
            employer_payload = await _hh_get(client, f'/employers/{employer_id}', access_token=access_token)
            company_name = employer_payload.get('name') if isinstance(employer_payload.get('name'), str) else None
            company_logo_url = _extract_logo_url(employer_payload)

    return {
        'user_name': _extract_user_name(me_payload),
        'company_name': company_name,
        'company_logo_url': company_logo_url,
        'manager_id': manager_id,
        'employer_id': employer_id,
    }

        if employer_id:
            employer_payload = await _hh_get(client, f'/employers/{employer_id}', access_token=access_token)
            company_name = employer_payload.get('name') if isinstance(employer_payload.get('name'), str) else None
            company_logo_url = _extract_logo_url(employer_payload)

@router.get('/vacancies')
async def get_vacancies(request: Request) -> dict[str, object]:
    access_token = _require_access_token(request)

    async with httpx.AsyncClient(timeout=20.0) as client:
        me_payload = await _hh_get(client, '/me', access_token=access_token)
        employer_id = _extract_employer_id(me_payload)
        manager_id = _extract_manager_id(me_payload)

        logger.info('HH vacancies debug: resolved employer_id=%s manager_id=%s', employer_id, manager_id)

        if not employer_id:
            raise HTTPException(status_code=502, detail='Не удалось определить employer_id из профиля HH.')

        active_raw = await _fetch_all_vacancies(
            client,
            access_token=access_token,
            employer_id=employer_id,
            manager_id=manager_id,
            archived=False,
        )
        archived_raw = await _fetch_all_vacancies(
            client,
            access_token=access_token,
            employer_id=employer_id,
            manager_id=manager_id,
            archived=True,
        )

    active = [_normalize_vacancy(vacancy, fallback_status='active') for vacancy in active_raw]
    archived = [_normalize_vacancy(vacancy, fallback_status='archived') for vacancy in archived_raw]

    return {
        'active': active,
        'archived': archived,
        'counts': {
            'active': len(active),
            'archived': len(archived),
        },
    }


def _require_access_token(request: Request) -> str:
    access_token = request.cookies.get('access_token')
    if not access_token:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return access_token


async def _hh_get(client: httpx.AsyncClient, path: str, *, access_token: str, params: dict[str, str] | None = None) -> dict:
    url = f'{HH_API_BASE}{path}'
    logger.info('HH request debug: url=%s params=%s', url, params)

    response = await client.get(
        url,
        headers={'Authorization': f'Bearer {access_token}'},
        params=params,
    )

    logger.info('HH response debug: url=%s status_code=%s', url, response.status_code)

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail='Unauthorized')

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f'HH API error on {path}: {response.text}') from exc

    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail=f'HH API returned non-object payload for {path}.')

    return payload


async def _fetch_all_vacancies(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    employer_id: str,
    manager_id: str | None,
    archived: bool,
) -> list[dict]:
    status_path = 'archived' if archived else 'active'

    preferred_items = await _fetch_paginated_vacancies(
        client,
        access_token=access_token,
        endpoint=f'/employers/{employer_id}/vacancies/{status_path}',
        params_builder=lambda page, per_page: {
            'page': str(page),
            'per_page': str(per_page),
        },
    )

    if preferred_items:
        return preferred_items

    fallback_items = await _fetch_paginated_vacancies(
        client,
        access_token=access_token,
        endpoint='/vacancies',
        params_builder=lambda page, per_page: {
            'employer_id': employer_id,
            'manager_id': manager_id or '',
            'archived': 'true' if archived else 'false',
            'page': str(page),
            'per_page': str(per_page),
        },
    )
    return fallback_items


async def _fetch_paginated_vacancies(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    endpoint: str,
    params_builder,
) -> list[dict]:
    page = 0
    per_page = 100
    all_items: list[dict] = []

    while True:
        params = params_builder(page, per_page)
        params = {k: v for k, v in params.items() if v}

        try:
            payload = await _hh_get(client, endpoint, access_token=access_token, params=params)
        except HTTPException as exc:
            logger.warning('HH vacancies debug: endpoint=%s failed status=%s', endpoint, exc.status_code)
            if page == 0:
                return []
            break

        items = payload.get('items')
        if isinstance(items, list):
            page_items = [item for item in items if isinstance(item, dict)]
            all_items.extend(page_items)
        else:
            page_items = []

        found = payload.get('found')
        logger.info(
            'HH vacancies debug: endpoint=%s page=%s items_len=%s found=%s sample_items=%s',
            endpoint,
            page,
            len(page_items),
            found,
            page_items[:2],
        )

        pages = payload.get('pages')
        if not isinstance(pages, int):
            break

        page += 1
        if page >= pages:
            break

    logger.info('HH vacancies debug: endpoint=%s total_items=%s', endpoint, len(all_items))
    return all_items


def _extract_user_name(me_payload: dict) -> str | None:
    first_name = me_payload.get('first_name')
    last_name = me_payload.get('last_name')

    parts = []
    if isinstance(first_name, str) and first_name.strip():
        parts.append(first_name.strip())
    if isinstance(last_name, str) and last_name.strip():
        parts.append(last_name.strip())

    return ' '.join(parts) if parts else None


def _extract_manager_id(me_payload: dict) -> str | None:
    manager = me_payload.get('manager')
    if isinstance(manager, dict) and manager.get('id') is not None:
        return str(manager.get('id'))
    return None


def _extract_employer_id(me_payload: dict) -> str | None:
    employer = me_payload.get('employer')
    if isinstance(employer, dict) and employer.get('id') is not None:
        return str(employer.get('id'))

    manager_settings_url = me_payload.get('manager_settings_url')
    if isinstance(manager_settings_url, str) and manager_settings_url:
        parsed = urlparse(manager_settings_url)
        parts = [part for part in parsed.path.split('/') if part]
        if 'employers' in parts:
            index = parts.index('employers')
            if index + 1 < len(parts):
                return parts[index + 1]

    return None


def _extract_logo_url(employer_payload: dict) -> str | None:
    logo_urls = employer_payload.get('logo_urls')
    if not isinstance(logo_urls, dict):
        return None

    for key in ('original', '240', '90'):
        value = logo_urls.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _normalize_vacancy(vacancy: dict, *, fallback_status: str) -> dict[str, str | None]:
    status_name: str | None = None

    vacancy_status = vacancy.get('status')
    vacancy_type = vacancy.get('type')

    if isinstance(vacancy_status, dict) and isinstance(vacancy_status.get('name'), str):
        status_name = vacancy_status.get('name')
    elif isinstance(vacancy_type, dict) and isinstance(vacancy_type.get('name'), str):
        status_name = vacancy_type.get('name')

    return {
        'id': str(vacancy.get('id', '')),
        'name': str(vacancy.get('name', '')),
        'status': status_name or fallback_status,
        'published_at': str(vacancy.get('published_at')) if vacancy.get('published_at') else None,
        'archived_at': str(vacancy.get('archived_at')) if vacancy.get('archived_at') else None,
    }
