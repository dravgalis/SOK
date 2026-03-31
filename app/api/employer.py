import httpx
from fastapi import APIRouter, Cookie, HTTPException

router = APIRouter()


@router.get('/me')
async def get_me(access_token: str | None = Cookie(default=None)) -> dict:
    if not access_token:
        raise HTTPException(status_code=401, detail='Unauthorized')

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get('https://api.hh.ru/me', headers={'Authorization': f'Bearer {access_token}'})

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail='Unauthorized')

    response.raise_for_status()
    return response.json()


@router.get('/vacancies')
async def get_vacancies(access_token: str | None = Cookie(default=None)) -> dict:
    if not access_token:
        raise HTTPException(status_code=401, detail='Unauthorized')

    async with httpx.AsyncClient(timeout=20.0) as client:
        me_response = await client.get('https://api.hh.ru/me', headers={'Authorization': f'Bearer {access_token}'})

    if me_response.status_code == 401:
        raise HTTPException(status_code=401, detail='Unauthorized')

    me_response.raise_for_status()
    employer_id = me_response.json().get('employer', {}).get('id')

    params = {'per_page': 20}
    if employer_id:
        params['employer_id'] = employer_id

    async with httpx.AsyncClient(timeout=20.0) as client:
        vacancies_response = await client.get(
            'https://api.hh.ru/vacancies',
            headers={'Authorization': f'Bearer {access_token}'},
            params=params,
        )

    if vacancies_response.status_code == 401:
        raise HTTPException(status_code=401, detail='Unauthorized')

    vacancies_response.raise_for_status()
    return vacancies_response.json()
