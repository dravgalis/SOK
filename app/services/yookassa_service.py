import base64
import os
import uuid
from datetime import datetime, timezone

import httpx

PLAN_PRICES: dict[str, tuple[str, int]] = {
    '1_month': ('990.00', 1),
    '6_months': ('4990.00', 6),
    '12_months': ('8990.00', 12),
}


class YooKassaServiceError(Exception):
    pass


class YooKassaService:
    def __init__(self) -> None:
        self.shop_id = os.getenv('YOOKASSA_SHOP_ID', '').strip()
        self.secret_key = os.getenv('YOOKASSA_SECRET_KEY', '').strip()
        # FRONTEND_PAYMENT_URL используется только для возврата после оплаты
        # если не задан — fallback на FRONTEND_APP_URL
        self.frontend_payment_url = (os.getenv('FRONTEND_PAYMENT_URL') or os.getenv('FRONTEND_APP_URL')).strip()
        self.currency = os.getenv('YOOKASSA_CURRENCY', 'RUB').strip().upper()
        self.api_url = 'https://api.yookassa.ru/v3/payments'

    def plan_price(self, plan_code: str) -> str:
        plan = PLAN_PRICES.get(plan_code)
        if plan is None:
            raise YooKassaServiceError('Unsupported plan_code.')
        return plan[0]

    def plan_months(self, plan_code: str) -> int:
        plan = PLAN_PRICES.get(plan_code)
        if plan is None:
            raise YooKassaServiceError('Unsupported plan_code.')
        return plan[1]

    async def create_payment(self, *, plan_code: str, hh_id: str) -> dict[str, str]:
        if not self.shop_id or not self.secret_key:
            raise YooKassaServiceError('YooKassa credentials are not configured.')

        amount = self.plan_price(plan_code)
        payload = {
            'amount': {'value': amount, 'currency': self.currency},
            'capture': True,
            'confirmation': {
                'type': 'redirect',
                'return_url': f"{self.frontend_payment_url.rstrip('/')}/payment-return",
            },
            'description': f'SOK subscription {plan_code}',
            'save_payment_method': True,
            'metadata': {'hh_id': hh_id, 'plan_code': plan_code},
        }
        response_data = await self._post_payment(payload)
        confirmation = response_data.get('confirmation') if isinstance(response_data.get('confirmation'), dict) else {}
        confirmation_url = confirmation.get('confirmation_url')
        payment_id = response_data.get('id')
        if not isinstance(confirmation_url, str) or not isinstance(payment_id, str):
            raise YooKassaServiceError('Invalid response from YooKassa.')
        return {'confirmation_url': confirmation_url, 'payment_id': payment_id, 'amount': amount, 'currency': self.currency}

    async def create_recurring_payment(self, *, plan_code: str, hh_id: str, payment_method_id: str) -> dict[str, str]:
        if not self.shop_id or not self.secret_key:
            raise YooKassaServiceError('YooKassa credentials are not configured.')

        amount = self.plan_price(plan_code)
        payload = {
            'amount': {'value': amount, 'currency': self.currency},
            'payment_method_id': payment_method_id,
            'capture': True,
            'description': f'SOK recurring subscription {plan_code}',
            'metadata': {'hh_id': hh_id, 'plan_code': plan_code, 'recurring': '1'},
        }
        response_data = await self._post_payment(payload)
        payment_id = response_data.get('id')
        if not isinstance(payment_id, str):
            raise YooKassaServiceError('Invalid recurring payment response from YooKassa.')
        return {'payment_id': payment_id, 'amount': amount, 'currency': self.currency}

    async def _post_payment(self, payload: dict[str, object]) -> dict[str, object]:
        auth_raw = f'{self.shop_id}:{self.secret_key}'.encode()
        auth_header = base64.b64encode(auth_raw).decode()
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Idempotence-Key': str(uuid.uuid4()),
            'Content-Type': 'application/json',
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(self.api_url, json=payload, headers=headers)
        if response.status_code >= 400:
            raise YooKassaServiceError(f'YooKassa API error: {response.text}')
        data = response.json()
        if not isinstance(data, dict):
            raise YooKassaServiceError('YooKassa returned invalid payload.')
        return data


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
