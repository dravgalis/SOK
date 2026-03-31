from uuid import uuid4

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.hh_client import HHClient
from app.services.hh_oauth import HHOAuthService

router = APIRouter(prefix='/auth/hh', tags=['hh-auth'])


@router.get('/login')
async def hh_login() -> dict:
    settings = get_settings()
    oauth = HHOAuthService(settings)
    state = uuid4().hex
    authorize_url = await oauth.build_authorize_url(state)
    return {'authorize_url': authorize_url, 'state': state}


@router.post('/callback')
async def hh_callback(payload: dict) -> dict:
    code = payload.get('code')
    state = payload.get('state')

    if not code or not state:
        return {'success': False, 'message': 'code/state обязательны'}

    client = HHClient()
    token_data = await client.exchange_code(code)
    return {'success': True, 'token': token_data, 'state': state}
