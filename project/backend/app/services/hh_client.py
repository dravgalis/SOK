class HHClient:
    async def exchange_code(self, code: str) -> dict:
        """MVP-заглушка. Здесь позже будет запрос в HH API."""
        return {'access_token': f'mock-token-for-{code}', 'token_type': 'bearer'}
