from __future__ import annotations

import asyncio
import logging
import re
from html import unescape
from urllib.parse import urlparse
from urllib.parse import unquote

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
    all_items.sort(key=_response_sort_key, reverse=True)
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
    vacancy_criteria = _extract_vacancy_criteria(vacancy_payload if vacancy_payload.get('_status_code') != 404 else {})

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

    direct_items, direct_pages_loaded, direct_raw_total, direct_page_counts, _ = await _fetch_negotiations_by_params(
        client,
        access_token=access_token,
        vacancy_id=vacancy_id,
        params={},
        expected_count_hint=hh_total_from_vacancy if hh_total_from_vacancy > 0 else None,
    )

    collection_items, collection_debug = await _fetch_followup_negotiations_from_collections(
        client,
        access_token=access_token,
        vacancy_id=vacancy_id,
        payload=seed_payload,
    )

    merged_raw_items: list[dict] = []
    seen_raw_keys: set[str] = set()
    duplicates_skipped = 0

    for source_items in (direct_items, collection_items):
        for item in source_items:
            raw_key = _extract_response_dedupe_key(item)
            if raw_key in seen_raw_keys:
                duplicates_skipped += 1
                continue
            seen_raw_keys.add(raw_key)
            merged_raw_items.append(item)

    unique_items: list[dict[str, object | None]] = []
    seen_response_ids: set[str] = set()
    raw_items_without_id = 0
    duplicate_items = 0
    resumes_profiles = await _fetch_resumes_profiles(client, access_token=access_token, items=merged_raw_items)

    for item in merged_raw_items:
        resume_id = _extract_resume_id(item)
        resume_profile = resumes_profiles.get(resume_id) if resume_id else None
        normalized_item = _normalize_response(item)
        score, score_breakdown = _score_candidate_against_vacancy(
            vacancy_criteria=vacancy_criteria,
            response_item=item,
            resume_profile=resume_profile if isinstance(resume_profile, dict) else None,
        )
        normalized_item['score'] = score
        normalized_item['score_breakdown'] = score_breakdown
        response_id = normalized_item.get('response_id')
        if not isinstance(response_id, str) or not response_id:
            raw_items_without_id += 1
            continue
        if response_id in seen_response_ids:
            duplicate_items += 1
            continue
        seen_response_ids.add(response_id)
        unique_items.append(normalized_item)

    summary_by_state = _extract_summary_by_state(seed_payload)
    summary_counts_map, _ = _aggregate_summary_by_state(summary_by_state)
    summary_total = sum(summary_counts_map.values())
    hh_total_raw = _extract_hh_total_raw(seed_payload)
    hh_total = hh_total_from_vacancy if hh_total_from_vacancy > 0 else (summary_total if summary_total > 0 else hh_total_raw)
    loaded_count = len(unique_items)

    collection_errors = collection_debug.get('errors', [])
    collection_errors_count = len(collection_errors) if isinstance(collection_errors, list) else 0
    collection_has_candidates = len(collection_items) > 0

    has_gap = hh_total > 0 and loaded_count == 0
    gap_reason = (
        'Не удалось собрать отклики кандидатов ни через /negotiations, ни через collections URLs.'
        if has_gap
        else None
    )

    return {
        'items': unique_items,
        'loaded_count': loaded_count,
        'hh_total': hh_total,
        'has_gap': has_gap,
        'gap_reason': gap_reason,
        'summary_total_raw': summary_total,
        'state_alias_groups': [],
        'debug': {
            'direct_items_count': len(direct_items),
            'direct_pages_loaded': direct_pages_loaded,
            'direct_raw_total': direct_raw_total,
            'direct_page_counts': direct_page_counts,
            'collection_items_count': len(collection_items),
            'collection_urls_processed': collection_debug.get('urls_processed', 0),
            'collection_pages_loaded': collection_debug.get('pages_loaded', 0),
            'collection_errors': collection_errors,
            'collection_errors_count': collection_errors_count,
            'collection_has_candidates': collection_has_candidates,
            'duplicates_skipped': duplicates_skipped + duplicate_items,
            'missing_items': max(hh_total - loaded_count, 0),
            'summary_total': summary_total,
            'hh_total_raw': hh_total_raw,
            'collection_failure': loaded_count == 0,
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
    per_page = 50
    items: list[dict] = []
    raw_total: int | None = None
    page_counts: list[dict[str, int]] = []
    raw_ids: list[str] = []
    normalized_params = dict(params)
    normalized_params['status'] = 'any'

    first_payload = await _hh_get(
        client,
        '/negotiations',
        access_token=access_token,
        params={
            'vacancy_id': vacancy_id,
            **normalized_params,
            'page': '0',
            'per_page': str(per_page),
            'all': 'true',
        },
        allow_404=True,
    )
    if first_payload.get('_status_code') == 404:
        return [], 0, None, [], []

    raw_total = _extract_hh_total_raw(first_payload)
    first_items_raw = first_payload.get('items') if isinstance(first_payload.get('items'), list) else []
    first_items = [item for item in first_items_raw if isinstance(item, dict)]
    items.extend(first_items)
    page_counts.append({'page': 0, 'count': len(first_items)})
    raw_ids.extend(_extract_response_dedupe_key(item) for item in first_items)

    pages_hint = first_payload.get('pages') if isinstance(first_payload.get('pages'), int) else None
    total_hint = raw_total if isinstance(raw_total, int) and raw_total > 0 else None
    pages_by_total = ((total_hint + per_page - 1) // per_page) if total_hint else None
    pages_by_expected = ((expected_count_hint + per_page - 1) // per_page) if isinstance(expected_count_hint, int) and expected_count_hint > 0 else None
    max_pages_hint = max(
        value for value in (pages_hint, pages_by_total, pages_by_expected) if isinstance(value, int) and value > 0
    ) if any(isinstance(value, int) and value > 0 for value in (pages_hint, pages_by_total, pages_by_expected)) else 1
    max_pages_hint = min(max_pages_hint, 200)

    if max_pages_hint > 1:
        page_tasks = [
            _hh_get(
                client,
                '/negotiations',
                access_token=access_token,
                params={
                    'vacancy_id': vacancy_id,
                    **normalized_params,
                    'page': str(page),
                    'per_page': str(per_page),
                    'all': 'true',
                },
                allow_404=True,
            )
            for page in range(1, max_pages_hint)
        ]
        page_payloads = await asyncio.gather(*page_tasks, return_exceptions=True)
        for page, payload in enumerate(page_payloads, start=1):
            if isinstance(payload, Exception):
                continue
            if not isinstance(payload, dict) or payload.get('_status_code') == 404:
                continue
            page_items_raw = payload.get('items') if isinstance(payload.get('items'), list) else []
            page_items = [item for item in page_items_raw if isinstance(item, dict)]
            items.extend(page_items)
            page_counts.append({'page': page, 'count': len(page_items)})
            raw_ids.extend(_extract_response_dedupe_key(item) for item in page_items)

    pages_loaded = len(page_counts)
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
    collection_url_state_index = _build_collection_url_state_index(payload)
    normalized_paths = [_normalize_hh_url_to_path(url_or_path) for url_or_path in _extract_collection_urls(payload)]
    paths = [path for path in normalized_paths if path]

    tasks = [
        _fetch_single_collection_path(
            client,
            access_token=access_token,
            vacancy_id=vacancy_id,
            payload=payload,
            path=path,
            collection_url_state_index=collection_url_state_index,
        )
        for path in paths
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    collected: list[dict] = []
    errors: list[str] = []
    pages_loaded = 0
    collection_diagnostics: list[dict[str, object]] = []
    for result in results:
        if isinstance(result, Exception):
            errors.append(str(result))
            continue
        collected.extend(result['items'])
        pages_loaded += int(result['pages_loaded'])
        errors.extend(result['errors'])
        collection_diagnostics.append(result['diagnostics'])

    return collected, {
        'urls_processed': len(paths),
        'pages_loaded': pages_loaded,
        'errors': errors,
        'collection_diagnostics': collection_diagnostics,
    }


async def _fetch_single_collection_path(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    vacancy_id: str,
    payload: dict,
    path: str,
    collection_url_state_index: dict[str, dict[str, str]],
) -> dict[str, object]:
    indexed_state = collection_url_state_index.get(_strip_pagination_query(path), {})
    collection_state_raw = indexed_state.get('state') or _extract_collection_state_from_path(path)
    collection_state = collection_state_raw if isinstance(collection_state_raw, str) and collection_state_raw else 'unknown'
    collection_name_raw = indexed_state.get('state_name') or _extract_collection_name_by_state(payload, collection_state)
    collection_name = collection_name_raw if isinstance(collection_name_raw, str) and collection_name_raw else collection_state

    per_page = 50
    base_path = path.split('?', 1)[0]
    base_params = {
        **({'vacancy_id': vacancy_id} if 'vacancy_id=' not in path else {}),
        **_extract_query_params_from_path(path),
    }

    errors: list[str] = []
    first_payload = await _hh_get(
        client,
        base_path,
        access_token=access_token,
        params={**base_params, 'page': '0', 'per_page': str(per_page)},
        allow_404=True,
    )
    if first_payload.get('_status_code') == 404:
        return {
            'items': [],
            'pages_loaded': 0,
            'errors': errors,
            'diagnostics': {
                'state': collection_state,
                'logical_state': _normalize_state_alias(collection_state),
                'state_name': collection_name,
                'url': path,
                'fetched_raw_count': 0,
                'page_counts': [],
                'added_raw_candidates': 0,
            },
        }

    pages = first_payload.get('pages') if isinstance(first_payload.get('pages'), int) and first_payload.get('pages') else 1
    page_payloads: list[dict] = [first_payload]
    if pages > 1:
        tasks = [
            _hh_get(
                client,
                base_path,
                access_token=access_token,
                params={**base_params, 'page': str(page), 'per_page': str(per_page)},
                allow_404=True,
            )
            for page in range(1, pages)
        ]
        rest = await asyncio.gather(*tasks, return_exceptions=True)
        for payload_item in rest:
            if isinstance(payload_item, Exception):
                errors.append(str(payload_item))
                continue
            if isinstance(payload_item, dict) and payload_item.get('_status_code') != 404:
                page_payloads.append(payload_item)

    collected: list[dict] = []
    detail_urls: set[str] = set()
    page_counts: list[dict[str, int]] = []
    for page_index, page_payload in enumerate(page_payloads):
        page_items = page_payload.get('items') if isinstance(page_payload.get('items'), list) else []
        page_counts.append({'page': page_index, 'count': len(page_items)})
        for item in page_items:
            if not isinstance(item, dict):
                continue
            if _is_real_response_item(item):
                collected.append(item)
            else:
                detail_path = _normalize_hh_url_to_path(str(item.get('negotiation_url') or item.get('url') or ''))
                if detail_path:
                    detail_urls.add(detail_path)

    if detail_urls:
        detail_tasks = [_hh_get(client, detail_path, access_token=access_token, allow_404=True) for detail_path in sorted(detail_urls)]
        details = await asyncio.gather(*detail_tasks, return_exceptions=True)
        for detail_payload in details:
            if isinstance(detail_payload, Exception):
                continue
            if isinstance(detail_payload, dict) and detail_payload.get('_status_code') != 404 and _is_real_response_item(detail_payload):
                collected.append(detail_payload)

    return {
        'items': collected,
        'pages_loaded': len(page_payloads),
        'errors': errors,
        'diagnostics': {
            'state': collection_state,
            'logical_state': _normalize_state_alias(collection_state),
            'state_name': collection_name,
            'url': path,
            'fetched_raw_count': sum(row['count'] for row in page_counts),
            'page_counts': page_counts,
            'added_raw_candidates': len(collected),
        },
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


def _extract_vacancy_criteria(vacancy_payload: dict) -> dict[str, dict[str, object]]:
    criteria: dict[str, dict[str, object]] = {}

    def add_criterion(
        *,
        criterion_id: str,
        expected: object,
        compare_mode: str,
        importance: str = 'preferred',
        label: str | None = None,
    ) -> None:
        if not _has_meaningful_value(expected):
            return
        criteria[criterion_id] = {
            'criterion': criterion_id,
            'label': label or criterion_id,
            'importance': importance,
            'compare_mode': compare_mode,
            'expected': expected,
        }

    # Явные, доменно-важные поля вакансии
    add_criterion(
        criterion_id='skills',
        expected=_extract_names_from_list(vacancy_payload.get('key_skills') if isinstance(vacancy_payload.get('key_skills'), list) else []),
        compare_mode='token_overlap',
        importance='required',
        label='Навыки',
    )
    add_criterion(
        criterion_id='specialization',
        expected=_extract_names_from_list(vacancy_payload.get('professional_roles') if isinstance(vacancy_payload.get('professional_roles'), list) else []),
        compare_mode='token_overlap',
        importance='required',
        label='Специализация',
    )

    area = vacancy_payload.get('area') if isinstance(vacancy_payload.get('area'), dict) else {}
    location_expected = [
        value
        for value in (
            area.get('name'),
            area.get('id'),
            area.get('parent') if isinstance(area.get('parent'), str) else None,
        )
        if isinstance(value, str) and value.strip()
    ]
    add_criterion(
        criterion_id='location',
        expected=location_expected,
        compare_mode='token_overlap',
        importance='preferred',
        label='Локация',
    )

    salary = vacancy_payload.get('salary') if isinstance(vacancy_payload.get('salary'), dict) else {}
    salary_from = salary.get('from') if isinstance(salary.get('from'), (int, float)) else None
    salary_to = salary.get('to') if isinstance(salary.get('to'), (int, float)) else None
    salary_expected = {
        'from': salary_from,
        'to': salary_to,
        'currency': salary.get('currency') if isinstance(salary.get('currency'), str) else None,
    }
    if salary_from is not None or salary_to is not None:
        add_criterion(
            criterion_id='salary',
            expected=salary_expected,
            compare_mode='salary_range',
            importance='required',
            label='Зарплата',
        )

    experience_values = _extract_single_name(vacancy_payload.get('experience'))
    if experience_values:
        experience_label = experience_values[0]
        min_months, max_months = _parse_experience_range_months(experience_label)
        add_criterion(
            criterion_id='experience',
            expected={
                'label': experience_label,
                'min_months': min_months,
                'max_months': max_months,
            },
            compare_mode='experience_range',
            importance='required',
            label='Опыт',
        )
    add_criterion(
        criterion_id='work_format',
        expected=_normalize_work_formats(_extract_names_from_list(vacancy_payload.get('work_format') if isinstance(vacancy_payload.get('work_format'), list) else [])),
        compare_mode='work_format_match',
        importance='preferred',
        label='Формат работы',
    )
    add_criterion(
        criterion_id='employment_type',
        expected=_extract_single_name(vacancy_payload.get('employment')),
        compare_mode='token_overlap',
        importance='required',
        label='Тип занятости',
    )
    add_criterion(
        criterion_id='language',
        expected=_extract_names_from_list(vacancy_payload.get('languages') if isinstance(vacancy_payload.get('languages'), list) else []),
        compare_mode='token_overlap',
        importance='preferred',
        label='Языки',
    )
    add_criterion(
        criterion_id='formalization',
        expected=_extract_single_name(vacancy_payload.get('driver_license_types'))
        or _extract_single_name(vacancy_payload.get('accept_handicapped'))
        or _extract_single_name(vacancy_payload.get('accept_kids')),
        compare_mode='token_overlap',
        importance='preferred',
        label='Оформление',
    )

    remote_markers: list[str] = []
    for key in ('work_format', 'working_days', 'schedule'):
        value = vacancy_payload.get(key)
        if isinstance(value, str) and value.strip():
            remote_markers.append(value)
        elif isinstance(value, dict):
            name = value.get('name')
            if isinstance(name, str) and name.strip():
                remote_markers.append(name)
    add_criterion(
        criterion_id='remote_mode',
        expected=remote_markers,
        compare_mode='token_overlap',
        importance='preferred',
        label='Удаленка / офис / гибрид',
    )

    # Дополнительные текстовые требования работодателя.
    requirements = vacancy_payload.get('requirements') if isinstance(vacancy_payload.get('requirements'), dict) else {}
    text_requirements: dict[str, str] = {}
    for key, value in requirements.items():
        if isinstance(value, str) and value.strip():
            normalized = _normalize_text(value)
            if normalized:
                text_requirements[key] = normalized
    if text_requirements:
        add_criterion(
            criterion_id='additional_requirements',
            expected=text_requirements,
            compare_mode='text_presence',
            importance='required',
            label='Дополнительные требования',
        )

    return criteria


def _score_candidate_against_vacancy(
    *,
    vacancy_criteria: dict[str, dict[str, object]],
    response_item: dict,
    resume_profile: dict | None = None,
) -> tuple[int | None, list[dict[str, object]]]:
    if not vacancy_criteria:
        return None, []

    criterion_weights = {
        'skills': 18,
        'specialization': 18,
        'location': 10,
        'salary': 14,
        'experience': 16,
        'work_format': 10,
        'employment_type': 12,
        'language': 10,
        'formalization': 8,
        'remote_mode': 8,
        'additional_requirements': 14,
    }

    candidate_profile = _extract_candidate_profile(response_item, resume_profile=resume_profile)
    breakdown: list[dict[str, object]] = []
    total_weight = 0
    earned_weight = 0.0

    for criterion, config in vacancy_criteria.items():
        weight = criterion_weights.get(criterion, 5)
        importance = config.get('importance') if isinstance(config.get('importance'), str) else 'preferred'
        if importance == 'required':
            weight = int(round(weight * 1.5))

        expected = config.get('expected')
        if not expected:
            continue

        compare_mode = config.get('compare_mode') if isinstance(config.get('compare_mode'), str) else 'token_overlap'
        match_ratio, reason = _match_criterion(
            criterion=criterion,
            compare_mode=compare_mode,
            expected=expected,
            candidate_profile=candidate_profile,
        )
        points = round(weight * match_ratio, 2)
        total_weight += weight
        earned_weight += points

        breakdown.append(
            {
                'criterion': criterion,
                'label': config.get('label') if isinstance(config.get('label'), str) else criterion,
                'importance': importance,
                'weight': weight,
                'points': points,
                'max_points': weight,
                'matched': match_ratio >= 0.99,
                'match_ratio': round(match_ratio, 3),
                'reason': reason,
            }
        )

    if total_weight == 0:
        return None, []

    score = int(round((earned_weight / total_weight) * 100))
    return max(0, min(score, 100)), breakdown


def _extract_candidate_profile(item: dict, *, resume_profile: dict | None = None) -> dict[str, object]:
    applicant = item.get('applicant') if isinstance(item.get('applicant'), dict) else {}
    resume = item.get('resume') if isinstance(item.get('resume'), dict) else {}
    resume_profile = resume_profile if isinstance(resume_profile, dict) else {}
    resume_source = resume_profile if resume_profile else resume
    area = resume.get('area') if isinstance(resume.get('area'), dict) else applicant.get('area') if isinstance(applicant.get('area'), dict) else {}
    if isinstance(resume_source.get('area'), dict):
        area = resume_source.get('area')
    salary = resume_source.get('salary') if isinstance(resume_source.get('salary'), dict) else {}
    languages = (
        resume_source.get('language')
        if isinstance(resume_source.get('language'), list)
        else resume_source.get('languages')
        if isinstance(resume_source.get('languages'), list)
        else []
    )
    schedule_names = _extract_names_from_list(resume_source.get('schedules') if isinstance(resume_source.get('schedules'), list) else [])
    employment_names = _extract_names_from_list(resume_source.get('employments') if isinstance(resume_source.get('employments'), list) else [])
    language_names = _extract_names_from_list(languages)
    work_format_names = _extract_names_from_list(
        resume_source.get('work_format') if isinstance(resume_source.get('work_format'), list) else []
    )
    specialization_names = _extract_names_from_list(
        resume_source.get('professional_roles') if isinstance(resume_source.get('professional_roles'), list) else []
    )
    resume_title = resume_source.get('title') if isinstance(resume_source.get('title'), str) else None
    parsed_experience_months = _extract_candidate_experience_months(resume_source, item)
    skill_candidates = _extract_names_from_list(
        resume_source.get('key_skills') if isinstance(resume_source.get('key_skills'), list) else []
    )
    if not skill_candidates:
        skill_candidates = _extract_names_from_list(resume_source.get('skill_set') if isinstance(resume_source.get('skill_set'), list) else [])

    text_blob = ' '.join(
        value
        for value in (
            resume_title,
            resume_source.get('skills'),
            resume_source.get('skill_set') if isinstance(resume_source.get('skill_set'), str) else None,
            resume_source.get('professional_roles') if isinstance(resume_source.get('professional_roles'), str) else None,
            item.get('cover_letter'),
            item.get('message'),
        )
        if isinstance(value, str) and value.strip()
    )
    normalized_blob = _normalize_text(text_blob)

    return {
        'skills': skill_candidates,
        'specialization': specialization_names or ([resume_title] if resume_title else []),
        'location': [area.get('name')] if isinstance(area.get('name'), str) and area.get('name').strip() else [],
        'salary_from': salary.get('from') if isinstance(salary.get('from'), (int, float)) else salary.get('amount') if isinstance(salary.get('amount'), (int, float)) else None,
        'salary_to': salary.get('to') if isinstance(salary.get('to'), (int, float)) else salary.get('amount') if isinstance(salary.get('amount'), (int, float)) else None,
        'experience': [value for value in (resume.get('total_experience'), resume.get('experience')) if isinstance(value, str) and value.strip()],
        'total_experience_months': parsed_experience_months,
        'work_format': _normalize_work_formats(work_format_names),
        'employment_type': employment_names,
        'language': language_names,
        'formalization': employment_names,
        'remote_mode': schedule_names,
        'summary_text': normalized_blob,
        'all_tokens': sorted(_normalize_tokens([normalized_blob] + schedule_names + employment_names + language_names)),
    }


def _match_criterion(
    *,
    criterion: str,
    compare_mode: str,
    expected: object,
    candidate_profile: dict[str, object],
) -> tuple[float, str]:
    if compare_mode == 'token_overlap':
        expected_tokens = _normalize_tokens(_as_string_list(expected))
        candidate_tokens = _normalize_tokens(_as_string_list(candidate_profile.get(criterion)))
        if not expected_tokens:
            return 0.0, 'Критерий вакансии не заполнен.'
        if not candidate_tokens:
            return 0.0, 'Нет данных кандидата для сравнения.'
        overlap = len(expected_tokens & candidate_tokens)
        if criterion == 'location':
            ratio = 1.0 if overlap > 0 else 0.0
        elif criterion == 'specialization':
            ratio = 1.0 if overlap > 0 else 0.0
        elif criterion == 'work_format':
            ratio = 1.0 if overlap > 0 else 0.0
        else:
            ratio = overlap / max(len(expected_tokens), 1)
        if criterion in {'skills', 'specialization'} and overlap > 0:
            matched_values = sorted(expected_tokens & candidate_tokens)
            label = 'Совпали навыки' if criterion == 'skills' else 'Совпала специализация'
            return ratio, f'{label}: {", ".join(matched_values)}'
        if criterion == 'work_format':
            if overlap > 0:
                matched_values = sorted(expected_tokens & candidate_tokens)
                return 1.0, f'Совпало: {", ".join(matched_values)}'
            return 0.0, 'Не совпадает формат работы'
        return ratio, f'Совпало {overlap} из {len(expected_tokens)}.'

    if compare_mode == 'work_format_match':
        expected_values = set(_normalize_work_formats(_as_string_list(expected)))
        candidate_values = set(_normalize_work_formats(_as_string_list(candidate_profile.get('work_format'))))
        if not expected_values:
            return 0.0, 'Критерий вакансии не заполнен.'
        if not candidate_values:
            return 0.0, 'Нет данных кандидата'
        overlap = expected_values & candidate_values
        if overlap:
            matched = ', '.join(_display_work_format(value) for value in sorted(overlap))
            return 1.0, f'Совпало: {matched}'
        return 0.0, 'Не совпадает формат работы'

    if compare_mode == 'salary_range' and isinstance(expected, dict):
        candidate_from = candidate_profile.get('salary_from')
        if not isinstance(candidate_from, (int, float)):
            return 0.0, 'У кандидата не указаны зарплатные ожидания.'
        expected_from = expected.get('from')
        expected_to = expected.get('to')
        if isinstance(expected_to, (int, float)) and candidate_from > expected_to:
            return 0.0, 'Ожидания кандидата выше вилки.'
        if isinstance(expected_from, (int, float)) and candidate_from < expected_from:
            return 0.7, 'Ожидания ниже минимальной границы.'
        return 1.0, 'Зарплатные ожидания попадают в вилку.'

    if compare_mode == 'experience_range' and isinstance(expected, dict):
        candidate_months = candidate_profile.get('total_experience_months')
        if not isinstance(candidate_months, int):
            return 0.0, 'Не удалось определить суммарный опыт кандидата.'

        min_months = expected.get('min_months')
        max_months = expected.get('max_months')
        experience_label = expected.get('label') if isinstance(expected.get('label'), str) else '—'

        if isinstance(min_months, int) and candidate_months < min_months:
            return 0.0, f'Опыт кандидата {candidate_months} мес., требуется от {min_months} мес. ({experience_label}).'
        if isinstance(max_months, int) and candidate_months > max_months:
            return 0.7, f'Опыт кандидата {candidate_months} мес., выше диапазона до {max_months} мес. ({experience_label}).'
        if isinstance(min_months, int) or isinstance(max_months, int):
            if isinstance(min_months, int) and isinstance(max_months, int):
                return 1.0, f'Опыт кандидата {candidate_months} мес., вакансия требует {min_months}–{max_months} мес.'
            if isinstance(min_months, int):
                return 1.0, f'Опыт кандидата {candidate_months} мес., вакансия требует от {min_months} мес.'
            return 1.0, f'Опыт кандидата {candidate_months} мес., вакансия требует до {max_months} мес.'

        candidate_text_tokens = _normalize_tokens(_as_string_list(candidate_profile.get('experience')))
        expected_tokens = _normalize_tokens([experience_label])
        if not candidate_text_tokens:
            return 0.0, 'Нет данных кандидата для сравнения по опыту.'
        overlap = len(expected_tokens & candidate_text_tokens)
        ratio = overlap / max(len(expected_tokens), 1)
        return ratio, f'Сопоставление текстового опыта: {overlap} из {len(expected_tokens)}.'

    if compare_mode == 'text_presence' and isinstance(expected, dict):
        summary_text = candidate_profile.get('summary_text') if isinstance(candidate_profile.get('summary_text'), str) else ''
        if not summary_text:
            return 0.0, 'Нет текстовых данных кандидата для проверки.'
        matched = 0
        for _, chunk in expected.items():
            chunk_tokens = [token for token in _normalize_text(chunk).split() if len(token) >= 4]
            if chunk_tokens and any(token in summary_text for token in chunk_tokens):
                matched += 1
        if not expected:
            return 0.0, 'Требования не указаны.'
        return matched / len(expected), f'Совпало {matched} из {len(expected)} текстовых требований.'

    return 0.0, 'Нет логики сравнения для критерия.'


def _extract_names_from_list(values: list[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
            continue
        if isinstance(value, dict):
            name = value.get('name')
            if isinstance(name, str) and name.strip():
                result.append(name.strip())
    return result


def _extract_single_name(value: object) -> list[str]:
    if isinstance(value, dict):
        name = value.get('name')
        if isinstance(name, str) and name.strip():
            return [name.strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return _extract_names_from_list(value)
    return []


def _has_meaningful_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_meaningful_value(nested) for nested in value.values())
    if isinstance(value, list):
        return any(_has_meaningful_value(nested) for nested in value)
    if isinstance(value, (int, float)):
        return True
    return False


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for nested_value in value.values():
            if isinstance(nested_value, str):
                result.append(nested_value)
        return result
    return []


def _normalize_text(value: str) -> str:
    decoded = unescape(value)
    no_tags = re.sub(r'<[^>]+>', ' ', decoded)
    normalized = no_tags.lower().replace('-', ' ').replace('—', ' ').replace('/', ' ')
    normalized = re.sub(r'[^a-zа-яё0-9+\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _extract_candidate_experience_months(resume: dict, item: dict) -> int | None:
    total_experience = resume.get('total_experience')
    if isinstance(total_experience, dict):
        months_value = total_experience.get('months')
        if isinstance(months_value, int):
            return max(months_value, 0)

    for source in (
        total_experience if isinstance(total_experience, str) else None,
        resume.get('experience') if isinstance(resume.get('experience'), str) else None,
        item.get('experience') if isinstance(item.get('experience'), str) else None,
    ):
        if isinstance(source, str):
            parsed = _parse_experience_months_from_text(source)
            if parsed is not None:
                return parsed
    return None


async def _fetch_resumes_profiles(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    items: list[dict],
) -> dict[str, dict]:
    resume_ids: set[str] = set()
    for item in items:
        resume_id = _extract_resume_id(item)
        if resume_id:
            resume_ids.add(resume_id)

    profiles: dict[str, dict] = {}
    for resume_id in resume_ids:
        payload = await _hh_get(client, f'/resumes/{resume_id}', access_token=access_token, allow_404=True)
        if payload.get('_status_code') == 404:
            continue
        profiles[resume_id] = payload
    return profiles


def _extract_resume_id(item: dict) -> str | None:
    resume = item.get('resume') if isinstance(item.get('resume'), dict) else {}
    direct_id = resume.get('id')
    if isinstance(direct_id, str) and direct_id.strip():
        return direct_id.strip()

    for key in ('url', 'alternate_url'):
        url_value = resume.get(key)
        if not isinstance(url_value, str) or not url_value:
            continue
        parsed = urlparse(url_value)
        path_parts = [part for part in parsed.path.split('/') if part]
        if 'resumes' in path_parts:
            idx = path_parts.index('resumes')
            if idx + 1 < len(path_parts):
                return unquote(path_parts[idx + 1])
    return None


def _parse_experience_months_from_text(value: str) -> int | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    years_match = re.search(r'(\d+)\s*(год|года|лет)', normalized)
    months_match = re.search(r'(\d+)\s*(месяц|месяца|месяцев|мес)', normalized)
    years = int(years_match.group(1)) if years_match else 0
    months = int(months_match.group(1)) if months_match else 0
    total = years * 12 + months
    if total > 0:
        return total

    plain_number_match = re.search(r'(\d+)', normalized)
    if plain_number_match:
        return int(plain_number_match.group(1)) * 12
    return None


def _parse_experience_range_months(label: str) -> tuple[int | None, int | None]:
    normalized = _normalize_text(label)
    if not normalized:
        return None, None

    numbers = [int(match) for match in re.findall(r'\d+', normalized)]
    if '+' in normalized and numbers:
        return numbers[0] * 12, None
    if len(numbers) >= 2:
        first, second = numbers[0], numbers[1]
        return min(first, second) * 12, max(first, second) * 12
    if len(numbers) == 1:
        value = numbers[0] * 12
        if 'до' in normalized:
            return None, value
        return value, None

    mapping = {
        'нет опыта': (0, 12),
        'от 1 года до 3 лет': (12, 36),
        'от 3 до 6 лет': (36, 72),
        'более 6 лет': (72, None),
    }
    for key, range_value in mapping.items():
        if key in normalized:
            return range_value

    return None, None


def _normalize_work_formats(values: list[str]) -> list[str]:
    normalized_values: list[str] = []
    for value in values:
        normalized = _normalize_work_format_value(value)
        if normalized and normalized not in normalized_values:
            normalized_values.append(normalized)
    return normalized_values


def _normalize_work_format_value(value: str) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    mapping = {
        'remote': 'remote',
        'удаленно': 'remote',
        'удалённо': 'remote',
        'office': 'office',
        'on site': 'office',
        'on_site': 'office',
        'на месте работодателя': 'office',
        'hybrid': 'hybrid',
        'гибрид': 'hybrid',
    }

    if normalized in mapping:
        return mapping[normalized]
    if normalized.upper() in {'REMOTE', 'OFFICE', 'HYBRID'}:
        return normalized.lower()
    return None


def _display_work_format(value: str) -> str:
    return {
        'remote': 'удалённо',
        'office': 'офис',
        'hybrid': 'гибрид',
    }.get(value, value)


def _normalize_tokens(values: list[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = _normalize_text(value)
        if normalized:
            tokens.add(normalized)
    return tokens


def _response_sort_key(item: dict[str, object | None]) -> tuple[int, int, str]:
    score_raw = item.get('score')
    score = score_raw if isinstance(score_raw, int) else -1
    has_score = 1 if isinstance(score_raw, int) else 0
    created_at = item.get('response_created_at')
    created_at_key = created_at if isinstance(created_at, str) else ''
    return has_score, score, created_at_key


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
