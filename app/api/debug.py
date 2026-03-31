from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

HH_API_BASE = 'https://api.hh.ru'


@router.get('/vacancies/{vacancy_id}/responses/raw')
async def get_vacancy_responses_raw(vacancy_id: str, request: Request) -> dict[str, object]:
    access_token = request.cookies.get('access_token')
    if not access_token:
        raise HTTPException(status_code=401, detail='Unauthorized')

    path = '/negotiations'
    params = {'vacancy_id': vacancy_id, 'per_page': '50', 'page': '0', 'status': 'any'}
    hh_request_url = str(httpx.URL(f'{HH_API_BASE}{path}', params=params))

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f'{HH_API_BASE}{path}',
            headers={'Authorization': f'Bearer {access_token}'},
            params=params,
        )

    try:
        hh_response: object = response.json()
    except ValueError:
        hh_response = {'raw_text': response.text}

    return {
        'vacancy_id': vacancy_id,
        'hh_request_url': hh_request_url,
        'hh_status_code': response.status_code,
        'hh_response': hh_response,
    }
