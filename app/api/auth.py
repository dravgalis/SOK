from fastapi import APIRouter

router = APIRouter()


@router.get('/hh/login')
async def hh_login() -> dict[str, str]:
    return {'status': 'ok', 'message': 'HH login route is available'}
