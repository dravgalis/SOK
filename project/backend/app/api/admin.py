import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from ..core.config import get_settings

router = APIRouter(prefix='/admin', tags=['admin'])

ADMIN_SESSION_COOKIE = 'admin_session'
ADMIN_SESSION_TTL_DAYS = 7


class AdminLoginRequest(BaseModel):
    login: str
    password: str


@router.post('/login')
async def admin_login(payload: AdminLoginRequest, response: Response) -> dict[str, bool]:
    settings = get_settings()

    expected_login = os.getenv('ADMIN_LOGIN', settings.admin_login).strip()
    expected_password = os.getenv('ADMIN_PASSWORD', settings.admin_password).strip()

    if payload.login.strip() == expected_login and payload.password.strip() == expected_password:
        return {'success': True}

    response.status_code = status.HTTP_401_UNAUTHORIZED
    return {'success': False}


@router.get('/users-count')
async def admin_users_count() -> dict[str, int]:
    return {'count': 10}
