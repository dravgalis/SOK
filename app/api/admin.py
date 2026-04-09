import os
import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from .employer import _extract_employer_id, _extract_manager_id, _fetch_all_responses, _fetch_all_vacancies
from ..core.admin_store import (
    get_all_users,
    get_cached_user_vacancies,
    get_cached_vacancy_responses,
    get_user_access_token,
    get_users_with_tokens,
    replace_user_vacancies,
    replace_vacancy_responses,
    update_user_subscription,
    update_user_metrics,
)

router = APIRouter(prefix='/admin', tags=['admin'])
SKILLS_MATCH_RE = re.compile(r'Совпало\s+(?P<matched>\d+)\s+из', flags=re.IGNORECASE)


class AdminLoginRequest(BaseModel):
    login: str
    password: str


class AdminSubscriptionUpdateRequest(BaseModel):
    period_type: str
    period_ends_on: str | None = None


def _admin_token() -> str:
    return os.getenv('ADMIN_TOKEN', 'admin-secret-token').strip() or 'admin-secret-token'


def _require_admin_token(authorization: str | None) -> None:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Admin authorization required.')

    token = authorization.removeprefix('Bearer ').strip()
    if token != _admin_token():
        raise HTTPException(status_code=401, detail='Invalid admin token.')


@router.post('/login')
async def admin_login(payload: AdminLoginRequest) -> dict[str, str | bool]:
    expected_login = os.getenv('ADMIN_LOGIN', '').strip()
    expected_password = os.getenv('ADMIN_PASSWORD', '').strip()

    normalized_login = payload.login.strip()
    normalized_password = payload.password.strip()

    if not expected_login or not expected_password:
        raise HTTPException(status_code=401, detail='ADMIN_LOGIN/ADMIN_PASSWORD are not configured on backend.')

    if normalized_login != expected_login or normalized_password != expected_password:
        raise HTTPException(status_code=401, detail='Invalid admin credentials.')

    return {'success': True, 'token': _admin_token()}


@router.get('/users')
async def admin_users(authorization: str | None = Header(default=None)) -> list[dict[str, str | int | None]]:
    _require_admin_token(authorization)
    await _refresh_metrics_for_stale_users()
    return get_all_users()


@router.patch('/users/{hh_id}/subscription')
async def admin_update_user_subscription(
    hh_id: str,
    payload: AdminSubscriptionUpdateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, str | None]:
    _require_admin_token(authorization)

    allowed_period_types = {'trial_3d', 'paid_1m', 'paid_6m', 'paid_1y'}
    period_type = payload.period_type.strip()
    if period_type not in allowed_period_types:
        raise HTTPException(status_code=400, detail='Invalid period type.')

    period_ends_at: str | None = None
    if payload.period_ends_on:
        date_raw = payload.period_ends_on.strip()
        try:
            period_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail='period_ends_on must be YYYY-MM-DD.') from exc

        period_ends_at = datetime.combine(period_date, datetime.max.time(), tzinfo=timezone.utc).isoformat()

    updated = update_user_subscription(
        hh_id=hh_id,
        subscription_status=period_type,
        subscription_expires_at=period_ends_at,
    )
    if not updated:
        raise HTTPException(status_code=404, detail='User not found.')

    return {
        'hh_id': hh_id,
        'subscription_status': period_type,
        'subscription_expires_at': period_ends_at,
    }


@router.get('/users/{hh_id}/vacancies')
async def admin_user_vacancies(
    hh_id: str,
    authorization: str | None = Header(default=None),
    force: bool = Query(default=False),
) -> dict[str, object]:
    _require_admin_token(authorization)

    cached_at, cached_vacancies = get_cached_user_vacancies(hh_id)
    if not force:
        return {'hh_id': hh_id, 'vacancies': cached_vacancies, 'cached_at': cached_at, 'source': 'cache'}

    access_token = get_user_access_token(hh_id)
    if not access_token:
        raise HTTPException(status_code=404, detail='User token not found.')

    async with httpx.AsyncClient(timeout=20.0) as client:
        me_response = await client.get('https://api.hh.ru/me', headers={'Authorization': f'Bearer {access_token}'})
        me_response.raise_for_status()
        me_payload = me_response.json()
        vacancies = await _load_user_vacancies(client, access_token, me_payload)

    refreshed_at = datetime.now(timezone.utc).isoformat()
    replace_user_vacancies(hh_id, vacancies, refreshed_at)
    return {'hh_id': hh_id, 'vacancies': vacancies, 'cached_at': refreshed_at, 'source': 'hh'}


