"""Account navigation is private and never requires a password change."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = get_user_model().objects.create_superuser(
            "operator@example.test", email="operator@example.test", password="ExistingShipsPassword!7631",
        )
        cls.customer = get_user_model().objects.create_user(
            "customer", email="customer@example.test", password="ExistingShipsPassword!7631",
        )

    def test_account_requires_login(self):
        self.assertRedirects(self.client.get(reverse("account")), reverse("login") + "?next=/accounts/")

    def test_operator_without_company_can_open_account_repeatedly_without_changing_password(self):
        password_hash = self.operator.password
        self.client.force_login(self.operator)
        for _ in range(3):
            response = self.client.get(reverse("account"))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "registration/account.html")
            self.assertContains(response, self.operator.username)
            self.assertNotContains(response, 'name="old_password"')
            self.assertNotContains(response, 'name="new_password1"')
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.password, password_hash)
        self.assertContains(response, 'href="' + reverse("password_change") + '"')
        self.assertEqual(self.client.get(reverse("password_change")).status_code, 200)

    def test_customer_sees_only_their_account_and_no_operator_link(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("account"))
        self.assertContains(response, self.customer.email)
        self.assertNotContains(response, self.operator.email)
        self.assertNotContains(response, "Open administration")
        self.assertNotContains(response, 'href="' + reverse("admin:index") + '"')

    def test_operator_console_has_a_normal_account_link(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<a href="' + reverse("account") + '">Account</a>')
