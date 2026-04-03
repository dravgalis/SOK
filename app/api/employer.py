from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

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

    active = [_normalize_vacancy(vacancy, archived=False) for vacancy in active_raw]
    archived = [_normalize_vacancy(vacancy, archived=True) for vacancy in archived_raw]

    return {
        'active': active,
        'archived': archived,
        'counts': {
            'active': len(active),
            'archived': len(archived),
        },
    }


@router.get('/vacancies/{vacancy_id}')
async def get_vacancy_by_id(vacancy_id: str, request: Request) -> dict[str, object]:
    access_token = _require_access_token(request)

    async with httpx.AsyncClient(timeout=20.0) as client:
        me_payload = await _hh_get(client, '/me', access_token=access_token)
        employer_id = _extract_employer_id(me_payload)
        manager_id = _extract_manager_id(me_payload)

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

    for vacancy in active_raw:
        if str(vacancy.get('id', '')) == vacancy_id:
            normalized = _normalize_vacancy(vacancy, archived=False)
            return {
                'id': normalized['id'],
                'name': normalized['name'],
                'normalized_status': normalized['normalized_status'],
                'published_at': normalized['published_at'],
                'archived_at': normalized['archived_at'],
                'responses_count': normalized['responses_count'],
                'description': None,
            }

    for vacancy in archived_raw:
        if str(vacancy.get('id', '')) == vacancy_id:
            normalized = _normalize_vacancy(vacancy, archived=True)
            return {
                'id': normalized['id'],
                'name': normalized['name'],
                'normalized_status': normalized['normalized_status'],
                'published_at': normalized['published_at'],
                'archived_at': normalized['archived_at'],
                'responses_count': normalized['responses_count'],
                'description': None,
            }

    raise HTTPException(status_code=404, detail='Вакансия не найдена.')


