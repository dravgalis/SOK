from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()

HH_API_BASE = 'https://api.hh.ru'
logger = logging.getLogger(__name__)
STATE_ALIAS_RE = re.compile(r'^(?P<base>[a-z_]+)_\d+$')


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
    per_page: int = Query(default=25, ge=1, le=200),
    all: bool = Query(default=False),
) -> dict[str, object]:
    access_token = _require_access_token(request)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            responses_payload = await _fetch_all_responses(client, access_token=access_token, vacancy_id=vacancy_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception('Unexpected error while loading vacancy responses: vacancy_id=%s', vacancy_id)
        raise HTTPException(status_code=502, detail='Failed to load vacancy responses from HH API.') from exc

    all_items = responses_payload.get('items')
    if not isinstance(all_items, list):
        all_items = []
    total = len(all_items)

    if all:
        resolved_page = 1
        effective_per_page = total if total > 0 else per_page
        pages = 1
        paginated_items = all_items
    else:
        effective_per_page = per_page
        pages = max((total + per_page - 1) // per_page, 1)
        resolved_page = min(page, pages)
        start_index = (resolved_page - 1) * per_page
        end_index = start_index + per_page
        paginated_items = all_items[start_index:end_index]

    return {
        'vacancy_id': vacancy_id,
        'items': paginated_items,
        'total': total,
        'count': total,
        'loaded_count': responses_payload.get('loaded_count', total),
        'hh_total': responses_payload.get('hh_total', 0),
        'has_gap': responses_payload.get('has_gap', False),
        'gap_reason': responses_payload.get('gap_reason'),
        'page': resolved_page,
        'per_page': effective_per_page,
        'pages': pages,
        'summary_total_raw': responses_payload.get('summary_total_raw', 0),
        'state_alias_groups': responses_payload.get('state_alias_groups', []),
        'debug': responses_payload.get('debug', {}),
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

    try:
        response = await client.get(
            url,
            headers={'Authorization': f'Bearer {access_token}'},
            params=params,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f'HH API request failed on {path}.') from exc

    logger.info('HH response debug: url=%s status_code=%s', url, response.status_code)

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail='Unauthorized')

    if allow_404 and response.status_code == 404:
        return {'_status_code': 404}

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f'HH API error on {path}: {response.text}') from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f'HH API returned invalid JSON for {path}.') from exc

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
    vacancy_payload = await _hh_get(client, f'/vacancies/{vacancy_id}', access_token=access_token, allow_404=True)
    hh_total_from_vacancy = _extract_responses_count(vacancy_payload) if vacancy_payload.get('_status_code') != 404 else 0

    seed_payload = await _hh_get(
        client,
        '/negotiations',
        access_token=access_token,
        params={
            'vacancy_id': vacancy_id,
            'status': 'any',
            'page': '0',
            'per_page': '1',
            'all': 'true',
        },
        allow_404=True,
    )
    if seed_payload.get('_status_code') == 404:
        seed_payload = {}

    discovered_states_raw, discovered_states_normalized, state_names = await _discover_response_states(
        client,
        access_token=access_token,
        vacancy_id=vacancy_id,
        seed_payload=seed_payload,
    )

    states_processed_raw: list[str] = []
    states_processed_normalized: list[str] = []
    raw_items: list[dict] = []
    seen_raw_keys: set[str] = set()
    duplicates_skipped = 0

    for state in discovered_states_normalized:
        params = {'status': state} if state else {}
        variant_items, variant_pages_loaded, variant_raw_total, _, _ = await _fetch_negotiations_by_params(
            client,
            access_token=access_token,
            vacancy_id=vacancy_id,
            params=params,
        )
        matching_raw_states = [raw for raw in discovered_states_raw if _normalize_state_alias(raw) == state]
        state_raw = matching_raw_states[0] if matching_raw_states else state
        states_processed_raw.append(state_raw or 'no_status')
        states_processed_normalized.append(state or 'no_status')

        added = 0
        for item in variant_items:
            raw_key = _extract_response_dedupe_key(item)
            if raw_key in seen_raw_keys:
                duplicates_skipped += 1
                continue
            seen_raw_keys.add(raw_key)
            raw_items.append(item)
            added += 1

        logger.info(
            'HH responses debug: vacancy_id=%s state=%s fetched=%s added=%s pages_loaded=%s raw_total=%s',
            vacancy_id,
            state,
            len(variant_items),
            added,
            variant_pages_loaded,
            variant_raw_total,
        )

    if 'any' not in discovered_states_normalized:
        fallback_items, variant_pages_loaded, variant_raw_total, _, _ = await _fetch_negotiations_by_params(
            client,
            access_token=access_token,
            vacancy_id=vacancy_id,
            params={'status': 'any'},
        )
        states_processed_raw.append('any')
        states_processed_normalized.append('any')
        for item in fallback_items:
            raw_key = _extract_response_dedupe_key(item)
            if raw_key in seen_raw_keys:
                duplicates_skipped += 1
                continue
            seen_raw_keys.add(raw_key)
            raw_items.append(item)
        logger.info(
            'HH responses debug: vacancy_id=%s state=%s fetched=%s pages_loaded=%s raw_total=%s',
            vacancy_id,
            'any',
            len(fallback_items),
            variant_pages_loaded,
            variant_raw_total,
        )

    unique_items: list[dict[str, object | None]] = []
    seen_response_ids: set[str] = set()
    raw_items_without_id = 0
    duplicate_items = 0

    for item in raw_items:
        normalized_item = _normalize_response(item)
        response_id = normalized_item.get('response_id')
        if not isinstance(response_id, str) or not response_id:
            raw_items_without_id += 1
            continue
        if response_id in seen_response_ids:
            duplicate_items += 1
            continue
        seen_response_ids.add(response_id)
        unique_items.append(normalized_item)

    logger.info(
        'HH responses debug: vacancy_id=%s raw_items=%s unique_items=%s duplicates=%s missing_response_id=%s sample_ids=%s',
        vacancy_id,
        len(raw_items),
        len(unique_items),
        duplicate_items,
        raw_items_without_id,
        list(seen_response_ids)[:10],
    )

    summary_by_state = _extract_summary_by_state(seed_payload, state_names=state_names)
    summary_counts_map, _ = _aggregate_summary_by_state(summary_by_state)
    summary_total = sum(summary_counts_map.values())
    hh_total_raw = _extract_hh_total_raw(seed_payload)
    hh_total = hh_total_from_vacancy if hh_total_from_vacancy > 0 else (summary_total if summary_total > 0 else hh_total_raw)
    loaded_count = len(unique_items)
    has_gap = hh_total > 0 and loaded_count < hh_total
    collection_failure = hh_total > 0 and loaded_count == 0
    visibility_gap = has_gap and not collection_failure

    return {
        'items': unique_items,
        'loaded_count': loaded_count,
        'hh_total': hh_total,
        'has_gap': has_gap,
        'gap_reason': (
            'HH API returns fewer detailed negotiations than vacancy counter (permissions / hidden / archived)'
            if has_gap
            else None
        ),
        'summary_total_raw': summary_total,
        'state_alias_groups': [],
        'debug': {
            'states_processed': states_processed_normalized,
            'states_processed_raw': states_processed_raw,
            'states_processed_normalized': states_processed_normalized,
            'discovered_states_raw': discovered_states_raw,
            'discovered_states_normalized': discovered_states_normalized,
            'duplicates_skipped': duplicates_skipped + duplicate_items,
            'missing_items': max(hh_total - loaded_count, 0),
            'summary_total': summary_total,
            'hh_total_raw': hh_total_raw,
            'visibility_gap': visibility_gap,
            'collection_failure': collection_failure,
        },
    }


