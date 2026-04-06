import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from ..core.config import get_settings
from ..core.db import get_users_count

router = APIRouter(prefix='/api/admin', tags=['admin'])

ADMIN_SESSION_COOKIE = 'admin_session'
ADMIN_SESSION_TTL_DAYS = 7


class AdminLoginRequest(BaseModel):
    login: str
    password: str


def _is_admin_session_valid(request: Request) -> bool:
    settings = get_settings()
    session_value = request.cookies.get(ADMIN_SESSION_COOKIE, '')
    return bool(session_value) and session_value == settings.admin_token


def _require_admin_session(request: Request) -> None:
    if not _is_admin_session_valid(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Admin authorization required.')


@router.post('/login')
async def admin_login(payload: AdminLoginRequest, response: Response) -> dict[str, bool]:
    settings = get_settings()

    expected_login = os.getenv('ADMIN_LOGIN', settings.admin_login).strip()
    expected_password = os.getenv('ADMIN_PASSWORD', settings.admin_password).strip()

    normalized_login = payload.login.strip()
    normalized_password = payload.password.strip()

    if not expected_login or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='ADMIN_LOGIN/ADMIN_PASSWORD are not configured on backend.',
        )

    if normalized_login != expected_login or normalized_password != expected_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid admin credentials.')

    expires = datetime.now(timezone.utc) + timedelta(days=ADMIN_SESSION_TTL_DAYS)
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=settings.admin_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        expires=expires,
        path='/',
    )

    return {'success': True}


@router.get('/users-count')
async def admin_users_count(request: Request) -> dict[str, int]:
    _require_admin_session(request)
    return {'count': get_users_count()}
