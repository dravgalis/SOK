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

    company_name: str | None = None
    company_logo_url: str | None = None

    employer_data = payload.get('employer')
    if isinstance(employer_data, dict):
        employer_name = employer_data.get('name')
        company_name = employer_name if isinstance(employer_name, str) else None

        logo_urls = employer_data.get('logo_urls')
        if isinstance(logo_urls, dict):
            company_logo_url = (
                logo_urls.get('original')
                if isinstance(logo_urls.get('original'), str)
                else logo_urls.get('240')
                if isinstance(logo_urls.get('240'), str)
                else logo_urls.get('90')
                if isinstance(logo_urls.get('90'), str)
                else None
            )

        employer_id = employer_data.get('id')
        if isinstance(employer_id, (str, int)) and (not company_name or not company_logo_url):
            try:
                employer_payload = await hh_client.get_employer(token, str(employer_id))
            except HHClientError:
                employer_payload = {}

            if not company_name and isinstance(employer_payload.get('name'), str):
                company_name = employer_payload.get('name')

            employer_logo_urls = employer_payload.get('logo_urls')
            if not company_logo_url and isinstance(employer_logo_urls, dict):
                company_logo_url = (
                    employer_logo_urls.get('original')
                    if isinstance(employer_logo_urls.get('original'), str)
                    else employer_logo_urls.get('240')
                    if isinstance(employer_logo_urls.get('240'), str)
                    else employer_logo_urls.get('90')
                    if isinstance(employer_logo_urls.get('90'), str)
                    else None
                )

    return {
        'id': str(payload.get('id', '')),
        'first_name': first_name,
        'last_name': last_name,
        'name': name or ' '.join(part for part in [first_name, last_name] if part),
        'avatar_url': avatar_url,
        'company_name': company_name,
        'company_logo_url': company_logo_url,
    }


@router.get('/vacancies')
async def get_vacancies(access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE)) -> dict[str, object]:
    token = _require_access_token(access_token)
    hh_client = HHClient(get_settings())

    try:
        active_items = await hh_client.get_vacancies(token, per_page=100, archived=False)
        archived_items = await hh_client.get_vacancies(token, per_page=100, archived=True)
    except HHClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    active_vacancies = [_map_vacancy(item, fallback_status='Активна') for item in active_items]
    archived_vacancies = [_map_vacancy(item, fallback_status='В архиве') for item in archived_items]

    return {
        'active': active_vacancies,
        'archived': archived_vacancies,
        'counts': {
            'active': len(active_vacancies),
            'archived': len(archived_vacancies),
        },
    }


def _map_vacancy(item: dict[str, object], *, fallback_status: str) -> dict[str, str | None]:
    name_raw = item.get('name')
    status_raw = item.get('status')
    type_raw = item.get('type')
    published_at_raw = item.get('published_at')
    archived_at_raw = item.get('archived_at')

    status: str | None = None
    if isinstance(status_raw, dict) and isinstance(status_raw.get('name'), str):
        status = status_raw.get('name')
    elif isinstance(type_raw, dict) and isinstance(type_raw.get('name'), str):
        status = type_raw.get('name')

    return {
        'id': str(item.get('id', '')),
        'name': str(name_raw) if name_raw is not None else '',
        'status': status or fallback_status,
        'published_at': str(published_at_raw) if published_at_raw else None,
        'archived_at': str(archived_at_raw) if archived_at_raw else None,
    }


def _require_access_token(access_token: str | None) -> str:
    if not access_token:
        raise HTTPException(status_code=401, detail='Требуется авторизация через HeadHunter.')
    return access_token


def _frontend_redirect(base_url: str, params: dict[str, str]) -> RedirectResponse:
    separator = '&' if '?' in base_url else '?'
    redirect_url = f'{base_url}{separator}{urlencode(params)}'
    return RedirectResponse(url=redirect_url, status_code=307)
