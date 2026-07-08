from datetime import date, datetime
from decimal import Decimal

from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import is_aware, is_naive, make_aware, make_naive
from unicodedata import normalize


class Coerce:
    SPACES = (
        '\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002'
        '\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000'
    )
    FALSEY_STRINGS = ('0', '-', 'f', 'false', 'falso', 'n', 'nao', 'não', 'no', 'none', 'nil', 'nihil', 'null')

    @classmethod
    def as_bool(cls, value):
        if isinstance(value, str):
            value = value.strip(cls.SPACES).casefold()
            return bool(value) and value not in cls.FALSEY_STRINGS
        return bool(value)

    @staticmethod
    def as_datetime(value, default=None, *, parse_format: str = None, tz_aware: bool | None = True):
        if isinstance(value, (int, float)):
            value = datetime.fromtimestamp(value)
        elif isinstance(value, str):
            try:
                if parse_format:
                    value = datetime.strptime(value, parse_format)
                else:
                    value = parse_datetime(value)
            except ValueError:
                return default
        if value.__class__ is date:
            value = datetime(year=value.year, month=value.month, day=value.day)
        if isinstance(value, datetime):
            if tz_aware is True and is_naive(value):
                value = make_aware(value)
            elif tz_aware is False and is_aware(value):
                value = make_naive(value)
            return value
        return default

    @staticmethod
    def as_date(value, default=None):
        if isinstance(value, (int, float)):
            value = datetime.fromtimestamp(value).date()
        elif isinstance(value, str):
            try:
                value = parse_date(value)
            except ValueError:
                return default
        if value.__class__ is date:
            value = datetime(year=value.year, month=value.month, day=value.day)
        if isinstance(value, datetime):
            if is_naive(value):
                value = make_aware(value)
            value = value.date()
        return value if isinstance(value, date) else default

    @staticmethod
    def digits(value):
        return '' if value in (Ellipsis, None) else ''.join(c for c in str(value) if c.isdecimal())

    @staticmethod
    def as_decimal(value):
        return Decimal(str(value or 0.0))

    @staticmethod
    def ascii(value):
        return normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('utf-8')
