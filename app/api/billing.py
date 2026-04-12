from datetime import datetime, timedelta, timezone
from math import ceil
from calendar import monthrange
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..core.admin_store import (
    add_support_message,
    get_payment,
    get_user_billing,
    get_user_selected_interface,
    get_billing_operations,
    get_user_unlocked_themes,
    get_support_chat_messages,
    mark_payment_failed,
    mark_support_messages_read_by_user,
    mark_payment_processed,
    record_payment,
    unlock_theme_for_user,
    update_user_selected_interface,
    update_user_billing,
    get_users_for_recurring,
)
from ..services.yookassa_service import YooKassaService, YooKassaServiceError

router = APIRouter(prefix='/api/billing', tags=['billing'])

ALLOWED_STATUSES = {'active', 'inactive', 'past_due', 'canceled'}


class CreatePaymentRequest(BaseModel):
    plan_code: Literal['1_month', '6_months', '12_months']


class AutoRenewRequest(BaseModel):
    enabled: bool


class CreateThemePaymentRequest(BaseModel):
    theme_code: str


class SelectThemeRequest(BaseModel):
    theme_code: str


class SupportMessageRequest(BaseModel):
    message: str


THEME_STORE: dict[str, dict[str, object]] = {
    'default': {'label': 'Светлая', 'price': 0.0, 'paid': False, 'rarity': 'Обычная'},
    'dark': {'label': 'Тёмно-синяя', 'price': 0.0, 'paid': False, 'rarity': 'Обычная'},
    'blue': {'label': 'Голубая', 'price': 0.0, 'paid': False, 'rarity': 'Обычная'},
    'beige': {'label': 'Бежевая', 'price': 0.0, 'paid': False, 'rarity': 'Обычная'},
    'mint': {'label': 'Мятная', 'price': 50.0, 'paid': True, 'rarity': 'Необычная'},
    'lavender': {'label': 'Лавандовая', 'price': 50.0, 'paid': True, 'rarity': 'Необычная'},
    'sunset': {'label': 'Закат', 'price': 50.0, 'paid': True, 'rarity': 'Необычная'},
    'aurora': {'label': 'Северное сияние', 'price': 150.0, 'paid': True, 'rarity': 'Редкая'},
    'neon': {'label': 'Неон', 'price': 750.0, 'paid': True, 'rarity': 'Эпическая'},
    'golden-sakura': {'label': 'Золотая сакура', 'price': 1500.0, 'paid': True, 'rarity': 'Легендарная'},
    'mythic-pop': {'label': 'Mythic Pop', 'price': 3000.0, 'paid': True, 'rarity': 'Мифическая'},
}


@router.post('/create-payment')
async def create_payment(payload: CreatePaymentRequest, request: Request) -> dict[str, str]:
    hh_id = await _require_hh_id(request)
    service = YooKassaService()
    try:
        payment = await service.create_payment(plan_code=payload.plan_code, hh_id=hh_id)
    except YooKassaServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_payment(
        payment_id=payment['payment_id'],
        hh_id=hh_id,
        plan_code=payload.plan_code,
        amount=payment['amount'],
        currency=payment['currency'],
        product_type='subscription',
    )
    return {'confirmation_url': payment['confirmation_url']}


@router.post('/create-theme-payment')
async def create_theme_payment(payload: CreateThemePaymentRequest, request: Request) -> dict[str, str]:
    hh_id = await _require_hh_id(request)
    theme_info = THEME_STORE.get(payload.theme_code)
    if theme_info is None or not bool(theme_info.get('paid')):
        raise HTTPException(status_code=400, detail='Theme is not payable.')
    service = YooKassaService()
    try:
        payment = await service.create_theme_payment(theme_code=payload.theme_code, hh_id=hh_id, amount=float(theme_info['price']))
    except YooKassaServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_payment(
        payment_id=payment['payment_id'],
        hh_id=hh_id,
        plan_code='theme_purchase',
        amount=payment['amount'],
        currency=payment['currency'],
        product_type='theme',
        theme_code=payload.theme_code,
    )
    return {'confirmation_url': payment['confirmation_url']}


