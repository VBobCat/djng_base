from __future__ import annotations

import base64
import binascii
import json
import regex
from typing import Any, AnyStr, Mapping
from urllib.parse import parse_qsl, urlencode
import httpx


def request_to_string(r: httpx.Request):
    return f'{r.method} {r.url}\n{r.headers}\n\n{r.content.decode(encoding='utf-8', errors='ignore')}'


def response_to_string(r: httpx.Response):
    return f'{r.status_code} {r.url}\n{r.headers}\n\n{r.content.decode(encoding=r.encoding or 'utf-8', errors='ignore')}'


# =====================================================================
# Configurações
# =====================================================================

REDACTED = '***REDACTED***'

SENSITIVE_KEYS = {
    'password',
    'token',
}

SENSITIVE_HEADERS = {
    'authorization',
    'cookie',
    'set-cookie',
    'x-api-key',
    'x-auth-token',
}

BASE64_MIN_LENGTH = 256  # evita falsos positivos

# =====================================================================
# Regex auxiliares
# =====================================================================

_BASE64_RE = regex.compile(r'^[A-Za-z0-9+/]+={0,2}$')

_DATA_URL_BASE64_RE = regex.compile(
    r'(data:'
    r'(?P<mime>[-\w.+/]+)'
    r';base64,'
    r'(?P<data>[A-Za-z0-9+/=\s]+))',
    regex.IGNORECASE,
)


# =====================================================================
# Headers
# =====================================================================

def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    result = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADERS:
            result[k] = REDACTED
        else:
            result[k] = v
    return result


def _serialize_headers(headers: Mapping[str, str]) -> str:
    return ''.join(f'{k}: {v}\r\n' for k, v in headers.items())


# =====================================================================
# Base64 helpers
# =====================================================================

def _try_decode_base64(value: AnyStr) -> int | None:
    """
    Retorna o tamanho em bytes do conteúdo decodificado
    se a string for Base64 válida; caso contrário, None.
    """
    if len(value) < BASE64_MIN_LENGTH:
        return None

    if len(value) % 4 != 0:
        return None

    if not _BASE64_RE.fullmatch(value):
        return None

    try:
        decoded = base64.b64decode(value, validate=True)
    except binascii.Error:
        return None

    return len(decoded)


def _redact_data_url_base64(text: str) -> str:
    def replacer(match: regex.Match) -> str:
        mime = match.group('mime')
        data = match.group('data').replace('\n', '').replace('\r', '')

        decoded_len = _try_decode_base64(data)
        if decoded_len is None:
            return match.group(0)

        return (
            f'data:{mime};base64,'
            f'<conteúdo base64: {decoded_len} bytes decodificados>'
        )

    return _DATA_URL_BASE64_RE.sub(replacer, text)


# =====================================================================
# JSON redaction
# =====================================================================

def _redact_json_value(value: Any) -> Any:
    if isinstance(value, str):
        # data URLs base64 (HTML, CSS, SVG, etc.)
        value = _redact_data_url_base64(value)

        # base64 "puro"
        decoded_len = _try_decode_base64(value)
        if decoded_len is not None:
            return f'<conteúdo base64: {decoded_len} bytes decodificados>'

        return value

    if isinstance(value, Mapping):
        return _redact_mapping(value)

    if isinstance(value, list):
        return [_redact_json_value(v) for v in value]

    return value


def _redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for k, v in data.items():
        key_lower = k.lower()

        if key_lower in SENSITIVE_KEYS:
            result[k] = REDACTED
            continue

        if isinstance(v, Mapping):
            result[k] = _redact_mapping(v)
            continue

        if isinstance(v, list):
            result[k] = [_redact_json_value(i) for i in v]
            continue

        if isinstance(v, str):
            result[k] = _redact_json_value(v)
            continue

        result[k] = v

    return result


