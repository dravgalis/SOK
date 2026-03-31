import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

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
