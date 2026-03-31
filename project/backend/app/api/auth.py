from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, HTTPException, Query
from fastapi.responses import RedirectResponse

from ..core.config import get_settings
from ..services.hh_client import HHClient, HHClientError
from ..services.hh_oauth import HHOAuthService

router = APIRouter(tags=['hh-auth'])

ACCESS_TOKEN_COOKIE = 'hh_access_token'


@router.get('/auth/hh/login')
async def hh_login() -> RedirectResponse:
    settings = get_settings()

    if not settings.hh_client_id or not settings.hh_redirect_uri:
        return _frontend_redirect(
            settings.frontend_app_url,
            {'auth': 'error', 'message': 'OAuth конфигурация сервера неполная.'},
        )

    oauth_service = HHOAuthService(settings)
    state = oauth_service.generate_state()
    authorize_url = await oauth_service.build_authorize_url(state)

    return RedirectResponse(url=authorize_url, status_code=307)


@router.get('/auth/hh/callback')
async def hh_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    settings = get_settings()
    oauth_service = HHOAuthService(settings)

    if error:
        return _frontend_redirect(
            settings.frontend_app_url,
            {'auth': 'error', 'message': error_description or error},
        )

    if not code or not state or not oauth_service.validate_state(state):
        return _frontend_redirect(
            settings.frontend_app_url,
            {'auth': 'error', 'message': 'Некорректные параметры OAuth callback.'},
        )

    if not settings.hh_client_id or not settings.hh_client_secret or not settings.hh_redirect_uri:
        return _frontend_redirect(
            settings.frontend_app_url,
            {'auth': 'error', 'message': 'OAuth конфигурация сервера неполная.'},
        )

    hh_client = HHClient(settings)

    try:
        access_token = await hh_client.exchange_code(code)
    except HHClientError as exc:
        return _frontend_redirect(
            settings.frontend_app_url,
            {'auth': 'error', 'message': str(exc)},
        )

    response = RedirectResponse(url=f"{settings.frontend_app_url.rstrip('/')}/app", status_code=307)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path='/',
        max_age=3600,
    )
    return response


@router.get('/me')
async def get_me(access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE)) -> dict[str, str | None]:
    token = _require_access_token(access_token)
    hh_client = HHClient(get_settings())

    try:
        payload = await hh_client.get_current_user(token)
    except HHClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    photo = payload.get('photo')
    avatar_url = photo.get('90') if isinstance(photo, dict) else None

    first_name = payload.get('first_name') if isinstance(payload.get('first_name'), str) else None
    last_name = payload.get('last_name') if isinstance(payload.get('last_name'), str) else None
    name = payload.get('name') if isinstance(payload.get('name'), str) else None

    return {
        'id': str(payload.get('id', '')),
        'first_name': first_name,
        'last_name': last_name,
        'name': name or ' '.join(part for part in [first_name, last_name] if part),
        'avatar_url': avatar_url,
    }


@router.get('/vacancies')
async def get_vacancies(access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE)) -> dict[str, list[dict[str, str | None]]]:
    token = _require_access_token(access_token)
    hh_client = HHClient(get_settings())

    try:
        payload = await hh_client.get_vacancies(token, per_page=20)
    except HHClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    items = payload.get('items') if isinstance(payload.get('items'), list) else []
    vacancies: list[dict[str, str | None]] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        status_data = item.get('type')
        status = status_data.get('name') if isinstance(status_data, dict) else None

        vacancies.append(
            {
                'id': str(item.get('id', '')),
                'name': str(item.get('name', '')),
                'status': status,
                'published_at': str(item.get('published_at')) if item.get('published_at') else None,
            }
        )

    return {'items': vacancies}


def _require_access_token(access_token: str | None) -> str:
    if not access_token:
        raise HTTPException(status_code=401, detail='Требуется авторизация через HeadHunter.')
    return access_token


def _frontend_redirect(base_url: str, params: dict[str, str]) -> RedirectResponse:
    separator = '&' if '?' in base_url else '?'
    redirect_url = f'{base_url}{separator}{urlencode(params)}'
    return RedirectResponse(url=redirect_url, status_code=307)
