"""Keep development pages and their scripts/styles in sync across browser caches."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@lru_cache(maxsize=64)
def asset_digest(path, modified_ns, size):
    return sha256(Path(path).read_bytes()).hexdigest()[:12]


@register.simple_tag
def versioned_static(path):
    url = static(path)
    # Production already uses content-hashed manifest filenames.
    if settings.DEBUG:
        source = finders.find(path)
        if source:
            stat = Path(source).stat()
            separator = "&" if "?" in url else "?"
            url += separator + "v=" + asset_digest(source, stat.st_mtime_ns, stat.st_size)
    return url
