"""Explicit production configuration; local development uses loopback only."""
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY; use DJANGO_DEBUG=1 only for local development.")
    SECRET_KEY = "local-development-only-do-not-use-in-production-7dad8d"
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("local-development", "replace-", "django-insecure-"))):
    raise ImproperlyConfigured("Production requires a random secret of at least 50 characters.")
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]" if DEBUG else "").split(",") if h.strip()]
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Set explicit DJANGO_ALLOWED_HOSTS for production.")
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x]
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "portal"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "portal.middleware.LoginThrottleMiddleware", "portal.middleware.PrivateResponseMiddleware"]
ROOT_URLCONF = "maritime.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "portal.context.workspace"]}}]
WSGI_APPLICATION = "maritime.wsgi.application"
database_url = os.environ.get("DATABASE_URL")
if database_url:
    parsed_db = urlparse(database_url)
    if parsed_db.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL URL.")
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": unquote(parsed_db.path[1:]), "USER": unquote(parsed_db.username or ""), "PASSWORD": unquote(parsed_db.password or ""), "HOST": parsed_db.hostname, "PORT": parsed_db.port or 5432, "CONN_MAX_AGE": 60, "CONN_HEALTH_CHECKS": True, "OPTIONS": {"sslmode": parse_qs(parsed_db.query).get("sslmode", ["require"])[0]}}}
elif DEBUG or os.environ.get("DJANGO_TESTING") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "workspace.sqlite3", "OPTIONS": {"timeout": 20}}}
else:
    raise ImproperlyConfigured("Set DATABASE_URL to a PostgreSQL database for production.")
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = LOGIN_URL
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Set only when a trusted reverse proxy strips and sets this header itself.
if os.environ.get("TRUST_PROXY_HTTPS") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_000_000
FILE_UPLOAD_MAX_MEMORY_SIZE = 1_000_000
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "")
PASSWORD_RESET_TIMEOUT = 3600
