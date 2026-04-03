import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, debug, employer

FRONTEND_ORIGIN = 'https://sok-app.onrender.com'


def _resolve_cors_origins() -> list[str]:
    raw = os.getenv('CORS_ORIGINS', FRONTEND_ORIGIN)
    parsed = [origin.strip() for origin in raw.split(',') if origin.strip()]
    if FRONTEND_ORIGIN not in parsed:
        parsed.append(FRONTEND_ORIGIN)
    return parsed


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
def root() -> dict[str, str]:
    return {'status': 'ok'}


app.include_router(auth.router, prefix='/api/auth')
app.include_router(employer.router, prefix='/api')

app.include_router(debug.router, prefix='/api/debug')
