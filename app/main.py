import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import admin, auth, debug, employer
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def startup_event() -> None:
    init_users_table()


@app.get('/')
def root() -> dict[str, str]:
    return {'status': 'ok'}


app.include_router(auth.router, prefix='/api/auth')
app.include_router(employer.router, prefix='/api')
app.include_router(admin.router)

app.include_router(debug.router, prefix='/api/debug')
