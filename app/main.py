from fastapi import FastAPI

from .api import auth

app = FastAPI()


@app.get('/')
def root() -> dict[str, str]:
    return {'status': 'ok'}


app.include_router(auth.router, prefix='/api/auth')
