"""Exercise production proxy trust through real Waitress and Django middleware."""
import hashlib
import os
from http.cookies import SimpleCookie
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.wsgi import get_wsgi_application
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from waitress.adjustments import Adjustments
from waitress.proxy_headers import proxy_headers_middleware

from maritime.serve import main, server_options
from portal.models import LoginBucket


class ServerConfigurationTests(SimpleTestCase):
    def test_https_proxy_requires_one_valid_address_before_server_start(self):
        for proxy in ("", "*", "proxy.internal", "10.0.0.0/24", "10.0.0.1,10.0.0.2", "10.0.0.999", "fe80::1%eth0"):
            with self.subTest(proxy=proxy), patch.dict(os.environ, {
                "TRUST_PROXY_HTTPS": "1", "WAITRESS_TRUSTED_PROXY": proxy,
            }, clear=True), patch("maritime.serve.serve") as start_server:
                with self.assertRaises(ImproperlyConfigured):
                    main()
                start_server.assert_not_called()

    def test_only_scheme_is_trusted_and_ipv6_is_normalized(self):
        options = server_options({"TRUST_PROXY_HTTPS": "1", "WAITRESS_TRUSTED_PROXY": "2001:0db8::1"})
        adjustments = Adjustments(**options)
        self.assertEqual(adjustments.trusted_proxy, "2001:db8::1")
        self.assertEqual(adjustments.trusted_proxy_headers, {"x-forwarded-proto"})
        self.assertEqual(adjustments.trusted_proxy_count, 1)
        self.assertTrue(adjustments.clear_untrusted_proxy_headers)

    def test_inconsistent_or_invalid_flag_configuration_is_rejected(self):
        for environ in ({"TRUST_PROXY_HTTPS": "yes"}, {"TRUST_PROXY_HTTPS": "0", "WAITRESS_TRUSTED_PROXY": "10.0.0.10"}):
            with self.subTest(environ=environ), self.assertRaises(ImproperlyConfigured):
                server_options(environ)

    def test_main_passes_validated_options_to_waitress(self):
        environ = {"TRUST_PROXY_HTTPS": "1", "WAITRESS_TRUSTED_PROXY": "10.0.0.10"}
        with patch.dict(os.environ, environ, clear=True), patch("maritime.serve.serve") as start_server:
            main()
        self.assertEqual(start_server.call_args.kwargs, server_options(environ))


