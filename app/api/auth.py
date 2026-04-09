import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from ..core.admin_store import get_user_subscription, upsert_hh_user

router = APIRouter()

_STATE_STORE: set[str] = set()


@router.get('/hh/login')
async def hh_login() -> RedirectResponse:
    frontend_url = _get_env('FRONTEND_APP_URL', 'https://sok-app.onrender.com')
    client_id = _get_env('HH_CLIENT_ID')
    redirect_uri = _get_env('HH_REDIRECT_URI')

    if not client_id or not redirect_uri:
        return _frontend_error_redirect(frontend_url, 'oauth_config_incomplete')

    state = secrets.token_urlsafe(32)
    _STATE_STORE.add(state)

    authorize_url = 'https://hh.ru/oauth/authorize?' + urlencode(
        {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'state': state,
        }
    )
    return RedirectResponse(url=authorize_url, status_code=307)


@router.get('/hh/callback')
async def hh_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    frontend_url = _get_env('FRONTEND_APP_URL', 'https://sok-app.onrender.com')

    if error:
        return _frontend_error_redirect(frontend_url, error)

    if not code or not state or state not in _STATE_STORE:
        return _frontend_error_redirect(frontend_url, 'invalid_callback_params')

    _STATE_STORE.discard(state)

    client_id = _get_env('HH_CLIENT_ID')
    client_secret = _get_env('HH_CLIENT_SECRET')
    redirect_uri = _get_env('HH_REDIRECT_URI')

    if not client_id or not client_secret or not redirect_uri:
        return _frontend_error_redirect(frontend_url, 'oauth_config_incomplete')

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                'https://hh.ru/oauth/token',
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                },
            )
        response.raise_for_status()
        token_payload = response.json()
    except httpx.HTTPError:
        return _frontend_error_redirect(frontend_url, 'token_exchange_failed')

    access_token = token_payload.get('access_token')
    if not access_token:
        return _frontend_error_redirect(frontend_url, 'token_missing')

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            me_response = await client.get(
                'https://api.hh.ru/me',
                headers={'Authorization': f'Bearer {access_token}'},
            )
            me_response.raise_for_status()
            me_payload = me_response.json()
            company_name, vacancies_count, responses_count = await _load_hh_metrics(client, access_token, me_payload)
        _track_hh_user_login(
            me_payload,
            access_token=access_token,
            company_name=company_name,
            vacancies_count=vacancies_count,
            responses_count=responses_count,
        )
    except (httpx.HTTPError, ValueError):
        return _frontend_error_redirect(frontend_url, 'failed_to_track_user')

    redirect_response = RedirectResponse(url=f'{frontend_url.rstrip("/")}/app', status_code=307)
    redirect_response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        secure=True,
        samesite='None',
        max_age=int(token_payload.get('expires_in', 3600)),
    )
    return redirect_response


def _get_env(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def _frontend_error_redirect(base_url: str, message: str) -> RedirectResponse:
    redirect_url = f"{base_url.rstrip('/')}/?{urlencode({'auth': 'error', 'message': message})}"
    return RedirectResponse(url=redirect_url, status_code=307)


def _track_hh_user_login(
    payload: dict[str, object],
    *,
    access_token: str,
    company_name: str | None,
    vacancies_count: int,
    responses_count: int,
) -> None:
    hh_id_raw = payload.get('id')
    hh_id = str(hh_id_raw).strip() if hh_id_raw is not None else ''
    if not hh_id:
        raise ValueError('hh_id_missing')

    first_name = payload.get('first_name')
    last_name = payload.get('last_name')
    full_name = ' '.join(part for part in [str(first_name or '').strip(), str(last_name or '').strip()] if part)
    fallback_name = payload.get('name') if isinstance(payload.get('name'), str) else None
    name = full_name or fallback_name or f'HH User {hh_id}'

    email_raw = payload.get('email')
    email = email_raw if isinstance(email_raw, str) and email_raw else None

    subscription_status, subscription_expires_at = _resolve_subscription_for_login(hh_id)

    upsert_hh_user(
        hh_id=hh_id,
        name=name,
        email=email,
        company_name=company_name,
        vacancies_count=vacancies_count,
        responses_count=responses_count,
        subscription_status=subscription_status,
        subscription_expires_at=subscription_expires_at,
        selected_interface='hh',
        access_token=access_token,
        metrics_updated_at=datetime.now(timezone.utc).isoformat(),
    )


def _resolve_subscription_for_login(hh_id: str) -> tuple[str | None, str | None]:
    now = datetime.now(timezone.utc)
    existing_status, existing_expires_at = get_user_subscription(hh_id)

    if existing_status and existing_expires_at:
        try:
            expires_at = datetime.fromisoformat(existing_expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return existing_status, expires_at.isoformat()
        except ValueError:
            pass

    trial_expires_at = now + timedelta(days=3)
    return 'trial_3d', trial_expires_at.isoformat()


async def _load_hh_metrics(
    client: httpx.AsyncClient,
    access_token: str,
    me_payload: dict[str, object],
) -> tuple[str | None, int, int]:
    employer_payload = me_payload.get('employer')
    company_name = None
    employer_id = None
    if isinstance(employer_payload, dict):
        employer_name = employer_payload.get('name')
        company_name = employer_name if isinstance(employer_name, str) else None
        employer_id_raw = employer_payload.get('id')
        employer_id = str(employer_id_raw).strip() if employer_id_raw is not None else None

    manager_payload = me_payload.get('manager')
    manager_id = None
    if isinstance(manager_payload, dict):
        manager_id_raw = manager_payload.get('id')
        manager_id = str(manager_id_raw).strip() if manager_id_raw is not None else None

    if not employer_id:
        return company_name, 0, 0

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

            response = await client.get(
                'https://api.hh.ru/vacancies',
                headers={'Authorization': f'Bearer {access_token}'},
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
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
