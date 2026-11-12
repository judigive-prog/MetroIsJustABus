import logging
from pathlib import Path

import structlog

from common.logging import redact_secrets
from config.env import env, read_secret

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = (
    read_secret(env.secret_key_file, default="notif-test-secret-key-32charslong")
    if env.secret_key_file
    else "notif-test-secret-key-32charslong"
)
DEBUG = env.debug
ALLOWED_HOSTS = env.allowed_hosts

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "drf_spectacular",
    "common",
    "subscriptions",
    "preferences",
    "inbox",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "common.correlation.CorrelationIdMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env.postgres_host,
        "PORT": env.postgres_port,
        "NAME": env.postgres_db,
        "USER": env.postgres_user,
        "PASSWORD": read_secret(env.postgres_password_file, default="") if env.postgres_password_file else "",
    }
}

USE_TZ = True
TIME_ZONE = "UTC"
USE_I18N = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

JWT_PUBLIC_KEY = read_secret(env.jwt_public_key_file, default="") if env.jwt_public_key_file else ""
JWT_ISSUER = env.jwt_issuer or "test-core-backend"

# Sandboxed email settings (Mailpit, ADR A-06)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env.email_host
EMAIL_PORT = env.email_port
EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = env.default_from_email

# RabbitMQ settings
RABBITMQ_HOST = env.rabbitmq_host
RABBITMQ_PORT = env.rabbitmq_port
RABBITMQ_USER = env.rabbitmq_user
RABBITMQ_PASSWORD = read_secret(env.rabbitmq_password_file, default="") if env.rabbitmq_password_file else ""

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
    "TITLE": "MetroIsJustABus notification API",
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
