from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..core.config import get_settings
from ..core.db import get_all_users

router = APIRouter(prefix='/admin', tags=['admin'])


class AdminLoginRequest(BaseModel):
    login: str
    password: str


def _require_admin_token(authorization: str | None) -> None:
    settings = get_settings()

    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Admin authorization required.')

    token = authorization.removeprefix('Bearer ').strip()
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail='Invalid admin token.')


@router.post('/login')
async def admin_login(payload: AdminLoginRequest) -> dict[str, str | bool]:
    settings = get_settings()

    if not settings.admin_login or not settings.admin_password:
        raise HTTPException(status_code=500, detail='Admin credentials are not configured.')

    if payload.login != settings.admin_login or payload.password != settings.admin_password:
        raise HTTPException(status_code=401, detail='Invalid admin credentials.')

    return {
        'success': True,
        'token': settings.admin_token,
    }


@router.get('/users')
async def admin_users(authorization: str | None = Header(default=None)) -> list[dict[str, str | None]]:
    _require_admin_token(authorization)
    return get_all_users()
