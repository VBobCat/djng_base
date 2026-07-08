from datetime import timedelta
from pathlib import Path

from .env_loader import Env

_env = Env(__file__)

BASE_DIR = _env.base_dir
SECRET_KEY = _env.secret_key
DEBUG = _env.debug
ALLOWED_HOSTS = _env.allowed_hosts
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS = _env.allowed_origins
CORS_EXPOSE_HEADERS = ('Content-Disposition',)


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',  # dep: https://pypi.org/project/django-cors-headers/
    'rest_framework',  # dep: https://pypi.org/project/djangorestframework/
    'rest_framework_simplejwt',  # dep: https://pypi.org/project/djangorestframework-simplejwt/
    'django_celery_beat',  # dep: https://pypi.org/project/django-celery-beat/
    'django_celery_results',  # dep: https://pypi.org/project/django-celery-results/
    'health_check',  # dep: https://pypi.org/project/django-health-check/
    'django_probes',  # dep: https://pypi.org/project/django-probes/
    'django_extensions',  # dep: https://pypi.org/project/django-extensions/
    'drf_spectacular',  # dep: https://pypi.org/project/drf-spectacular/
    'drf_spectacular_sidecar',  # dep: https://pypi.org/project/drf-spectacular-sidecar/
    *_env.project_apps,
    'django_cleanup.apps.CleanupConfig',  # dep: https://pypi.org/project/django-cleanup/
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # dep: https://pypi.org/project/django-cors-headers/
    'whitenoise.middleware.WhiteNoiseMiddleware',  # dep: https://pypi.org/project/whitenoise/
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'djng.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'base.wsgi.application'

# Database https://docs.djangoproject.com/en/6.0/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {'connect_timeout': 15},
        **_env.postgres_conninfo,
    }
}

CACHES = {'default': {'BACKEND': 'django_valkey.cache.ValkeyCache', 'LOCATION': f'{_env.valkey_url}/0'}}

# Password validation https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# Internationalization https://docs.djangoproject.com/en/6.0/topics/i18n/
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Whitenoise settings: https://whitenoise.readthedocs.io/en/stable/django.html
WHITENOISE_INDEX_FILE = True  # dep: https://pypi.org/project/whitenoise/
WHITENOISE_ROOT = _env.whitenoise_root
WHITENOISE_MANIFEST_STRICT = False

# Static files (CSS, JavaScript, Images) https://docs.djangoproject.com/en/6.0/howto/static-files/
STATIC_URL = 'static/'
MEDIA_ROOT = _env.media_root
MEDIA_URL = 'media/'
STATICFILES_DIRS = _env.staticfiles_dirs
STATIC_ROOT = BASE_DIR / 'static'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Django REST Framework settings: https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_FILTER_BACKENDS': ['common.rest.filters.JsonParameterFilterBackend'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_SCHEMA_CLASS': 'common.rest.schema.CustomAutoSchema',
    'PAGE_SIZE': 10,
}

# Simple JWT settings: https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html#settings
SIMPLE_JWT = {
    'AUTH_TOKEN_CLASSES': ['rest_framework_simplejwt.tokens.SlidingToken'],
    'ISSUER': 'DJNG',
    'AUDIENCE': 'DJNG',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=60),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(minutes=60),
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'exp',
    'TOKEN_TYPE_CLAIM': 'jwt',
    'UPDATE_LAST_LOGIN': True,
    'USER_ID_CLAIM': 'sub',
}

TIKA_URL = _env.tika_url
GOTENBERG_URL = _env.gotenberg_url

# Celery settings: https://docs.celeryproject.org/en/stable/userguide/configuration.html
if _env.enable_db_periodic_tasks:
    CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
else:
    _BEAT_SCHEDULE_PATH = MEDIA_ROOT.joinpath('temp', 'celerybeat-schedule').resolve()
    _BEAT_SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CELERY_BEAT_SCHEDULE_FILENAME = str(_BEAT_SCHEDULE_PATH)
CELERY_BROKER_URL = f'{_env.redis_url}/1'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_RESULT_EXPIRES = timedelta(days=3)
CELERY_RESULT_EXTENDED = True
CELERY_TASK_REMOTE_TRACEBACKS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_TASK_SOFT_TIME_LIMIT = 28800  # 8h
CELERY_TASK_TIME_LIMIT = 30000  # 8h+20min
CELERY_TASK_TRACK_STARTED = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_DEDUPLICATE_SUCCESSFUL_TASKS = True
CELERY_WORKER_SEND_TASK_EVENTS = True

SPECTACULAR_SETTINGS = {
    'DESCRIPTION': 'Base para aplicações Django',
    'REDOC_DIST': 'SIDECAR',
    'SWAGGER_UI_DIST': 'SIDECAR',  # shorthand to use the sidecar instead
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'TITLE': 'DJNG_BASE',
    'VERSION': '0.1',
}