@router.get('/vacancies/{vacancy_id}/responses')
async def get_vacancy_responses(
    vacancy_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    all: bool = Query(default=False),
) -> dict[str, object]:
    access_token = _require_access_token(request)

    async with httpx.AsyncClient(timeout=20.0) as client:
        responses_payload = await _fetch_all_responses(client, access_token=access_token, vacancy_id=vacancy_id)

    all_items = responses_payload['items'] if isinstance(responses_payload['items'], list) else []
    detailed_items_count = responses_payload['detailed_items_count'] if isinstance(responses_payload['detailed_items_count'], int) else len(all_items)

    if all:
        resolved_page = 1
        effective_per_page = detailed_items_count if detailed_items_count > 0 else per_page
        pages = 1
        paginated_items = all_items
    else:
        effective_per_page = per_page
        pages = max((detailed_items_count + per_page - 1) // per_page, 1)
        resolved_page = min(page, pages)
        start_index = (resolved_page - 1) * per_page
        end_index = start_index + per_page
        paginated_items = all_items[start_index:end_index]

    return {
        'vacancy_id': vacancy_id,
        'items': paginated_items,
        'summary_by_state': responses_payload['summary_by_state'],
        'total': responses_payload['count'],
        'count': responses_payload['count'],
        'page': resolved_page,
        'per_page': effective_per_page,
        'pages': pages,
        'total_from_vacancy': responses_payload['total_from_vacancy'],
        'hh_total_raw': responses_payload['hh_total_raw'],
        'detailed_items_count': detailed_items_count,
        'pages_loaded': responses_payload['pages_loaded'],
        'items_before_filtering': responses_payload['items_before_filtering'],
        'items_after_filtering': responses_payload['items_after_filtering'],
        'states_processed': responses_payload['states_processed'],
        'full_export': all,
    }


def _require_access_token(request: Request) -> str:
    access_token = request.cookies.get('access_token')
    if not access_token:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return access_token


async def _hh_get(
    client: httpx.AsyncClient,
    path: str,
    *,
    access_token: str,
    params: dict[str, str] | None = None,
    allow_404: bool = False,
) -> dict:
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

    if allow_404 and response.status_code == 404:
        return {'_status_code': 404}

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

        pages = payload.get('pages')
        if not isinstance(pages, int):
            break

        page += 1
        if page >= pages:
            break

    return all_items


async def _fetch_all_responses(client: httpx.AsyncClient, *, access_token: str, vacancy_id: str) -> dict[str, object]:
    vacancy_payload = await _hh_get(
        client,
        f'/vacancies/{vacancy_id}',
        access_token=access_token,
        allow_404=True,
    )
    total_from_vacancy = _extract_responses_count(vacancy_payload) if vacancy_payload.get('_status_code') != 404 else 0

    payload = await _hh_get(
        client,
        '/negotiations',
        access_token=access_token,
        params={
            'vacancy_id': vacancy_id,
            'status': 'any',
            'page': '0',
            'per_page': '50',
        },
        allow_404=True,
    )

    if payload.get('_status_code') == 404:
        return {
            'items': [],
            'summary_by_state': [],
            'count': 0,
            'total_from_vacancy': total_from_vacancy,
            'hh_total_raw': 0,
            'pages_loaded': 0,
            'items_before_filtering': 0,
            'items_after_filtering': 0,
            'states_processed': [],
        }

    states_processed, state_names = await _discover_response_states(
        client,
        access_token=access_token,
        vacancy_id=vacancy_id,
        seed_payload=payload,
    )
    summary_by_state = _extract_summary_by_state(payload, state_names=state_names)

    pages_loaded = 0
    hh_total_raw = _extract_hh_total_raw(payload)
    raw_items: list[dict] = []
    dedupe_keys: set[str] = set()

    for state in states_processed:
        state_items, state_pages, state_total = await _fetch_negotiations_pages(
            client,
            access_token=access_token,
            vacancy_id=vacancy_id,
            state=state,
        )
        pages_loaded += state_pages
        if isinstance(state_total, int):
            hh_total_raw = max(hh_total_raw, state_total)

        for item in state_items:
            dedupe_key = _extract_response_dedupe_key(item)
            if dedupe_key in dedupe_keys:
                continue
            dedupe_keys.add(dedupe_key)
            raw_items.append(item)

    followup_items = await _fetch_followup_negotiations_from_collections(
        client,
        access_token=access_token,
        vacancy_id=vacancy_id,
        payload=payload,
    )
    for item in followup_items:
        dedupe_key = _extract_response_dedupe_key(item)
        if dedupe_key in dedupe_keys:
            continue
        dedupe_keys.add(dedupe_key)
        raw_items.append(item)

    items_before_filtering = len(raw_items)
    source_items = [item for item in raw_items if _is_real_response_item(item)]
    items_after_filtering = len(source_items)

    normalized_items = [_normalize_response(item) for item in source_items]
    total_count = len(normalized_items)

    return {
        'items': normalized_items,
        'summary_by_state': summary_by_state,
        'count': total_count,
        'detailed_items_count': len(normalized_items),
        'total_from_vacancy': total_from_vacancy,
        'hh_total_raw': hh_total_raw,
        'pages_loaded': pages_loaded,
        'items_before_filtering': items_before_filtering,
        'items_after_filtering': items_after_filtering,
        'states_processed': states_processed,
        'summary_total_hint': sum(item.get('count', 0) for item in summary_by_state if isinstance(item.get('count'), int)),
    }


def _extract_hh_total_raw(payload: dict) -> int:
    for key in ('total', 'found', 'count'):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return 0


def _extract_states_from_collections(payload: dict) -> list[str]:
    collections = payload.get('collections')
    if not isinstance(collections, list):
        return []

    states: list[str] = []
    for collection in collections:
        if not isinstance(collection, dict):
            continue
        for entry in _extract_collection_entries(collection):
            state = entry.get('id')
            if isinstance(state, str) and state and state not in states:
                states.append(state)
    return states


def _extract_state_names_from_collections(payload: dict) -> dict[str, str]:
    collections = payload.get('collections')
    if not isinstance(collections, list):
        return {}

    state_names: dict[str, str] = {}
    for collection in collections:
        if not isinstance(collection, dict):
            continue
        for entry in _extract_collection_entries(collection):
            state_id = entry.get('id')
            state_name = entry.get('name')
            if isinstance(state_id, str) and state_id and isinstance(state_name, str) and state_name:
                state_names[state_id] = state_name
    return state_names


async def _discover_response_states(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    vacancy_id: str,
    seed_payload: dict,
) -> tuple[list[str], dict[str, str]]:
    states: list[str] = ['any']
    state_names = _extract_state_names_from_collections(seed_payload)
    for state in _extract_states_from_collections(seed_payload):
        if state not in states:
            states.append(state)

    for path in ('/negotiations/response_statuses', '/negotiations/statuses'):
        payload = await _hh_get(
            client,
            path,
            access_token=access_token,
            params={'vacancy_id': vacancy_id},
            allow_404=True,
        )
        if payload.get('_status_code') == 404:
            continue

        for state_id, state_name in _extract_states_from_payload(payload):
            if state_id not in states:
                states.append(state_id)
            if state_name:
                state_names[state_id] = state_name

    return states, state_names


def _extract_states_from_payload(payload: dict) -> list[tuple[str, str | None]]:
    extracted: list[tuple[str, str | None]] = []
    seen: set[str] = set()

    def push(state_id: object, state_name: object) -> None:
        if not isinstance(state_id, str) or not state_id:
            return
        if state_id in seen:
            return
        seen.add(state_id)
        extracted.append((state_id, state_name if isinstance(state_name, str) and state_name else None))

    state_names = _extract_state_names_from_collections(payload)
    for state in _extract_states_from_collections(payload):
        state_name = state_names.get(state)
        push(state, state_name)

    for key in ('items', 'statuses', 'data'):
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            push(row.get('id'), row.get('name'))

    return extracted


async def _fetch_negotiations_pages(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    vacancy_id: str,
    state: str,
) -> tuple[list[dict], int, int | None]:
    page = 0
    per_page = 50
    pages_loaded = 0
    items: list[dict] = []
    raw_total: int | None = None

    while True:
        payload = await _hh_get(
            client,
            '/negotiations',
            access_token=access_token,
            params={
                'vacancy_id': vacancy_id,
                'status': state,
                'page': str(page),
                'per_page': str(per_page),
            },
            allow_404=True,
        )
        if payload.get('_status_code') == 404:
            break

        pages_loaded += 1
        raw_total = _extract_hh_total_raw(payload)

        page_items = payload.get('items')
        if isinstance(page_items, list):
            items.extend(item for item in page_items if isinstance(item, dict))

        pages = payload.get('pages')
        if not isinstance(pages, int):
            break
        page += 1
        if page >= pages:
            break

    return items, pages_loaded, raw_total


def _extract_collection_entries(collection: dict) -> list[dict]:
    raw_items = collection.get('items')
    if isinstance(raw_items, list) and raw_items and all(isinstance(item, dict) for item in raw_items):
        return [item for item in raw_items if isinstance(item, dict)]

    sub_collections = collection.get('sub_collections')
    if isinstance(sub_collections, list) and sub_collections:
        return [item for item in sub_collections if isinstance(item, dict)]
    return [collection]


def _extract_collection_urls(payload: dict) -> list[str]:
    collections = payload.get('collections')
    if not isinstance(collections, list):
        return []

    urls: list[str] = []
    for collection in collections:
        if not isinstance(collection, dict):
            continue
        for entry in _extract_collection_entries(collection):
            for key in ('url', 'items_url', 'negotiations_url'):
                value = entry.get(key)
                if isinstance(value, str) and value:
                    urls.append(value)
    return urls


def _normalize_hh_url_to_path(url_or_path: str) -> str | None:
    if not url_or_path:
        return None
    if url_or_path.startswith('http://') or url_or_path.startswith('https://'):
        parsed = urlparse(url_or_path)
        if not parsed.path:
            return None
        return f"{parsed.path}{f'?{parsed.query}' if parsed.query else ''}"
    return url_or_path if url_or_path.startswith('/') else f'/{url_or_path}'


async def _fetch_followup_negotiations_from_collections(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    vacancy_id: str,
    payload: dict,
) -> list[dict]:
    collected: list[dict] = []
    seen_details: set[str] = set()

    for url_or_path in _extract_collection_urls(payload):
        path = _normalize_hh_url_to_path(url_or_path)
        if not path:
            continue
        page = 0
        per_page = 50
        while True:
            try:
                page_payload = await _hh_get(
                    client,
                    path.split('?', 1)[0],
                    access_token=access_token,
                    params={
                        **({'vacancy_id': vacancy_id} if 'vacancy_id=' not in path else {}),
                        **_extract_query_params_from_path(path),
                        'page': str(page),
                        'per_page': str(per_page),
                    },
                    allow_404=True,
                )
            except HTTPException:
                break
            if page_payload.get('_status_code') == 404:
                break

            page_items = page_payload.get('items') if isinstance(page_payload.get('items'), list) else []
            if not page_items:
                break

            for item in page_items:
                if not isinstance(item, dict):
                    continue
                if _is_real_response_item(item):
                    collected.append(item)
                    continue
                detail_path = _normalize_hh_url_to_path(
                    str(item.get('negotiation_url') or item.get('url') or '')
                )
                if not detail_path or detail_path in seen_details:
                    continue
                seen_details.add(detail_path)
                try:
                    detail_payload = await _hh_get(client, detail_path, access_token=access_token, allow_404=True)
                except HTTPException:
                    continue
                if detail_payload.get('_status_code') == 404:
                    continue
                if _is_real_response_item(detail_payload):
                    collected.append(detail_payload)

            pages = page_payload.get('pages')
            if not isinstance(pages, int):
                break
            page += 1
            if page >= pages:
                break

    return collected


def _extract_query_params_from_path(path: str) -> dict[str, str]:
    if '?' not in path:
        return {}
    query = path.split('?', 1)[1]
    params: dict[str, str] = {}
    for chunk in query.split('&'):
        if not chunk:
            continue
        if '=' in chunk:
            key, value = chunk.split('=', 1)
            params[key] = value
        else:
            params[chunk] = ''
    return params


def _extract_summary_by_state(payload: dict, *, state_names: dict[str, str] | None = None) -> list[dict[str, object]]:
    collections = payload.get('collections')
    if not isinstance(collections, list):
        return []

    summary: list[dict[str, object]] = []
    for collection in collections:
        if not isinstance(collection, dict):
            continue

        for entry in _extract_collection_entries(collection):
            state = entry.get('id')
            counters = entry.get('counters') if isinstance(entry.get('counters'), dict) else {}
            count_value = counters.get('total')
            if not isinstance(count_value, int):
                count_value = 0

            state_id = str(state) if state is not None else ''
            state_name = str(entry.get('name', '')) if entry.get('name') is not None else ''
            if not state_name and state_names and state_id in state_names:
                state_name = state_names[state_id]
            summary.append(
                {
                    'state': state_id,
                    'state_name': state_name,
                    'count': count_value,
                }
            )
    return summary


def _extract_response_dedupe_key(item: dict) -> str:
    for key in ('id', 'response_id', 'negotiation_id'):
        value = item.get(key)
        if value is not None:
            raw = str(value).strip()
            if raw:
                return f'{key}:{raw}'

    topic = item.get('topic')
    if isinstance(topic, dict):
        topic_id = topic.get('id')
        if topic_id is not None:
            raw = str(topic_id).strip()
            if raw:
                return f'topic_id:{raw}'

    return f'fallback:{id(item)}'


def _is_real_response_item(item: object) -> bool:
    if not isinstance(item, dict):
        return False

    has_id = item.get('id') is not None
    if not has_id:
        return False

    has_applicant = isinstance(item.get('applicant'), dict)
    has_resume = isinstance(item.get('resume'), dict)
    if has_applicant or has_resume:
        return True

    state = item.get('state') if isinstance(item.get('state'), dict) else item.get('status') if isinstance(item.get('status'), dict) else {}
    has_state = isinstance(state.get('id'), str) or isinstance(state.get('name'), str)
    return has_state




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


def _normalize_vacancy(vacancy: dict, *, archived: bool) -> dict[str, object]:
    return {
        'id': str(vacancy.get('id', '')),
        'name': str(vacancy.get('name', '')),
        'normalized_status': 'Архивная' if archived else 'Активная',
        'published_at': str(vacancy.get('published_at')) if vacancy.get('published_at') else None,
        'archived_at': str(vacancy.get('archived_at')) if vacancy.get('archived_at') else None,
        'responses_count': _extract_responses_count(vacancy),
    }


def _extract_responses_count(vacancy: dict) -> int:
    counters = vacancy.get('counters')
    if isinstance(counters, dict):
        for key in ('responses', 'new_responses', 'all_responses'):
            value = counters.get(key)
            if isinstance(value, int):
                return value

    for key in ('responses_count', 'response_count', 'responses'):
        value = vacancy.get(key)
        if isinstance(value, int):
            return value

    return 0


def _normalize_response(item: dict) -> dict[str, object | None]:
    applicant = item.get('applicant') if isinstance(item.get('applicant'), dict) else {}
    candidate = item.get('candidate') if isinstance(item.get('candidate'), dict) else {}
    resume = item.get('resume') if isinstance(item.get('resume'), dict) else {}
    salary = resume.get('salary') if isinstance(resume.get('salary'), dict) else {}
    state = item.get('state') if isinstance(item.get('state'), dict) else item.get('status') if isinstance(item.get('status'), dict) else {}

    amount = salary.get('amount') or salary.get('from') or salary.get('to')
    currency = salary.get('currency') if isinstance(salary.get('currency'), str) else None

    expected_salary: str | None = None
    if isinstance(amount, (int, float)):
        expected_salary = str(int(amount))
    elif isinstance(amount, str):
        expected_salary = amount
    if expected_salary and currency:
        expected_salary = f'{expected_salary} {currency}'

    area = resume.get('area') if isinstance(resume.get('area'), dict) else applicant.get('area') if isinstance(applicant.get('area'), dict) else {}
    contact = item.get('contact') if isinstance(item.get('contact'), dict) else applicant.get('contact') if isinstance(applicant.get('contact'), dict) else {}
    phones = contact.get('phones') if isinstance(contact.get('phones'), list) else applicant.get('phones') if isinstance(applicant.get('phones'), list) else []

    phone: str | None = None
    for phone_item in phones:
        if isinstance(phone_item, dict):
            phone_value = phone_item.get('number') or phone_item.get('formatted')
            if isinstance(phone_value, str) and phone_value:
                phone = phone_value
                break
        elif isinstance(phone_item, str) and phone_item:
            phone = phone_item
            break

    email = contact.get('email') if isinstance(contact.get('email'), str) else applicant.get('email') if isinstance(applicant.get('email'), str) else None
    age = resume.get('age') if isinstance(resume.get('age'), int) else applicant.get('age') if isinstance(applicant.get('age'), int) else None
    resume_url = resume.get('alternate_url') if isinstance(resume.get('alternate_url'), str) else resume.get('url') if isinstance(resume.get('url'), str) else None

    state_id = state.get('id') if isinstance(state.get('id'), str) else None
    state_name = (
        item.get('state_name') if isinstance(item.get('state_name'), str) else state.get('name') if isinstance(state.get('name'), str) else None
    )

    return {
        'response_id': str(item.get('id', '')),
        'candidate_name': _extract_candidate_name(item, applicant, candidate, resume),
        'resume_title': resume.get('title') if isinstance(resume.get('title'), str) else None,
        'age': age,
        'expected_salary': expected_salary,
        'location': area.get('name') if isinstance(area.get('name'), str) else None,
        'response_created_at': str(item.get('created_at')) if item.get('created_at') else None,
        'cover_letter': item.get('cover_letter') if isinstance(item.get('cover_letter'), str) else item.get('message') if isinstance(item.get('message'), str) else None,
        'status': _extract_status_label(item, state),
        'state': state_id,
        'state_name': state_name,
        'resume_url': resume_url,
        'phone': phone,
        'email': email,
    }


def _extract_candidate_name(item: dict, applicant: dict, candidate: dict, resume: dict) -> str | None:
    direct_candidates: list[object] = [
        applicant.get('full_name'),
        applicant.get('name'),
        candidate.get('full_name'),
        candidate.get('name'),
        resume.get('full_name'),
    ]

    contact = item.get('contact') if isinstance(item.get('contact'), dict) else {}
    if isinstance(contact, dict):
        direct_candidates.append(contact.get('full_name'))
        direct_candidates.append(contact.get('name'))

    owner = resume.get('owner') if isinstance(resume.get('owner'), dict) else {}
    if isinstance(owner, dict):
        direct_candidates.append(owner.get('full_name'))
        direct_candidates.append(owner.get('name'))

    for candidate in direct_candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    combined_name_sources: list[tuple[object, object]] = [
        (applicant.get('first_name'), applicant.get('last_name')),
        (candidate.get('first_name'), candidate.get('last_name')),
        (resume.get('first_name'), resume.get('last_name')),
    ]
    if isinstance(owner, dict):
        combined_name_sources.append((owner.get('first_name'), owner.get('last_name')))
    if isinstance(contact, dict):
        combined_name_sources.append((contact.get('first_name'), contact.get('last_name')))

    for first_name_raw, last_name_raw in combined_name_sources:
        first_name = first_name_raw.strip() if isinstance(first_name_raw, str) else ''
        last_name = last_name_raw.strip() if isinstance(last_name_raw, str) else ''
        full_name = ' '.join(part for part in (first_name, last_name) if part)
        if full_name:
            return full_name

    return None


def _extract_status_label(item: dict, state: dict) -> str | None:
    state_name = item.get('state_name') if isinstance(item.get('state_name'), str) else item.get('status_name') if isinstance(item.get('status_name'), str) else None
    if state_name:
        return state_name

    raw_name = state.get('name') if isinstance(state.get('name'), str) else None
    if raw_name and raw_name.strip():
        return raw_name

    state_id = state.get('id') if isinstance(state.get('id'), str) else None
    return state_id or raw_name
