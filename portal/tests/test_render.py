"""Render configuration, HTTPS boundary and safe first-operator provisioning."""
import base64
import io
import os
import subprocess
import sys
import textwrap
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.wsgi import get_wsgi_application
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from waitress.adjustments import Adjustments
from waitress.proxy_headers import proxy_headers_middleware

from maritime.render import configure_environment, initialize_database, server_options
from maritime.serve import main as docker_main
from portal.models import TrialInvitation


class RenderConfigurationTests(SimpleTestCase):
    def environment(self, **overrides):
        return {"RENDER": "true", "RENDER_EXTERNAL_HOSTNAME": "maritime-carbon.onrender.com", "RENDER_SECRET_KEY": base64.b64encode(bytes(range(32))).decode(), **overrides}

    def test_render_generated_secret_is_stable_and_exact_host_and_origin_are_added(self):
        first = configure_environment(self.environment())
        second = configure_environment(self.environment())
        self.assertEqual(first["DJANGO_SECRET_KEY"], second["DJANGO_SECRET_KEY"])
        self.assertEqual(len(first["DJANGO_SECRET_KEY"]), 64)
        self.assertEqual(first["DJANGO_ALLOWED_HOSTS"], "maritime-carbon.onrender.com")
        self.assertEqual(first["DJANGO_CSRF_TRUSTED_ORIGINS"], "https://maritime-carbon.onrender.com")
        self.assertEqual(configure_environment(first), first)

    def test_existing_secret_and_custom_domain_are_preserved(self):
        env = configure_environment(self.environment(DJANGO_SECRET_KEY="existing-secret" * 5, DJANGO_ALLOWED_HOSTS="carbon.example.com", DJANGO_CSRF_TRUSTED_ORIGINS="https://carbon.example.com"))
        self.assertEqual(env["DJANGO_SECRET_KEY"], "existing-secret" * 5)
        self.assertEqual(env["DJANGO_ALLOWED_HOSTS"], "carbon.example.com,maritime-carbon.onrender.com")
        self.assertEqual(env["DJANGO_CSRF_TRUSTED_ORIGINS"], "https://carbon.example.com,https://maritime-carbon.onrender.com")

    def test_local_wildcard_or_unrecognized_hosts_and_debug_are_rejected(self):
        for override in ({"RENDER": "false"}, {"RENDER_EXTERNAL_HOSTNAME": "*"}, {"RENDER_EXTERNAL_HOSTNAME": "evil.example.com"}, {"RENDER_EXTERNAL_HOSTNAME": "https://app.onrender.com"}, {"DJANGO_DEBUG": "1"}):
            with self.subTest(override=override), self.assertRaises(ImproperlyConfigured):
                configure_environment(self.environment(**override))

    def test_missing_or_malformed_generated_secret_is_rejected(self):
        for secret in ("", "replace-with-secret", "a" * 50, base64.b64encode(b"short").decode()):
            with self.subTest(secret=secret), self.assertRaises(ImproperlyConfigured):
                configure_environment(self.environment(RENDER_SECRET_KEY=secret))

    def test_neon_transaction_pooler_is_rejected_before_session_lock_migrations(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "Connection pooling off"):
            configure_environment(self.environment(DATABASE_URL="postgresql://user:password@ep-example-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"))
        self.assertIn("DJANGO_SECRET_KEY", configure_environment(self.environment(DATABASE_URL="postgresql://user:password@ep-example.eu-central-1.aws.neon.tech/neondb?sslmode=require")))

    def test_port_binding_and_proxy_headers_do_not_require_wildcard_trust(self):
        options = server_options(self.environment(PORT="12345"))
        self.assertEqual(options["listen"], "0.0.0.0:12345")
        adjustments = Adjustments(**options)
        self.assertEqual(adjustments.url_scheme, "https")
        self.assertIsNone(adjustments.trusted_proxy)
        self.assertTrue(adjustments.clear_untrusted_proxy_headers)
        for port in ("0", "80", "65536", "10000;invalid"):
            with self.subTest(port=port), self.assertRaises(ImproperlyConfigured):
                server_options(self.environment(PORT=port))

    def test_migrations_and_bootstrap_are_serialized_and_lock_is_released_on_failure(self):
        cursor = MagicMock()
        connection = SimpleNamespace(vendor="postgresql", cursor=MagicMock(), close=MagicMock())
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch("django.db.connection", connection), patch("django.core.management.call_command", side_effect=[None, CommandError("invalid operator")]) as command:
            with self.assertRaises(CommandError):
                initialize_database()
        self.assertEqual(command.call_args_list, [call("migrate", interactive=False), call("bootstrap_operator")])
        self.assertEqual(cursor.execute.call_args_list[0].args[0], "SELECT pg_advisory_lock(%s)")
        self.assertEqual(cursor.execute.call_args_list[-1].args[0], "SELECT pg_advisory_unlock(%s)")
        connection.close.assert_called_once()

    def test_docker_launcher_configures_production_before_loading_wsgi(self):
        # A fresh interpreter reproduces Docker startup: Django settings have
        # not yet been loaded and only Render's generated secret is provided.
        environ = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("DJANGO_", "RENDER_", "BOOTSTRAP_ADMIN_", "WAITRESS_"))
            and key not in ("RENDER", "DATABASE_URL", "TRUST_PROXY_HTTPS", "PORT")
        }
        environ.update(self.environment(PORT="12345", DATABASE_URL="postgresql://test:test@localhost/test?sslmode=require"))
        script = textwrap.dedent("""
            from unittest.mock import patch
            from maritime.serve import main

            with patch("maritime.render.initialize_database") as initialize, patch("waitress.serve") as start:
                main()
                initialize.assert_called_once_with()
                start.assert_called_once()
                application = start.call_args.args[0]
                options = start.call_args.kwargs
                assert options["listen"] == "0.0.0.0:12345"
                assert options["url_scheme"] == "https"
                assert options["clear_untrusted_proxy_headers"] is True
                from django.conf import settings
                assert settings.DEBUG is False
                assert len(settings.SECRET_KEY) == 64
                assert settings.ALLOWED_HOSTS == ["maritime-carbon.onrender.com"]
                assert settings.CSRF_TRUSTED_ORIGINS == ["https://maritime-carbon.onrender.com"]
                from django.test import RequestFactory
                request = RequestFactory().get("/health/", secure=True, HTTP_HOST="maritime-carbon.onrender.com")
                captured = {}
                # The health view queries Postgres; this test checks startup
                # and HTTPS handling without requiring an external database.
                with patch("django.db.connection.cursor"):
                    response = application(request.environ, lambda status, headers: captured.update(status=status))
                    try:
                        assert b"".join(response) == b"ok"
                        assert captured["status"] == "200 OK"
                    finally:
                        response.close()
                print("Docker production startup verified")
        """)
        result = subprocess.run([sys.executable, "-c", script], env=environ, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Docker production startup verified", result.stdout)

    def test_docker_launcher_rejects_incomplete_render_configuration_before_starting(self):
        for overrides in ({"RENDER_SECRET_KEY": ""}, {"RENDER_EXTERNAL_HOSTNAME": "invalid.example.com"}, {"DJANGO_DEBUG": "1"}):
            with self.subTest(overrides=overrides), patch.dict(os.environ, self.environment(**overrides), clear=True), patch.object(sys, "argv", ["maritime.serve"]), patch("maritime.render.initialize_database") as initialize, patch("waitress.serve") as start:
                with self.assertRaises(ImproperlyConfigured):
                    docker_main()
                initialize.assert_not_called()
                start.assert_not_called()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BootstrapOperatorTests(TestCase):
    def bootstrap(self, **overrides):
        output = io.StringIO()
        env = {"BOOTSTRAP_ADMIN_USERNAME": "initial_operator", "BOOTSTRAP_ADMIN_EMAIL": "operator@example.test", "BOOTSTRAP_ADMIN_PASSWORD": "ShipsOranges!7639", **overrides}
        with patch.dict(os.environ, env, clear=True):
            call_command("bootstrap_operator", stdout=output)
        return output.getvalue()

    def test_operator_created_with_hashed_password_and_no_password_in_output(self):
        output = self.bootstrap()
        user = get_user_model().objects.get(username="initial_operator")
        self.assertTrue(user.is_staff and user.is_superuser and user.is_active)
        self.assertTrue(user.check_password("ShipsOranges!7639"))
        self.assertNotIn("ShipsOranges", output)

    def test_redeploy_does_not_reset_operator_password(self):
        self.bootstrap()
        user = get_user_model().objects.get(username="initial_operator")
        user.set_password("ChangedByOperator!6483")
        user.save()
        self.bootstrap()
        user.refresh_from_db()
        self.assertTrue(user.check_password("ChangedByOperator!6483"))
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_existing_customer_cannot_be_promoted_by_bootstrap(self):
        get_user_model().objects.create_user("INITIAL_OPERATOR", email="operator@example.test")
        with self.assertRaises(CommandError):
            self.bootstrap()
        user = get_user_model().objects.get(username="INITIAL_OPERATOR")
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_weak_or_missing_credentials_create_nothing(self):
        for changes in ({"BOOTSTRAP_ADMIN_PASSWORD": "123"}, {"BOOTSTRAP_ADMIN_EMAIL": ""}):
            with self.subTest(changes=changes), self.assertRaises(CommandError):
                self.bootstrap(**changes)
        self.assertEqual(get_user_model().objects.count(), 0)
        with patch.dict(os.environ, {}, clear=True):
            call_command("bootstrap_operator", stdout=io.StringIO())
        self.assertEqual(get_user_model().objects.count(), 0)


@override_settings(DEBUG=False, ALLOWED_HOSTS=["maritime-carbon.onrender.com"], CSRF_TRUSTED_ORIGINS=["https://maritime-carbon.onrender.com"], SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RenderHttpsTests(TestCase):
    def request(self, path, data=None, cookie=""):
        options = server_options({"RENDER": "true", "RENDER_EXTERNAL_HOSTNAME": "maritime-carbon.onrender.com"})
        adjustments = Adjustments(**options)
        headers = {"HTTP_HOST": "maritime-carbon.onrender.com", "REMOTE_ADDR": "10.0.0.12", "HTTP_X_FORWARDED_PROTO": "http", "HTTP_X_FORWARDED_FOR": "198.51.100.3", "HTTP_COOKIE": cookie, "HTTP_ORIGIN": "https://maritime-carbon.onrender.com"}
        factory = RequestFactory()
        request = factory.get(path, **headers) if data is None else factory.post(path, data, **headers)
        request.environ["wsgi.url_scheme"] = adjustments.url_scheme
        app = proxy_headers_middleware(get_wsgi_application(), trusted_proxy=adjustments.trusted_proxy, trusted_proxy_headers=adjustments.trusted_proxy_headers, clear_untrusted=True)
        captured = {"environ": request.environ}
        response = app(request.environ, lambda status, headers: captured.update(status=status, headers=headers))
        try:
            captured["body"] = b"".join(response)
        finally:
            response.close()
        return captured

    def test_https_health_does_not_redirect_and_untrusted_forwarded_headers_are_removed(self):
        captured = self.request("/health/")
        self.assertEqual(captured["body"], b"ok")
        self.assertEqual(captured["status"], "200 OK")
        self.assertNotIn("Location", dict(captured["headers"]))
        self.assertEqual(captured["environ"]["REMOTE_ADDR"], "10.0.0.12")
        self.assertNotIn("HTTP_X_FORWARDED_FOR", captured["environ"])
        self.assertNotIn("HTTP_X_FORWARDED_PROTO", captured["environ"])

    def test_invitation_registration_accepts_https_csrf_and_creates_secure_session(self):
        invitation = TrialInvitation.objects.create(email="secure@example.test", company_name="HTTPS trial")
        path = f"/accounts/register/{invitation.pk}/"
        page = self.request(path)
        cookies = SimpleCookie()
        for key, value in page["headers"]:
            if key.lower() == "set-cookie":
                cookies.load(value)
        csrf = cookies["csrftoken"].value
        self.assertTrue(cookies["csrftoken"]["secure"])
        result = self.request(path, {"first_name": "Tester", "username": "secure_trial", "password1": "OrangesShips!8742", "password2": "OrangesShips!8742", "csrfmiddlewaretoken": csrf}, cookie=f"csrftoken={csrf}")
        self.assertEqual(result["status"], "302 Found")
        session = SimpleCookie()
        for key, value in result["headers"]:
            if key.lower() == "set-cookie":
                session.load(value)
        self.assertTrue(session["sessionid"]["secure"])
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