@override_settings(
    DEBUG=False,
    ALLOWED_HOSTS=["carbon.example.test"],
    CSRF_TRUSTED_ORIGINS=["https://carbon.example.test"],
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=None,
    SECURE_HSTS_SECONDS=31536000,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ProxyIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user("proxy_user", password="proxy-test-password")

    def wsgi_request(self, path, *, method="GET", data=None, peer="10.0.0.10", forwarded="https", cookie="", origin="", trust=True):
        factory = RequestFactory()
        headers = {
            "HTTP_HOST": "carbon.example.test", "REMOTE_ADDR": peer,
            "SERVER_PORT": "8000", "HTTP_X_FORWARDED_PROTO": forwarded,
            "HTTP_X_FORWARDED_FOR": "198.51.100.77", "HTTP_FORWARDED": "for=198.51.100.77;proto=https",
            "HTTP_COOKIE": cookie, "HTTP_ORIGIN": origin,
        }
        request = (factory.post(path, data or {}, **headers) if method == "POST"
                   else factory.get(path, **headers))
        options = server_options({"TRUST_PROXY_HTTPS": "1", "WAITRESS_TRUSTED_PROXY": "10.0.0.10"} if trust else {})
        adjustments = Adjustments(**options)
        app = proxy_headers_middleware(
            get_wsgi_application(), trusted_proxy=adjustments.trusted_proxy,
            trusted_proxy_count=adjustments.trusted_proxy_count,
            trusted_proxy_headers=adjustments.trusted_proxy_headers,
            clear_untrusted=adjustments.clear_untrusted_proxy_headers,
        )
        captured = {}

        def start_response(status, response_headers, exc_info=None):
            captured.update(status=int(status.split()[0]), headers=response_headers)

        response = app(request.environ, start_response)
        try:
            captured["body"] = b"".join(response)
        finally:
            if hasattr(response, "close"):
                response.close()
        captured["environ"] = request.environ
        return captured

    def test_trusted_https_health_and_login_do_not_redirect(self):
        for path in ("/health/", "/accounts/login/"):
            with self.subTest(path=path):
                response = self.wsgi_request(path)
                self.assertEqual(response["status"], 200)
                self.assertEqual(response["environ"]["wsgi.url_scheme"], "https")
                self.assertIn("Strict-Transport-Security", dict(response["headers"]))
                self.assertNotIn("Location", dict(response["headers"]))

    def test_https_login_post_accepts_csrf_and_sets_secure_session(self):
        page = self.wsgi_request("/accounts/login/")
        cookies = SimpleCookie()
        for key, value in page["headers"]:
            if key.lower() == "set-cookie":
                cookies.load(value)
        token = cookies["csrftoken"].value
        response = self.wsgi_request(
            "/accounts/login/", method="POST", cookie=f"csrftoken={token}",
            origin="https://carbon.example.test",
            data={"username": "proxy_user", "password": "proxy-test-password", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response["status"], 302)
        self.assertEqual(dict(response["headers"])["Location"], "/")
        session_cookies = SimpleCookie()
        for key, value in response["headers"]:
            if key.lower() == "set-cookie":
                session_cookies.load(value)
        self.assertTrue(session_cookies["sessionid"]["secure"])

    def test_other_proxy_headers_are_removed_and_peer_ip_is_retained(self):
        response = self.wsgi_request("/health/")
        self.assertEqual(response["environ"]["REMOTE_ADDR"], "10.0.0.10")
        self.assertNotIn("HTTP_X_FORWARDED_FOR", response["environ"])
        self.assertNotIn("HTTP_FORWARDED", response["environ"])

    def test_failed_login_throttles_the_direct_peer_ip(self):
        page = self.wsgi_request("/accounts/login/")
        cookies = SimpleCookie()
        for key, value in page["headers"]:
            if key.lower() == "set-cookie":
                cookies.load(value)
        token = cookies["csrftoken"].value
        response = self.wsgi_request(
            "/accounts/login/", method="POST", cookie=f"csrftoken={token}",
            origin="https://carbon.example.test",
            data={"username": "proxy_user", "password": "wrong", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response["status"], 200)
        peer_key = hashlib.sha256(b"ip:10.0.0.10").hexdigest()
        forwarded_key = hashlib.sha256(b"ip:198.51.100.77").hexdigest()
        self.assertEqual(LoginBucket.objects.get(key=peer_key).failures, 1)
        self.assertFalse(LoginBucket.objects.filter(key=forwarded_key).exists())

    def test_untrusted_peer_cannot_claim_https(self):
        response = self.wsgi_request("/health/", peer="10.0.0.11")
        self.assertEqual(response["status"], 301)
        self.assertEqual(dict(response["headers"])["Location"], "https://carbon.example.test/health/")
        self.assertEqual(response["environ"]["wsgi.url_scheme"], "http")
        self.assertNotIn("HTTP_X_FORWARDED_PROTO", response["environ"])

    def test_trusted_proxy_http_still_redirects_to_https(self):
        response = self.wsgi_request("/health/", forwarded="http")
        self.assertEqual(response["status"], 301)

    @override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, SECURE_HSTS_SECONDS=0)
    def test_default_local_direct_http_is_unchanged(self):
        response = self.wsgi_request("/health/", peer="127.0.0.1", trust=False)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["environ"]["wsgi.url_scheme"], "http")
        self.assertNotIn("HTTP_X_FORWARDED_PROTO", response["environ"])