@router.get('/users/{hh_id}/vacancies/{vacancy_id}/responses')
async def admin_vacancy_responses(
    hh_id: str,
    vacancy_id: str,
    authorization: str | None = Header(default=None),
    force: bool = Query(default=False),
) -> dict[str, object]:
    _require_admin_token(authorization)

    cached_at, cached_responses = get_cached_vacancy_responses(hh_id, vacancy_id)
    if not force:
        return {
            'hh_id': hh_id,
            'vacancy_id': vacancy_id,
            'responses': cached_responses,
            'cached_at': cached_at,
            'source': 'cache',
        }

    access_token = get_user_access_token(hh_id)
    if not access_token:
        raise HTTPException(status_code=404, detail='User token not found.')

    async with httpx.AsyncClient(timeout=20.0) as client:
        responses_payload = await _fetch_all_responses(client, access_token=access_token, vacancy_id=vacancy_id)
    rows = _normalize_admin_responses(responses_payload)
    refreshed_at = datetime.now(timezone.utc).isoformat()
    replace_vacancy_responses(hh_id, vacancy_id, rows, refreshed_at)
    return {
        'hh_id': hh_id,
        'vacancy_id': vacancy_id,
        'responses': rows,
        'cached_at': refreshed_at,
        'source': 'hh',
    }


async def _refresh_metrics_for_stale_users() -> None:
    users = get_users_with_tokens()
    async with httpx.AsyncClient(timeout=20.0) as client:
        for user in users:
            hh_id_raw = user.get('hh_id')
            token = user.get('access_token')
            if not isinstance(hh_id_raw, str) or not isinstance(token, str) or not token:
                continue

            if not _needs_refresh(user.get('metrics_updated_at')):
                continue

            try:
                company_name, vacancies_count, responses_count = await _load_hh_metrics(client, token)
                update_user_metrics(
                    hh_id=hh_id_raw,
                    company_name=company_name,
                    vacancies_count=vacancies_count,
                    responses_count=responses_count,
                )
            except httpx.HTTPError:
                continue


def _needs_refresh(metrics_updated_at: str | int | None) -> bool:
    if not isinstance(metrics_updated_at, str) or not metrics_updated_at:
        return True
    try:
        updated_at = datetime.fromisoformat(metrics_updated_at)
    except ValueError:
        return True

    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - updated_at >= timedelta(seconds=10)