def _redact_json(body: bytes) -> bytes:
    try:
        data = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        return body

    if isinstance(data, Mapping):
        data = _redact_mapping(data)
    elif isinstance(data, list):
        data = [_redact_json_value(v) for v in data]

    return json.dumps(data, separators=(',', ':')).encode('utf-8')


# =====================================================================
# Outros formatos de corpo
# =====================================================================

def _redact_form_urlencoded(body: bytes) -> bytes:
    parsed = parse_qsl(body.decode('utf-8'), keep_blank_values=True)
    redacted = [
        (k, REDACTED if k.lower() in SENSITIVE_KEYS else v)
        for k, v in parsed
    ]
    return urlencode(redacted).encode('utf-8')


def _redact_multipart(body: bytes) -> bytes:
    """
    Heurística segura para logging:
    substitui apenas valores de campos sensíveis.
    """
    text = body.decode('utf-8', errors='replace')

    for key in SENSITIVE_KEYS:
        pattern = (
            rf'(name="{regex.escape(key)}"\s*\r?\n\r?\n)'
            rf'(.*?)(\r?\n--)'
        )
        text = regex.sub(
            pattern,
            rf'\1{REDACTED}\3',
            text,
            flags=regex.DOTALL | regex.IGNORECASE,
        )

    return text.encode('utf-8')


# =====================================================================
# Detecção de binário
# =====================================================================
NON_BINARY_CONTENT_TYPES = {
    'application/json',
    'application/x-www-form-urlencoded',
    'multipart/form-data',
    'text/*',
    'application/xml',
}


def _is_binary_body(body: bytes, content_type: str) -> bool:
    if not body:
        return False

    ct = content_type.lower()

    if any(ct.startswith(t.rstrip('*')) for t in NON_BINARY_CONTENT_TYPES):
        return False

    if b'\x00' in body:
        return True

    try:
        body.decode('utf-8')
        return False
    except UnicodeDecodeError:
        return True


def _redact_body(body: bytes | None, headers: Mapping[str, str]) -> str | None:
    if not body:
        return None

    content_type = headers.get('content-type', '')

    if _is_binary_body(body, content_type):
        return f'<sequência de {len(body)} bytes>'

    ct = content_type.lower()

    if 'application/json' in ct:
        return _redact_json(body).decode('utf-8', errors='replace')

    if 'application/x-www-form-urlencoded' in ct:
        return _redact_form_urlencoded(body).decode('utf-8', errors='replace')

    if 'multipart/form-data' in ct:
        return _redact_multipart(body).decode('utf-8', errors='replace')

    return body.decode('utf-8', errors='replace')


# =====================================================================
# API pública
# =====================================================================

def serialize_httpx_request(request: httpx.Request) -> str:
    """
    Serializa requisição HTTP/1.x com:
    - ofuscação de dados sensíveis
    - saneamento de base64
    - proteção contra dumping de binários
    Ideal para logging seguro.
    """
    req_headers = _redact_headers(dict(request.headers))
    req_body = _redact_body(request.content, request.headers)
    request_line = f'{request.method} {request.url.raw_path.decode()} HTTP/1.1\n'
    request_section = f'{request_line}{_serialize_headers(req_headers)}\n'
    if req_body:
        request_section += req_body
    return f'----- HTTP REQUEST -----\n{request_section.strip()}'


def serialize_httpx_exchange(response: httpx.Response) -> str:
    """
    Serializa requisição + resposta HTTP/1.x com:
    - ofuscação de dados sensíveis
    - saneamento de base64
    - proteção contra dumping de binários
    Ideal para logging seguro.
    """
    request_block = serialize_httpx_request(response.request)
    resp_headers = _redact_headers(dict(response.headers))
    resp_body = _redact_body(response.content, response.headers)
    status_line = f'HTTP/1.1 {response.status_code} {response.reason_phrase}\n'
    response_section = f'{status_line}{_serialize_headers(resp_headers)}\n'
    if resp_body:
        response_section += resp_body
    return f'{request_block}\n\n----- HTTP RESPONSE -----\n{response_section.strip()}'
