import asyncio
import os
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import admin, auth, billing, debug, employer
from .api.billing import process_recurring_payments
from .core.admin_store import init_users_table

FRONTEND_ORIGIN = 'https://sok-app.onrender.com'
ADMIN_FRONTEND_ORIGIN = 'https://sok-1.onrender.com'


def _resolve_cors_origins() -> list[str]:
    raw = os.getenv('CORS_ORIGINS', FRONTEND_ORIGIN)
    parsed = [origin.strip() for origin in raw.split(',') if origin.strip()]
    if FRONTEND_ORIGIN not in parsed:
        parsed.append(FRONTEND_ORIGIN)
    if ADMIN_FRONTEND_ORIGIN not in parsed:
        parsed.append(ADMIN_FRONTEND_ORIGIN)
    return parsed


app = FastAPI()
recurring_task: asyncio.Task[None] | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


async def _recurring_billing_worker() -> None:
    interval_seconds = max(30, int(os.getenv('RECURRING_CHECK_INTERVAL_SECONDS', '300')))
    while True:
        try:
            await process_recurring_payments()
        except Exception as exc:  # noqa: BLE001
            print('Recurring billing worker error:', exc)
        await asyncio.sleep(interval_seconds)


@app.on_event('startup')
async def startup_event() -> None:
    global recurring_task
    init_users_table()
    recurring_task = asyncio.create_task(_recurring_billing_worker())


@app.on_event('shutdown')
async def shutdown_event() -> None:
    global recurring_task
    if recurring_task is None:
        return
    recurring_task.cancel()
    with suppress(asyncio.CancelledError):
        await recurring_task
    recurring_task = None


@app.get('/')
def root() -> dict[str, str]:
    return {'status': 'ok'}


app.include_router(auth.router, prefix='/api/auth')
app.include_router(employer.router, prefix='/api')
app.include_router(billing.router)
app.include_router(admin.router)

app.include_router(debug.router, prefix='/api/debug')
