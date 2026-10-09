"""Free Render build/start entry point; public TLS is terminated by Render."""
import argparse
import base64
import binascii
import hashlib
import os
import re
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured


def render_hostname(environ):
    host = environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if environ.get("RENDER") != "true" or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com", host
    ):
        raise ImproperlyConfigured("This entry point requires Render and its exact onrender.com hostname.")
    return host


def configure_environment(environ=None):
    environ = os.environ if environ is None else environ
    host = render_hostname(environ)
    if environ.get("DJANGO_DEBUG", "0") != "0":
        raise ImproperlyConfigured("Render must run with DJANGO_DEBUG=0.")
    database_host = urlparse(environ.get("DATABASE_URL", "")).hostname or ""
    if database_host.endswith(".neon.tech") and database_host.split(".")[0].endswith("-pooler"):
        raise ImproperlyConfigured("Use Neon's direct DATABASE_URL (turn Connection pooling off); startup migrations require a session lock.")
    if not environ.get("DJANGO_SECRET_KEY"):
        # Render generates 32 random bytes encoded as 44 characters. Derive a
        # stable Django key that satisfies the app's existing 50-character rule.
        try:
            secret = base64.b64decode(environ.get("RENDER_SECRET_KEY", ""), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ImproperlyConfigured("RENDER_SECRET_KEY must be Render's generated 256-bit secret.") from exc
        if len(secret) != 32:
            raise ImproperlyConfigured("RENDER_SECRET_KEY must be Render's generated 256-bit secret.")
        environ["DJANGO_SECRET_KEY"] = hashlib.sha256(b"maritime-carbon-django:" + secret).hexdigest()
    for key, value in (("DJANGO_ALLOWED_HOSTS", host), ("DJANGO_CSRF_TRUSTED_ORIGINS", "https://" + host)):
        entries = [item.strip() for item in environ.get(key, "").split(",") if item.strip()]
        if value not in entries:
            entries.append(value)
        environ[key] = ",".join(entries)
    environ.setdefault("DJANGO_SETTINGS_MODULE", "maritime.settings")
    return environ


def server_options(environ=None):
    environ = os.environ if environ is None else environ
    render_hostname(environ)
    try:
        port = int(environ.get("PORT", "10000"))
    except ValueError as exc:
        raise ImproperlyConfigured("PORT must be a TCP port number.") from exc
    if not 1024 <= port <= 65535:
        raise ImproperlyConfigured("PORT must be between 1024 and 65535.")
    # Render redirects public HTTP to HTTPS before forwarding to this server.
    # Set the scheme directly and discard all client-supplied proxy headers.
    # No wildcard trust, or assumptions about changing proxy IPs, are needed.
    return {
        "listen": f"0.0.0.0:{port}",
        "threads": 2,
        "url_scheme": "https",
        "clear_untrusted_proxy_headers": True,
    }


def initialize_database():
    from django.core.management import call_command
    from django.db import connection

    if connection.vendor != "postgresql":
        raise ImproperlyConfigured("Render requires PostgreSQL for persistent accounts and saved cases.")
    # Free web services have no pre-deploy command or interactive shell. Run
    # migrations once at startup, serializing overlapping releases in Postgres.
    lock_id = 0x4D41524954494D45
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])
            try:
                call_command("migrate", interactive=False)
                call_command("bootstrap_operator")
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Collect static files without connecting to the database.")
    options = parser.parse_args()
    configure_environment()
    import django
    from django.core.management import call_command

    django.setup()
    call_command("check", deploy=True, fail_level="WARNING")
    if options.build:
        call_command("collectstatic", interactive=False)
        return
    initialize_database()
    from waitress import serve
    from .wsgi import application

    serve(application, **server_options())


if __name__ == "__main__":
    main()
