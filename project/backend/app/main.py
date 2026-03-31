from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import router as hh_auth_router
from .core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
async def healthcheck() -> dict:
    return {'status': 'ok'}


app.include_router(hh_auth_router, prefix='/api')
