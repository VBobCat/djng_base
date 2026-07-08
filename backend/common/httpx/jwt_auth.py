import base64
import json
import time

import httpx
from httpx import Auth
from jwt.algorithms import get_default_algorithms


class JWTAuth(Auth):
    def __init__(self, algorithms: list[str] = None, *, token: str = None):
        self._algorithms = algorithms or get_default_algorithms()
        self._token_claims = None
        self.token = token or ''

    @property
    def token(self):
        if self._token and self.token_exp > time.time():
            return self._token
        return ''

    @token.setter
    def token(self, value: str):
        try:
            if value:
                parts = value.split('.')
                claims_part = parts[1]
                claims_json = base64.b64decode(f'{claims_part}==')
                self._token_claims = json.loads(claims_json)
            self._token = value or None
        except Exception:
            raise AssertionError('Invalid token')

    @property
    def token_claims(self):
        return self._token_claims

    @property
    def token_exp(self):
        return (self.token_claims or {}).get('exp', 0)

    def token_remaining_time(self) -> float:
        if self._token:
            now = time.time()
            if self.token_exp > now:
                return self.token_exp - now
        return 0.0

    def auth_flow(self, request: httpx.Request):
        if self.token:
            request.headers['Authorization'] = f'Bearer {self.token}'
        yield request
