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

    active_vacancies = [_map_vacancy(item, archived=False) for item in active_items]
    archived_vacancies = [_map_vacancy(item, archived=True) for item in archived_items]

    return {
        'active': active_vacancies,
        'archived': archived_vacancies,
        'counts': {
            'active': len(active_vacancies),
            'archived': len(archived_vacancies),
        },
    }


@router.get('/vacancies/{vacancy_id}')
async def get_vacancy_details(
    vacancy_id: str,
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
) -> dict[str, object]:
    token = _require_access_token(access_token)
    hh_client = HHClient(get_settings())

    try:
        active_items = await hh_client.get_vacancies(token, per_page=100, archived=False)
        archived_items = await hh_client.get_vacancies(token, per_page=100, archived=True)
    except HHClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    found_active = _find_vacancy_by_id(active_items, vacancy_id)
    if found_active is not None:
        mapped = _map_vacancy(found_active, archived=False)
        return {
            'id': mapped['id'],
            'name': mapped['name'],
            'normalized_status': mapped['normalized_status'],
            'published_at': mapped['published_at'],
            'archived_at': mapped['archived_at'],
            'responses_count': mapped['responses_count'],
            'description': None,
        }

    found_archived = _find_vacancy_by_id(archived_items, vacancy_id)
    if found_archived is not None:
        mapped = _map_vacancy(found_archived, archived=True)
        return {
            'id': mapped['id'],
            'name': mapped['name'],
            'normalized_status': mapped['normalized_status'],
            'published_at': mapped['published_at'],
            'archived_at': mapped['archived_at'],
            'responses_count': mapped['responses_count'],
            'description': None,
        }

    raise HTTPException(status_code=404, detail='Вакансия не найдена.')


@router.get('/vacancies/{vacancy_id}/responses')
async def get_vacancy_responses(
    vacancy_id: str,
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
) -> dict[str, object]:
    token = _require_access_token(access_token)
    hh_client = HHClient(get_settings())

    try:
        me = await hh_client.get_current_user(token)
        employer_id = _extract_employer_id(me)
        response_result = await hh_client.get_vacancy_responses_with_debug(token, vacancy_id, employer_id=employer_id)
    except HHClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response_items = response_result.get('items') if isinstance(response_result.get('items'), list) else []
    responses = [_map_response(item) for item in response_items]
    payload: dict[str, object] = {
        'vacancy_id': vacancy_id,
        'items': responses,
        'count': len(responses),
    }
    if not responses:
        payload['debug'] = response_result.get('debug')
    return payload


@router.get('/debug/vacancies/{vacancy_id}/responses/raw')
async def debug_vacancy_responses_raw(
    vacancy_id: str,
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
) -> dict[str, object]:
    token = _require_access_token(access_token)
    hh_client = HHClient(get_settings())

    try:
        me = await hh_client.get_current_user(token)
        employer_id = _extract_employer_id(me)
        return await hh_client.get_vacancy_responses_raw_debug(token, vacancy_id, employer_id=employer_id)
    except HHClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _find_vacancy_by_id(items: list[dict[str, object]], vacancy_id: str) -> dict[str, object] | None:
    for item in items:
        if str(item.get('id', '')) == vacancy_id:
            return item
    return None


def _extract_employer_id(me_payload: dict[str, object]) -> str | None:
    employer = me_payload.get('employer')
    if isinstance(employer, dict):
        employer_id = employer.get('id')
        if isinstance(employer_id, (str, int)):
            return str(employer_id)
    return None


def _map_vacancy(item: dict[str, object], *, archived: bool) -> dict[str, object]:
    return {
        'id': str(item.get('id', '')),
        'name': _as_string(item.get('name')),
        'status': _normalize_status(archived),
        'normalized_status': _normalize_status(archived),
        'archived': archived,
        'published_at': _as_string_or_none(item.get('published_at')),
        'archived_at': _as_string_or_none(item.get('archived_at')),
        'responses_count': _extract_responses_count(item),
    }


def _map_response(item: dict[str, object]) -> dict[str, object]:
    resume = _extract_first_dict(item, ('resume', 'resume_info', 'cv'))
    applicant = _extract_first_dict(item, ('applicant', 'user', 'candidate'))
    salary = resume.get('salary') if isinstance(resume.get('salary'), dict) else {}
    area = resume.get('area') if isinstance(resume.get('area'), dict) else applicant.get('area') if isinstance(applicant.get('area'), dict) else {}
    status = item.get('state') if isinstance(item.get('state'), dict) else item.get('status') if isinstance(item.get('status'), dict) else {}
    candidate_name = (
        applicant.get('full_name')
        or applicant.get('name')
        or _extract_nested_value(item, ('resume', 'owner', 'name'))
        or _extract_nested_value(item, ('resume', 'first_name'))
    )
    cover_letter = (
        item.get('cover_letter')
        or item.get('message')
        or _extract_nested_value(item, ('topic', 'body'))
        or _extract_nested_value(item, ('chat', 'message'))
    )
    created_at = item.get('created_at') or item.get('updated_at') or item.get('date')
    response_id = item.get('id') or item.get('response_id') or _extract_nested_value(item, ('topic', 'id'))

    return {
        'response_id': _as_string(response_id),
        'candidate_name': _as_string_or_none(candidate_name),
        'resume_title': _as_string_or_none(resume.get('title')),
        'expected_salary': _format_salary(salary),
        'location': _as_string_or_none(area.get('name')),
        'response_created_at': _as_string_or_none(created_at),
        'cover_letter': _as_string_or_none(cover_letter),
        'status': _as_string_or_none(status.get('name') or status.get('id')),
    }


def _extract_first_dict(item: dict[str, object], keys: tuple[str, ...]) -> dict[str, object]:
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _extract_nested_value(item: dict[str, object], path: tuple[str, ...]) -> object | None:
    current: object = item
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _format_salary(salary: dict[str, object]) -> str | None:
    amount_raw = salary.get('amount') or salary.get('from') or salary.get('to')
    currency_raw = salary.get('currency')

    amount: str | None = None
    if isinstance(amount_raw, (int, float)):
        amount = str(int(amount_raw))
    elif isinstance(amount_raw, str):
        amount = amount_raw

    currency = currency_raw if isinstance(currency_raw, str) else None

    if amount and currency:
        return f'{amount} {currency}'

    return amount


def _extract_responses_count(item: dict[str, object]) -> int:
    counters = item.get('counters')
    if isinstance(counters, dict):
        for key in ('responses', 'new_responses', 'all_responses'):
            value = counters.get(key)
            if isinstance(value, int):
                return value

    for key in ('responses_count', 'response_count', 'responses'):
        value = item.get(key)
        if isinstance(value, int):
            return value

    return 0


def _normalize_status(archived: bool) -> str:
    return 'Архивная' if archived else 'Активная'


def _as_string(value: object) -> str:
    return str(value) if value is not None else ''


def _as_string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _require_access_token(access_token: str | None) -> str:
    if not access_token:
        raise HTTPException(status_code=401, detail='Требуется авторизация через HeadHunter.')
    return access_token


def _frontend_redirect(base_url: str, params: dict[str, str]) -> RedirectResponse:
    separator = '&' if '?' in base_url else '?'
    redirect_url = f'{base_url}{separator}{urlencode(params)}'
    return RedirectResponse(url=redirect_url, status_code=307)
