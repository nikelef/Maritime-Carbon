from datetime import timedelta
import hashlib
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from .models import LoginBucket


class LoginThrottleMiddleware:
    """Database-backed buckets shared by workers; never trust forwarded IPs.

    Five failures per submitted username or 30 per direct client IP per 15 min.
    Apply to both customer and operator login. Edge rate limits remain advisable.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST" or request.path not in ("/accounts/login/", "/admin/login/"):
            return self.get_response(request)
        cutoff = timezone.now() - timedelta(minutes=15)
        raw = [("user:" + request.POST.get("username", "").casefold().strip()[:150], 5), ("ip:" + request.META.get("REMOTE_ADDR", "unknown"), 30)]
        keys = [(hashlib.sha256(k.encode()).hexdigest(), limit) for k, limit in raw]
        for key, limit in keys:
            if LoginBucket.objects.filter(key=key, started_at__gt=cutoff, failures__gte=limit).exists():
                response = HttpResponse("Too many sign-in attempts. Please wait 15 minutes and try again.", status=429)
                response["Retry-After"] = "900"
                return response
        response = self.get_response(request)
        if request.user.is_authenticated and response.status_code in (302, 303):
            LoginBucket.objects.filter(key=keys[0][0]).delete()
        elif response.status_code == 200:
            for key, _ in keys:
                bucket, _ = LoginBucket.objects.get_or_create(key=key)
                LoginBucket.objects.filter(pk=bucket.pk, started_at__lte=cutoff).update(failures=0, started_at=timezone.now())
                LoginBucket.objects.filter(pk=bucket.pk).update(failures=F("failures") + 1)
        return response


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        add_never_cache_headers(response)
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