def _count_items_by_state(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        state = _extract_item_state_id(item)
        logical_state = _normalize_state_alias(state)
        counts[logical_state] = counts.get(logical_state, 0) + 1
    return counts


def _extract_item_state_id(item: dict) -> str:
    state = item.get('state') if isinstance(item.get('state'), dict) else item.get('status') if isinstance(item.get('status'), dict) else {}
    state_id = state.get('id')
    if isinstance(state_id, str) and state_id:
        return state_id
    fallback = item.get('state_name') if isinstance(item.get('state_name'), str) and item.get('state_name') else 'unknown'
    return fallback


def _aggregate_summary_by_state(
    summary_by_state: list[dict[str, object]],
    *,
    normalize_aliases: bool = True,
) -> tuple[dict[str, int], dict[str, str]]:
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    has_aliases: dict[str, bool] = {}
    for row in summary_by_state:
        state = row.get('state')
        if not isinstance(state, str) or not state:
            state = 'unknown'
        logical_state = _normalize_state_alias(state) if normalize_aliases else state
        count = row.get('count')
        count_value = count if isinstance(count, int) else 0
        if normalize_aliases:
            if logical_state not in counts:
                counts[logical_state] = count_value
            elif _is_state_alias(state) or has_aliases.get(logical_state, False):
                counts[logical_state] = max(counts[logical_state], count_value)
            else:
                counts[logical_state] = counts[logical_state] + count_value
            has_aliases[logical_state] = has_aliases.get(logical_state, False) or _is_state_alias(state)
        else:
            counts[logical_state] = counts.get(logical_state, 0) + count_value
        state_name = row.get('state_name')
        if isinstance(state_name, str) and state_name:
            names[logical_state] = state_name
    return counts, names


def _build_state_diagnostics(
    *,
    summary_counts_map: dict[str, int],
    fetched_counts_map: dict[str, int],
    summary_names_map: dict[str, str],
    state_names: dict[str, str],
    state_fetch_diagnostics: list[dict[str, object]],
) -> list[dict[str, object]]:
    fetch_by_logical_state: dict[str, dict[str, object]] = {}
    for row in state_fetch_diagnostics:
        state = row.get('state')
        if not isinstance(state, str) or not state:
            continue
        logical_state = _normalize_state_alias(state)
        existing = fetch_by_logical_state.get(logical_state)
        state_total_raw = row.get('state_total_raw')
        state_total_raw_value = state_total_raw if isinstance(state_total_raw, int) else None
        fetched_raw_count = row.get('fetched_raw_count')
        fetched_raw_count_value = fetched_raw_count if isinstance(fetched_raw_count, int) else 0
        if existing is None:
            fetch_by_logical_state[logical_state] = {
                'state_total_raw': state_total_raw_value,
                'fetched_raw_count': fetched_raw_count_value,
            }
            continue
        existing_total = existing.get('state_total_raw')
        if isinstance(existing_total, int) and isinstance(state_total_raw_value, int):
            existing['state_total_raw'] = max(existing_total, state_total_raw_value)
        elif isinstance(state_total_raw_value, int):
            existing['state_total_raw'] = state_total_raw_value
        existing['fetched_raw_count'] = max(int(existing.get('fetched_raw_count', 0)), fetched_raw_count_value)

    diagnostics: list[dict[str, object]] = []
    all_states = sorted(set(summary_counts_map) | set(fetched_counts_map))
    for state in all_states:
        expected_count = summary_counts_map.get(state, 0)
        fetched_count = fetched_counts_map.get(state, 0)
        state_fetch = fetch_by_logical_state.get(state, {})
        hh_state_total_raw = state_fetch.get('state_total_raw')
        fetched_raw_count = state_fetch.get('fetched_raw_count', 0)
        api_limitation_suspected = isinstance(hh_state_total_raw, int) and hh_state_total_raw < expected_count
        diagnostics.append(
            {
                'state': state,
                'state_name': summary_names_map.get(state) or state_names.get(state) or state,
                'expected_count': expected_count,
                'fetched_count': fetched_count,
                'missing_count': max(expected_count - fetched_count, 0),
                'fetched_raw_count': fetched_raw_count,
                'hh_state_total_raw': hh_state_total_raw if isinstance(hh_state_total_raw, int) else None,
                'api_limitation_suspected': api_limitation_suspected,
            }
        )
    return diagnostics


def _enrich_collection_diagnostics(
    *,
    raw_collection_diagnostics: list[dict[str, object]],
    summary_counts_map: dict[str, int],
    fetched_counts_map: dict[str, int],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for row in raw_collection_diagnostics:
        state = row.get('state')
        if not isinstance(state, str) or not state:
            state = 'unknown'
        logical_state = _normalize_state_alias(state)
        summary_count = summary_counts_map.get(logical_state, 0)
        fetched_detailed_count = fetched_counts_map.get(logical_state, 0)
        enriched.append(
            {
                **row,
                'logical_state': logical_state,
                'summary_count': summary_count,
                'fetched_detailed_count': fetched_detailed_count,
                'missing_count': max(summary_count - fetched_detailed_count, 0),
            }
        )
    return enriched


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
) -> tuple[list[str], list[str], dict[str, str]]:
    raw_states: list[str] = ['any']
    normalized_states: list[str] = ['any']
    state_names = _extract_state_names_from_collections(seed_payload)
    for state in _extract_states_from_collections(seed_payload):
        if state not in raw_states:
            raw_states.append(state)
        normalized_state = _normalize_state_alias(state)
        if normalized_state and normalized_state not in normalized_states:
            normalized_states.append(normalized_state)
            if state in state_names and normalized_state not in state_names:
                state_names[normalized_state] = state_names[state]

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
            if state_id not in raw_states:
                raw_states.append(state_id)
            normalized_state = _normalize_state_alias(state_id)
            if normalized_state and normalized_state not in normalized_states:
                normalized_states.append(normalized_state)
            if state_name:
                state_names[state_id] = state_name
                if normalized_state and normalized_state not in state_names:
                    state_names[normalized_state] = state_name

    return raw_states, normalized_states, state_names


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
    expected_count_hint: int | None = None,
) -> tuple[list[dict], int, int | None, list[dict[str, int]], list[str]]:
    return await _fetch_negotiations_by_params(
        client,
        access_token=access_token,
        vacancy_id=vacancy_id,
        params={'status': state},
        expected_count_hint=expected_count_hint,
    )


