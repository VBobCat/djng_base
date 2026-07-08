from base64 import urlsafe_b64encode
from itertools import chain, product
from os import getenv
from pathlib import Path
from random import randbytes
from hashlib import sha256

from dotenv import load_dotenv


class Env:
    _falsey_strs = frozenset(
        ('', '0', '-', 'f', 'false', 'falso', 'n', 'nao', 'não', 'no', 'none', 'nil', 'nihil', 'null'),
    )

    def __init__(self, settings_file: str | Path):
        self._base_dir = Path(settings_file).resolve().parent.parent
        self._proj_dir = self._base_dir.parent.resolve()
        _env_file = next(chain(*(d.glob('.env') for d in (self._base_dir, *self._base_dir.parents))), None)
        if _env_file:
            load_dotenv(_env_file)
        self._secret_key = getenv('DJANGO_SECRET_KEY', urlsafe_b64encode(randbytes(64)).decode('ascii'))
        self._secret_key_hash = bytes(reversed(sha256(self._secret_key.encode('utf-8')).digest()))
        self._debug = (
            ((_debug := getenv('DJANGO_DEBUG')) is not None)
            and _debug.strip().casefold() not in self._falsey_strs,
        )
        self._allowed_hosts = sorted(filter(bool, map(str.strip, getenv('DJANGO_ALLOWED_HOSTS', '').split(';'))))
        _allowed_schemas = filter(bool, map(str.strip, getenv('DJANGO_ALLOWED_SCHEMAS', '').split(';')))
        _allowed_ports = map(str.strip, getenv('DJANGO_ALLOWED_PORTS', '').split(';'))
        self._allowed_origins = sorted(
            {f'{schema}://{host}:{port}'.rstrip(':') for schema, host, port in
             product(_allowed_schemas, self._allowed_hosts, _allowed_ports)},
        )
        self._project_apps = sorted(
            ('.'.join(apps_py.parent.relative_to(self._base_dir).parts)
             for apps_py in self._base_dir.glob('**/apps.py')),
        )
        self._is_docker = (
            Path('/.dockerenv').is_file()
            or (cgroup := Path('/proc/self/cgroup')).is_file()
            and 'docker' in cgroup.read_text()
        )
        self._postgres_db = getenv('POSTGRES_DB', 'postgres')
        self._postgres_user = getenv('POSTGRES_USER', 'postgres')
        self._postgres_pw = getenv('POSTGRES_PASSWORD', 'postgres')
        self._postgres_host = 'postgres' if self._is_docker else 'localhost'
        self._postgres_port = (
            getenv('POSTGRES_PORT', '5432')
            if self._is_docker
            else getenv('POSTGRES_HOST_PORT', '5432')
        )
        self._firefox_url = 'http://{0}:{1}'.format(
            'firefox' if self._is_docker else 'localhost',
            getenv('FIREFOX_PORT', '4444') if self._is_docker else getenv('FIREFOX_HOST_PORT', '4444'),
        )
        self._gotenberg_url = 'http://{0}:{1}'.format(
            'gotenberg' if self._is_docker else 'localhost',
            getenv('GOTENBERG_PORT', '3000') if self._is_docker else getenv('GOTENBERG_HOST_PORT', '3000'),
        )
        self._tika_url = 'http://{0}:{1}'.format(
            'tika' if self._is_docker else 'localhost',
            getenv('TIKA_PORT', '9998') if self._is_docker else getenv('TIKA_HOST_PORT', '9998'),
        )
        self._valkey_url = 'valkey://{0}:{1}'.format(
            'valkey' if self._is_docker else 'localhost',
            getenv('VALKEY_PORT', '6379') if self._is_docker else getenv('VALKEY_HOST_PORT', '6379'),
        )
        self._redis_url = self._valkey_url.replace('valkey://', 'redis://')
        self._whitenoise_root = next(
            (index.parent.resolve() for index in (self._proj_dir / 'frontend' / 'dist').rglob('index.html')), None,
        )
        self._media_root = Path(getenv('DJANGO_MEDIA_ROOT') or getenv('HOST_MEDIA_ROOT') or self._base_dir / 'media')
        if not self._media_root.is_absolute():
            self._media_root = self._base_dir.joinpath(self._media_root)
        if not (self._media_root and self._media_root.is_dir()):
            self._media_root = self._base_dir / 'media'
            self._media_root.mkdir(parents=True, exist_ok=True)
        self._staticfiles_dirs = [self._whitenoise_root] if self._whitenoise_root else []
        self._enable_db_periodic_tasks = (
            ((_enable_periodic_tasks := getenv('DJANGO_ENABLE_DB_PERIODIC_TASKS')) is not None)
            and _enable_periodic_tasks.strip().casefold() not in self._falsey_strs,
        )

    @property
    def base_dir(self):
        return self._base_dir

    @property
    def secret_key(self):
        return self._secret_key

    @property
    def debug(self):
        return self._debug

    @property
    def allowed_hosts(self):
        return self._allowed_hosts

    @property
    def project_apps(self):
        return self._project_apps

    @property
    def allowed_origins(self):
        return self._allowed_origins

    @property
    def postgres_conninfo(self):
        return {
            'NAME': self._postgres_db,
            'USER': self._postgres_user,
            'PASSWORD': self._postgres_pw,
            'HOST': self._postgres_host,
            'PORT': self._postgres_port,
        }

    @property
    def firefox_url(self):
        return self._firefox_url

    @property
    def gotenberg_url(self):
        return self._gotenberg_url

    @property
    def tika_url(self):
        return self._tika_url

    @property
    def valkey_url(self):
        return self._valkey_url

    @property
    def redis_url(self):
        return self._redis_url

    @property
    def media_root(self):
        return self._media_root

    @property
    def staticfiles_dirs(self):
        return self._staticfiles_dirs

    @property
    def is_docker(self):
        return self._is_docker

    @property
    def whitenoise_root(self):
        return self._whitenoise_root

    @property
    def enable_db_periodic_tasks(self):
        return self._enable_db_periodic_tasks
