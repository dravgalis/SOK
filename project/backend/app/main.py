from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.admin import router as admin_router
from .api.auth import router as hh_auth_router
from .core.config import get_settings
from .core.db import init_users_table

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
async def startup_event() -> None:
    init_users_table()


@app.get('/')
async def healthcheck() -> dict:
    return {'status': 'ok'}


app.include_router(hh_auth_router, prefix='/api')
app.include_router(admin_router)
