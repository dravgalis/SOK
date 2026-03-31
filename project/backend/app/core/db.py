from typing import AsyncGenerator


async def get_db() -> AsyncGenerator[None, None]:
    """MVP-заглушка для зависимости БД."""
    yield
