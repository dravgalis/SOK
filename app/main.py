from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, debug, employer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://sok-app.onrender.com'],
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