@router.post('/yookassa/webhook')
async def yookassa_webhook(payload: dict[str, object]) -> dict[str, bool]:
    event = payload.get('event')
    if event not in {'payment.succeeded', 'payment.canceled'}:
        return {'ok': True}

    obj = payload.get('object')
    if not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail='Invalid webhook payload.')

    payment_id = obj.get('id')
    if not isinstance(payment_id, str):
        raise HTTPException(status_code=400, detail='Missing payment id.')
    print('WEBHOOK RECEIVED:', payment_id)

    payment_row = get_payment(payment_id)
    if payment_row is None:
        print('WEBHOOK ERROR: payment not found in billing_payments:', payment_id)
        return {'ok': False}

    if event == 'payment.canceled':
        cancellation_details = obj.get('cancellation_details') if isinstance(obj.get('cancellation_details'), dict) else {}
        reason_raw = cancellation_details.get('reason')
        reason = reason_raw if isinstance(reason_raw, str) and reason_raw else 'payment_canceled'
        provider_status_raw = obj.get('status')
        provider_status = provider_status_raw if isinstance(provider_status_raw, str) else 'canceled'
        mark_payment_failed(payment_id, reason=reason, provider_status=provider_status)
        if payment_row.get('product_type') != 'theme':
            update_user_billing(hh_id=payment_row['hh_id'], status='past_due', sync_legacy_subscription=False)
        return {'ok': True}

    already_processed = payment_row['status'] == 'succeeded'
    if not already_processed:
        already_processed = not mark_payment_processed(payment_id, 'succeeded')

    hh_id = payment_row['hh_id']
    plan_code = payment_row['plan_code']
    if payment_row.get('product_type') == 'theme':
        theme_code = payment_row.get('theme_code')
        if isinstance(theme_code, str) and theme_code:
            unlock_theme_for_user(hh_id, theme_code)
        return {'ok': True}

    print('USER:', hh_id)
    print('PLAN:', plan_code)
    current = get_user_billing(hh_id) or {}
    now = datetime.now(timezone.utc)
    duration = _months_for_plan(plan_code)
    current_end = _parse_iso(current.get('current_period_end') if isinstance(current, dict) else None)
    payment_method = obj.get('payment_method') if isinstance(obj.get('payment_method'), dict) else {}
    payment_method_id: str | None = None
    if payment_method and payment_method.get('saved'):
        method_id_raw = payment_method.get('id')
        if isinstance(method_id_raw, str) and method_id_raw:
            payment_method_id = method_id_raw

    if current_end and now < current_end:
        extended_end = _add_calendar_months(current_end, duration)
    else:
        extended_end = _add_calendar_months(now, duration)

    next_period_end = current_end.isoformat() if (already_processed and current_end) else extended_end.isoformat()

    update_user_billing(
        hh_id=hh_id,
        plan_code=plan_code,
        amount=payment_row['amount'],
        currency=payment_row['currency'],
        status='active',
        current_period_end=next_period_end,
        payment_method_id=payment_method_id if payment_method_id else current.get('payment_method_id'),
        last_payment_id=payment_id,
        last_payment_at=now.isoformat(),
    )
    return {'ok': True}


@router.get('/operations')
async def my_operations(request: Request) -> dict[str, object]:
    hh_id = await _require_hh_id(request)
    operations = get_billing_operations(hh_id)
    billing = get_user_billing(hh_id) or {}
    now = datetime.now(timezone.utc)
    current_period_end = _parse_iso(billing.get('current_period_end'))
    days_left = 0
    if current_period_end:
        days_left = max(0, ceil((current_period_end - now).total_seconds() / 86400))

    mapped: list[dict[str, object]] = []
    for operation in operations:
        plan_code = str(operation.get('plan_code') or '')
        mapped.append(
            {
                'payment_id': operation.get('payment_id'),
                'plan_code': plan_code,
                'months_extended': _months_for_plan(plan_code) if plan_code in {'1_month', '6_months', '12_months'} else 0,
                'amount': operation.get('amount'),
                'currency': operation.get('currency'),
                'status': operation.get('status'),
                'reason': operation.get('failure_reason'),
                'created_at': operation.get('created_at'),
                'processed_at': operation.get('processed_at'),
            }
        )

    return {
        'operations': mapped,
        'total_paid': sum(_safe_float(item.get('amount')) for item in operations if item.get('status') == 'succeeded'),
        'days_left': days_left,
    }


@router.post('/support-message')
async def send_support_message(payload: SupportMessageRequest, request: Request) -> dict[str, str]:
    hh_id = await _require_hh_id(request)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail='Сообщение не должно быть пустым.')
    if len(message) > 2000:
        raise HTTPException(status_code=400, detail='Сообщение слишком длинное (максимум 2000 символов).')
    message_id = add_support_message(hh_id=hh_id, message=message)
    return {'message_id': message_id}


@router.get('/support-chat')
async def get_support_chat(request: Request) -> dict[str, object]:
    hh_id = await _require_hh_id(request)
    messages = get_support_chat_messages(hh_id)
    unread_for_user = sum(
        1
        for item in messages
        if item.get('sender_role') == 'admin' and not bool(item.get('read_by_user'))
    )
    return {'messages': messages, 'unread_for_user': unread_for_user}


@router.post('/support-chat/read')
async def mark_support_chat_read(request: Request) -> dict[str, int]:
    hh_id = await _require_hh_id(request)
    updated = mark_support_messages_read_by_user(hh_id)
    return {'updated': updated}


@router.get('/themes')
async def my_themes(request: Request) -> dict[str, object]:
    hh_id = await _require_hh_id(request)
    unlocked = get_user_unlocked_themes(hh_id)
    themes = []
    for code, item in THEME_STORE.items():
        is_paid = bool(item.get('paid'))
        themes.append(
            {
                'code': code,
                'label': item.get('label'),
                'price': item.get('price'),
                'paid': is_paid,
                'rarity': item.get('rarity', 'Обычная'),
                'unlocked': (not is_paid) or (code in unlocked),
            }
        )
    return {'themes': themes}


