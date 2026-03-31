from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from ..core.config import get_settings
from ..services.hh_client import HHClient, HHClientError
from ..services.hh_oauth import HHOAuthService

router = APIRouter(prefix='/hh', tags=['hh-auth'])


@router.get('/login')
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


@router.get('/callback')
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
        await hh_client.exchange_code(code)
    except HHClientError as exc:
        return _frontend_redirect(
            settings.frontend_app_url,
            {'auth': 'error', 'message': str(exc)},
        )

    return _frontend_redirect(settings.frontend_app_url, {'auth': 'success'})


def _frontend_redirect(base_url: str, params: dict[str, str]) -> RedirectResponse:
    separator = '&' if '?' in base_url else '?'
    redirect_url = f'{base_url}{separator}{urlencode(params)}'
    return RedirectResponse(url=redirect_url, status_code=307)
