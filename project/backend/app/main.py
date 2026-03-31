from fastapi import FastAPI

from app.api.auth import router as hh_auth_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get('/')
async def healthcheck() -> dict:
    return {'status': 'ok'}


app.include_router(hh_auth_router, prefix='/api')