@router.get('/selected-theme')
async def get_selected_theme(request: Request) -> dict[str, str]:
    hh_id = await _require_hh_id(request)
    unlocked = get_user_unlocked_themes(hh_id)

    current_selected = get_user_selected_interface(hh_id)
    selected = current_selected or 'default'
    theme_info = THEME_STORE.get(selected)
    if theme_info is None:
        selected = 'default'
    elif bool(theme_info.get('paid')) and selected not in unlocked:
        selected = 'default'

    if current_selected != selected:
        update_user_selected_interface(hh_id, selected)

    return {'selected_theme': selected}


@router.patch('/selected-theme')
async def set_selected_theme(payload: SelectThemeRequest, request: Request) -> dict[str, str]:
    hh_id = await _require_hh_id(request)
    theme_info = THEME_STORE.get(payload.theme_code)
    if theme_info is None:
        raise HTTPException(status_code=400, detail='Unknown theme.')

    if bool(theme_info.get('paid')):
        unlocked = get_user_unlocked_themes(hh_id)
        if payload.theme_code not in unlocked:
            raise HTTPException(status_code=403, detail='Theme is locked.')

    if not update_user_selected_interface(hh_id, payload.theme_code):
        raise HTTPException(status_code=404, detail='User not found.')
    return {'selected_theme': payload.theme_code}


@router.get('/me')
async def my_billing(request: Request) -> dict[str, object]:
    hh_id = await _require_hh_id(request)
    billing = get_user_billing(hh_id)
    if billing is None:
        raise HTTPException(status_code=404, detail='User not found.')

    now = datetime.now(timezone.utc)
    current_period_end = _parse_iso(billing.get('current_period_end') if isinstance(billing, dict) else None)
    days_left = 0
    if current_period_end:
        delta_seconds = (current_period_end - now).total_seconds()
        days_left = max(0, ceil(delta_seconds / 86400))

    status_raw = billing.get('status') if isinstance(billing.get('status'), str) else 'inactive'
    if current_period_end and current_period_end > now:
        status = 'active'
    else:
        status = status_raw
    if status not in ALLOWED_STATUSES:
        status = 'inactive'
    return {
        'plan_code': billing.get('plan_code'),
        'current_period_end': current_period_end.isoformat() if current_period_end else None,
        'days_left': days_left,
        'auto_renew_enabled': bool(billing.get('auto_renew_enabled')),
        'status': status,
    }


@router.patch('/auto-renew')
async def toggle_auto_renew(payload: AutoRenewRequest, request: Request) -> dict[str, bool]:
    hh_id = await _require_hh_id(request)
    if payload.enabled:
        raise HTTPException(status_code=400, detail='Автосписание временно отключено.')
    updated = update_user_billing(hh_id=hh_id, auto_renew_enabled=False, sync_legacy_subscription=False)
    if not updated:
        raise HTTPException(status_code=404, detail='User not found.')
    return {'auto_renew_enabled': False}


async def process_recurring_payments() -> None:
    now = datetime.now(timezone.utc)
    pending_cutoff = now.replace(microsecond=0) - timedelta(minutes=30)
    users = get_users_for_recurring(now.isoformat(), pending_cutoff.isoformat())
    service = YooKassaService()
    for user in users:
        hh_id = str(user.get('hh_id', '')).strip()
        plan_code = '1_month'
        payment_method_id = str(user.get('payment_method_id', '')).strip()
        if not hh_id or not plan_code or not payment_method_id:
            continue
        try:
            payment = await service.create_recurring_payment(
                plan_code=plan_code,
                hh_id=hh_id,
                payment_method_id=payment_method_id,
            )
            record_payment(
                payment_id=payment['payment_id'],
                hh_id=hh_id,
                plan_code=plan_code,
                amount=payment['amount'],
                currency=payment['currency'],
            )
        except YooKassaServiceError:
            update_user_billing(hh_id=hh_id, status='past_due', sync_legacy_subscription=False)


async def _require_hh_id(request: Request) -> str:
    access_token = request.cookies.get('access_token')
    if not access_token:
        raise HTTPException(status_code=401, detail='Unauthorized.')

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get('https://api.hh.ru/me', headers={'Authorization': f'Bearer {access_token}'})
    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail='Invalid access token.')
    payload = response.json()
    hh_id = str(payload.get('id', '')).strip()
    if not hh_id:
        raise HTTPException(status_code=401, detail='Unable to resolve user id.')
    return hh_id


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _months_for_plan(plan_code: str) -> int:
    mapping = {'1_month': 1, '6_months': 6, '12_months': 12}
    months = mapping.get(plan_code)
    if months is None:
        raise HTTPException(status_code=400, detail='Unsupported plan_code.')
    return months


def _add_calendar_months(start: datetime, months: int) -> datetime:
    year = start.year + ((start.month - 1 + months) // 12)
    month = ((start.month - 1 + months) % 12) + 1
    day = min(start.day, monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def _safe_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0
