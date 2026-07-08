from base64 import b64decode
from os import getenv
from pathlib import Path

from django.conf import settings


def getenv_str(key, default: str = None, *, decode: bool = False):
    if (strval := getenv(key)) is not None:
        if decode:
            strval = b64decode(strval).decode('utf-8')
        return strval
    return default


def getenv_split(key, default: list = None, *, sep=';', maxsplit=-1, decode: bool = False):
    if (strval := getenv_str(key, decode=decode)) is not None:
        return strval.split(sep, maxsplit)
    return default or []


def media_dir(*parts, filename: str = None):
    mdir = Path(settings.MEDIA_ROOT, *parts)
    mdir.mkdir(parents=True, exist_ok=True)
    return mdir / filename if filename else mdir