async def _fetch_missing_negotiations_fallback(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    vacancy_id: str,
    expected_total: int,
    existing_items: list[dict],
    existing_dedupe_keys: set[str],
) -> tuple[list[dict], list[dict[str, object]]]:
    fallback_variants: list[dict[str, str]] = [
        {'status': 'any', 'archived': 'true'},
        {'status': 'any', 'hidden': 'true'},
        {'status': 'any', 'archived': 'true', 'hidden': 'true'},
    ]
    collected: list[dict] = []
    diagnostics: list[dict[str, object]] = []

    for params in fallback_variants:
        items, pages_loaded, raw_total, page_counts, _ = await _fetch_negotiations_by_params(
            client,
            access_token=access_token,
            vacancy_id=vacancy_id,
            params=params,
        )
        added = 0
        duplicates = 0
        for item in items:
            dedupe_key = _extract_response_dedupe_key(item)
            if dedupe_key in existing_dedupe_keys:
                duplicates += 1
                continue
            existing_dedupe_keys.add(dedupe_key)
            existing_items.append(item)
            collected.append(item)
            added += 1
        current_real_count = len([item for item in existing_items if _is_real_response_item(item)])
        diagnostics.append(
            {
                'params': params,
                'pages_loaded': pages_loaded,
                'raw_total': raw_total,
                'fetched_raw_count': len(items),
                'added_after_dedupe': added,
                'duplicates_skipped': duplicates,
                'page_counts': page_counts,
                'current_real_count': current_real_count,
            }
        )
        if current_real_count >= expected_total:
            break

    return collected, diagnostics