def _normalize_admin_responses(payload: dict[str, object]) -> list[dict[str, str | int]]:
    items = payload.get('items')
    if not isinstance(items, list):
        return []

    normalized_rows: list[dict[str, str | int]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        breakdown = item.get('score_breakdown')
        breakdown_rows = breakdown if isinstance(breakdown, list) else []
        normalized_rows.append(
            {
                'response_id': str(item.get('response_id') or ''),
                'name': str(item.get('candidate_name') or 'Без имени'),
                'specialization': str(item.get('resume_title') or '—'),
                'experience': _extract_experience_value(breakdown_rows),
                'matched_skills_count': _extract_skills_matches(breakdown_rows),
                'score_points': int(item.get('score') or 0),
            }
        )
    return normalized_rows


def _extract_experience_value(score_breakdown: list[object]) -> str:
    for row in score_breakdown:
        if not isinstance(row, dict):
            continue
        if row.get('criterion') != 'experience':
            continue
        reason = row.get('reason')
        if isinstance(reason, str) and reason:
            return reason
    return '—'


def _extract_skills_matches(score_breakdown: list[object]) -> int:
    for row in score_breakdown:
        if not isinstance(row, dict):
            continue
        if row.get('criterion') != 'skills':
            continue
        reason = row.get('reason')
        if not isinstance(reason, str) or not reason:
            return 0
        if reason.startswith('Совпали навыки:'):
            parts = [part.strip() for part in reason.removeprefix('Совпали навыки:').split(',') if part.strip()]
            return len(parts)
        match = SKILLS_MATCH_RE.search(reason)
        if match:
            return int(match.group('matched'))
    return 0


async def _load_hh_metrics(client: httpx.AsyncClient, access_token: str) -> tuple[str | None, int, int]:
    me_response = await client.get('https://api.hh.ru/me', headers={'Authorization': f'Bearer {access_token}'})
    me_response.raise_for_status()
    me_payload = me_response.json()

    employer_payload = me_payload.get('employer')
    employer_id = None
    company_name = None
    if isinstance(employer_payload, dict):
        employer_id_raw = employer_payload.get('id')
        employer_id = str(employer_id_raw).strip() if employer_id_raw is not None else None
        employer_name = employer_payload.get('name')
        company_name = employer_name if isinstance(employer_name, str) else None

    if not employer_id:
        return company_name, 0, 0

    manager_id = None
    manager_payload = me_payload.get('manager')
    if isinstance(manager_payload, dict):
        manager_id_raw = manager_payload.get('id')
        manager_id = str(manager_id_raw).strip() if manager_id_raw is not None else None

    vacancies_count = 0
    responses_count = 0
    for archived in (False, True):
        page = 0
        pages = 1
        while page < pages:
            params = {
                'employer_id': employer_id,
                'archived': 'true' if archived else 'false',
                'per_page': '100',
                'page': str(page),
            }
            if manager_id:
                params['manager_id'] = manager_id

            vacancies_response = await client.get(
                'https://api.hh.ru/vacancies',
                headers={'Authorization': f'Bearer {access_token}'},
                params=params,
            )
            vacancies_response.raise_for_status()
            payload = vacancies_response.json()

            items = payload.get('items')
            if not isinstance(items, list):
                items = []
            vacancies_count += len(items)
            for item in items:
                if not isinstance(item, dict):
                    continue
                counters = item.get('counters')
                if not isinstance(counters, dict):
                    continue
                responses_raw = counters.get('responses')
                if isinstance(responses_raw, int):
                    responses_count += responses_raw

            page += 1
            pages_raw = payload.get('pages')
            pages = pages_raw if isinstance(pages_raw, int) and pages_raw > 0 else 1

    return company_name, vacancies_count, responses_count


async def _load_user_vacancies(
    client: httpx.AsyncClient, access_token: str, me_payload: dict[str, object]
) -> list[dict[str, str | int]]:
    employer_id = _extract_employer_id(me_payload)
    if not employer_id:
        return []

    manager_id = _extract_manager_id(me_payload)

    rows: list[dict[str, str | int]] = []
    active_vacancies = await _fetch_all_vacancies(
        client,
        access_token=access_token,
        employer_id=employer_id,
        manager_id=manager_id,
        archived=False,
    )
    archived_vacancies = await _fetch_all_vacancies(
        client,
        access_token=access_token,
        employer_id=employer_id,
        manager_id=manager_id,
        archived=True,
    )

    for archived, vacancies in ((False, active_vacancies), (True, archived_vacancies)):
        for item in vacancies:
            if not isinstance(item, dict):
                continue
            vacancy_id_raw = item.get('id')
            vacancy_id = str(vacancy_id_raw) if vacancy_id_raw is not None else ''
            if not vacancy_id:
                continue

            responses_payload = await _fetch_all_responses(client, access_token=access_token, vacancy_id=vacancy_id)
            responses_count_raw = responses_payload.get('loaded_count')
            responses_count = responses_count_raw if isinstance(responses_count_raw, int) else 0

            vacancy_name_raw = item.get('name')
            rows.append(
                {
                    'id': vacancy_id,
                    'name': vacancy_name_raw if isinstance(vacancy_name_raw, str) else 'Без названия',
                    'status': 'archived' if archived else 'active',
                    'responses_count': responses_count,
                }
            )

    return rows
