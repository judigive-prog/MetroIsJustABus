import logging

import structlog
from django.core.management.utils import get_random_secret_key

from common.logging import redact_secrets
from config.env import env, read_secret

if env.secret_key_file:
    SECRET_KEY = env.secret_key_file.read_text(encoding="utf-8").strip()
elif env.debug:
    SECRET_KEY = get_random_secret_key()
else:
    raise RuntimeError("SECRET_KEY_FILE must be configured when DEBUG is false.")

DEBUG = env.debug
ALLOWED_HOSTS = env.allowed_hosts

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "drf_spectacular",
    "common",
    "accounts",
    "network",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "common.correlation.CorrelationIdMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

if env.postgres_password_file:
    _db_password = env.postgres_password_file.read_text(encoding="utf-8").strip()
elif env.debug:
    _db_password = ""
else:
    raise RuntimeError("POSTGRES_PASSWORD_FILE must be configured when DEBUG is false.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env.postgres_host,
        "PORT": env.postgres_port,
        "NAME": env.postgres_db,
        "USER": env.postgres_user,
        "PASSWORD": _db_password,
    }
}

# Only Argon2id is enabled so passwords can never be stored with weaker or reversible schemes (NFR-051).
PASSWORD_HASHERS = [
    "accounts.hashers.CoreArgon2PasswordHasher",
]

USE_TZ = True
TIME_ZONE = "UTC"
USE_I18N = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

JWT_PUBLIC_KEY = read_secret(env.jwt_public_key_file, default="") if env.jwt_public_key_file else ""
JWT_ISSUER = env.jwt_issuer or None

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["common.auth.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["common.permissions.DenyAll"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "common.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MetroIsJustABus core API",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SERVE_AUTHENTICATION": [],
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_secrets,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
