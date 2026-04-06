import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..core.admin_store import get_all_users

router = APIRouter(prefix='/admin', tags=['admin'])


class AdminLoginRequest(BaseModel):
    login: str
    password: str


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

    if not expected_login or not expected_password:
        raise HTTPException(status_code=500, detail='Admin credentials are not configured.')

    if payload.login != expected_login or payload.password != expected_password:
        raise HTTPException(status_code=401, detail='Invalid admin credentials.')

    return {'success': True, 'token': _admin_token()}


@router.get('/users')
async def admin_users(authorization: str | None = Header(default=None)) -> list[dict[str, str | None]]:
    _require_admin_token(authorization)
    return get_all_users()
