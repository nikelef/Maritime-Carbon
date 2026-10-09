"""Waitress entry point for Render or an explicitly trusted HTTPS proxy."""
import ipaddress
import os

from django.core.exceptions import ImproperlyConfigured
from waitress import serve


def server_options(environ=None):
    """Validate deployment configuration without opening a listening socket."""
    environ = os.environ if environ is None else environ
    trust_https = environ.get("TRUST_PROXY_HTTPS", "0")
    proxy = environ.get("WAITRESS_TRUSTED_PROXY", "").strip()
    if trust_https not in ("0", "1"):
        raise ImproperlyConfigured("TRUST_PROXY_HTTPS must be 0 or 1.")
    options = {
        "listen": "0.0.0.0:8000",
        "threads": 4,
        "clear_untrusted_proxy_headers": True,
    }
    if trust_https == "0":
        if proxy:
            raise ImproperlyConfigured("WAITRESS_TRUSTED_PROXY requires TRUST_PROXY_HTTPS=1.")
        return options
    try:
        if not proxy or "%" in proxy:
            raise ValueError
        proxy = str(ipaddress.ip_address(proxy))
    except ValueError as exc:
        raise ImproperlyConfigured(
            "TRUST_PROXY_HTTPS=1 requires WAITRESS_TRUSTED_PROXY to be one IPv4 or IPv6 address; "
            "hostnames, networks and wildcard trust are not supported."
        ) from exc
    # Trust the scheme only. Keep REMOTE_ADDR as the direct peer for login buckets.
    options.update(
        trusted_proxy=proxy,
        trusted_proxy_count=1,
        trusted_proxy_headers={"x-forwarded-proto"},
    )
    return options


def main():
    if os.environ.get("RENDER") == "true":
        # Docker runs this entry point too. Configure Render's secrets, hostname,
        # migrations and HTTPS scheme before importing Django's WSGI application.
        from .render import main as render_main

        return render_main()
    options = server_options()
    from .wsgi import application

    serve(application, **options)


if __name__ == "__main__":
    main()