async def _fetch_negotiations_by_params(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    vacancy_id: str,
    params: dict[str, str],
    expected_count_hint: int | None = None,
) -> tuple[list[dict], int, int | None, list[dict[str, int]], list[str]]:
    page = 0
    per_page = 50
    pages_loaded = 0
    items: list[dict] = []
    raw_total: int | None = None
    page_counts: list[dict[str, int]] = []
    raw_ids: list[str] = []

    while True:
        normalized_params = dict(params)
        status = normalized_params.get('status')
        if isinstance(status, str) and status:
            normalized_params['status'] = _normalize_state_alias(status)
        request_params = {
            'vacancy_id': vacancy_id,
            **normalized_params,
            'page': str(page),
            'per_page': str(per_page),
            'all': 'true',
        }
        payload = await _hh_get(
            client,
            '/negotiations',
            access_token=access_token,
            params=request_params,
            allow_404=True,
        )
        if payload.get('_status_code') == 404:
            logger.info('HH negotiations debug: vacancy_id=%s params=%s status=404', vacancy_id, request_params)
            break

        pages_loaded += 1
        raw_total = _extract_hh_total_raw(payload)

        page_items = payload.get('items')
        if isinstance(page_items, list):
            normalized_page_items = [item for item in page_items if isinstance(item, dict)]
            items.extend(normalized_page_items)
            page_counts.append({'page': page, 'count': len(normalized_page_items)})
            for item in normalized_page_items:
                raw_ids.append(_extract_response_dedupe_key(item))

        pages = payload.get('pages')
        total_hint = raw_total if isinstance(raw_total, int) and raw_total > 0 else None
        pages_by_total = ((total_hint + per_page - 1) // per_page) if total_hint else None
        pages_by_expected = ((expected_count_hint + per_page - 1) // per_page) if isinstance(expected_count_hint, int) and expected_count_hint > 0 else None
        pages_hint = pages if isinstance(pages, int) and pages > 0 else None
        max_pages_hint = max(
            value for value in (pages_hint, pages_by_total, pages_by_expected) if isinstance(value, int) and value > 0
        ) if any(isinstance(value, int) and value > 0 for value in (pages_hint, pages_by_total, pages_by_expected)) else None

        page += 1
        logger.info(
            'HH negotiations debug: vacancy_id=%s params=%s page_items=%s pages_loaded=%s raw_total=%s',
            vacancy_id,
            request_params,
            len(page_items) if isinstance(page_items, list) else 0,
            pages_loaded,
            raw_total,
        )
        if max_pages_hint is not None and page >= max_pages_hint:
            break
        if not page_items:
            break
        if page >= 200:
            break

    return items, pages_loaded, raw_total, page_counts, raw_ids


def _extract_collection_entries(collection: dict) -> list[dict]:
    entries: list[dict] = []
    stack: list[dict] = [collection]
    seen_ids: set[int] = set()

    while stack:
        current = stack.pop()
        marker = id(current)
        if marker in seen_ids:
            continue
        seen_ids.add(marker)
        entries.append(current)

        for key in ('items', 'sub_collections'):
            nested = current.get(key)
            if not isinstance(nested, list):
                continue
            for item in nested:
                if isinstance(item, dict):
                    stack.append(item)

    return entries


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
) -> tuple[list[dict], dict[str, object]]:
    collected: list[dict] = []
    seen_details: set[str] = set()
    errors: list[str] = []
    urls_processed = 0
    pages_loaded = 0
    collection_diagnostics: list[dict[str, object]] = []
    collection_url_state_index = _build_collection_url_state_index(payload)

    for url_or_path in _extract_collection_urls(payload):
        path = _normalize_hh_url_to_path(url_or_path)
        if not path:
            continue
        urls_processed += 1
        indexed_state = collection_url_state_index.get(_strip_pagination_query(path), {})
        collection_state_raw = indexed_state.get('state') or _extract_collection_state_from_path(path)
        collection_state = collection_state_raw if isinstance(collection_state_raw, str) and collection_state_raw else 'unknown'
        collection_name_raw = indexed_state.get('state_name') or _extract_collection_name_by_state(payload, collection_state)
        collection_name = collection_name_raw if isinstance(collection_name_raw, str) and collection_name_raw else collection_state
        collection_items_total = 0
        collection_added_after_dedupe_hint = 0
        collection_page_counts: list[dict[str, int]] = []
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
            except HTTPException as exc:
                errors.append(f'{path}: {exc.status_code}')
                break
            if page_payload.get('_status_code') == 404:
                break

            pages_loaded += 1
            page_items = page_payload.get('items') if isinstance(page_payload.get('items'), list) else []
            collection_items_total += len(page_items)
            collection_page_counts.append({'page': page, 'count': len(page_items)})

            for item in page_items:
                if not isinstance(item, dict):
                    continue
                if _is_real_response_item(item):
                    collected.append(item)
                    collection_added_after_dedupe_hint += 1
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
                    collection_added_after_dedupe_hint += 1

            pages = page_payload.get('pages')
            if not isinstance(pages, int):
                break
            page += 1
            if page >= pages:
                break

        collection_diagnostics.append(
            {
                'state': collection_state,
                'logical_state': _normalize_state_alias(collection_state),
                'state_name': collection_name,
                'url': path,
                'fetched_raw_count': collection_items_total,
                'page_counts': collection_page_counts,
                'added_raw_candidates': collection_added_after_dedupe_hint,
            }
        )

    return collected, {
        'urls_processed': urls_processed,
        'pages_loaded': pages_loaded,
        'errors': errors,
        'collection_diagnostics': collection_diagnostics,
    }


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


def _extract_collection_state_from_path(path: str) -> str:
    params = _extract_query_params_from_path(path)
    state = params.get('status') or params.get('state') or ''
    return state if state else 'unknown'


def _strip_pagination_query(path: str) -> str:
    params = _extract_query_params_from_path(path)
    filtered_params = {key: value for key, value in params.items() if key not in {'page', 'per_page'}}
    base = path.split('?', 1)[0]
    if not filtered_params:
        return base
    query = '&'.join(f'{key}={value}' for key, value in sorted(filtered_params.items()))
    return f'{base}?{query}'


def _build_collection_url_state_index(payload: dict) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    collections = payload.get('collections')
    if not isinstance(collections, list):
        return index

    for collection in collections:
        if not isinstance(collection, dict):
            continue
        for entry in _extract_collection_entries(collection):
            state = entry.get('id')
            state_name = entry.get('name')
            if not isinstance(state, str) or not state:
                continue
            for key in ('url', 'items_url', 'negotiations_url'):
                raw_url = entry.get(key)
                if not isinstance(raw_url, str) or not raw_url:
                    continue
                normalized_path = _normalize_hh_url_to_path(raw_url)
                if not normalized_path:
                    continue
                index[_strip_pagination_query(normalized_path)] = {
                    'state': state,
                    'state_name': state_name if isinstance(state_name, str) else state,
                }
    return index


def _extract_collection_name_by_state(payload: dict, state: str) -> str:
    if not state or state == 'unknown':
        return state
    for row in _extract_summary_by_state(payload):
        row_state = row.get('state')
        if isinstance(row_state, str) and row_state == state:
            row_name = row.get('state_name')
            if isinstance(row_name, str) and row_name:
                return row_name
    return state


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


def _normalize_state_alias(state: str) -> str:
    match = STATE_ALIAS_RE.match(state)
    if not match:
        return state
    base = match.group('base')
    return base if base else state


def _is_state_alias(state: str) -> bool:
    return STATE_ALIAS_RE.match(state) is not None


def _build_state_alias_groups(
    *,
    summary_counts_raw_map: dict[str, int],
    summary_names_map: dict[str, str],
    fetched_counts_map: dict[str, int],
) -> list[dict[str, object]]:
    grouped_states: dict[str, list[str]] = {}
    all_states = set(summary_counts_raw_map) | set(fetched_counts_map)
    for state in all_states:
        logical_state = _normalize_state_alias(state)
        grouped_states.setdefault(logical_state, []).append(state)

    groups: list[dict[str, object]] = []
    for logical_state in sorted(grouped_states):
        aliases = sorted(grouped_states[logical_state])
        summary_counts_by_alias = {alias: summary_counts_raw_map.get(alias, 0) for alias in aliases}
        groups.append(
            {
                'logical_state': logical_state,
                'state_name': summary_names_map.get(logical_state) or logical_state,
                'aliases': aliases,
                'summary_counts_by_alias': summary_counts_by_alias,
                'normalized_summary_count': max(summary_counts_by_alias.values()) if summary_counts_by_alias else 0,
                'fetched_detailed_count': fetched_counts_map.get(logical_state, 0),
            }
        )
    return groups


def _extract_response_dedupe_key(item: dict) -> str:
    response_id = _extract_response_id(item)
    if response_id:
        return f'response_id:{response_id}'

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


def _extract_response_id(item: dict) -> str | None:
    for key in ('id', 'response_id', 'negotiation_id'):
        value = item.get(key)
        if value is None:
            continue
        raw = str(value).strip()
        if raw:
            return raw

    topic = item.get('topic')
    if isinstance(topic, dict):
        topic_id = topic.get('id')
        if topic_id is not None:
            raw = str(topic_id).strip()
            if raw:
                return raw

    return None


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
        'response_id': _extract_response_id(item) or '',
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

    for candidate_name in direct_candidates:
        if isinstance(candidate_name, str) and candidate_name.strip():
            return candidate_name.strip()

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
