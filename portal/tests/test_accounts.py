"""Operators can use both environments, with a private calculator workspace."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.accounts import ensure_operator_workspace
from portal.models import AuditEvent, Company, Membership, Scenario


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

    def user_login(self, **overrides):
        return self.client.post(reverse("login"), {
            "username": self.operator.username, "password": "ExistingShipsPassword!7631", **overrides,
        })

    def test_operator_user_login_opens_calculator_with_a_private_workspace(self):
        other = Company.objects.create(name="Other customer's company", status="active", access_until=timezone.localdate() + timedelta(days=30))
        foreign = Scenario.objects.create(company=other, name="Other customer's case", inputs={}, created_by=self.customer)
        response = self.user_login()
        self.assertRedirects(response, reverse("dashboard"))
        member = Membership.objects.get(user=self.operator)
        self.assertNotEqual(member.company, other)
        self.assertEqual(member.role, "admin")
        self.assertTrue(member.company.has_access)
        self.assertEqual(member.company.max_vessels, 20)
        self.assertEqual(self.client.get(reverse("scenario_create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("team")).status_code, 200)
        self.assertEqual(self.client.get(reverse("scenario", args=[foreign.pk])).status_code, 404)
        account = self.client.get(reverse("account"))
        self.assertContains(account, "Open calculator")
        self.assertContains(account, "Open administration")
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.is_staff and self.operator.is_superuser)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_repeated_operator_logins_reuse_workspace_and_saved_cases(self):
        self.user_login()
        member = Membership.objects.get(user=self.operator)
        case = Scenario.objects.create(company=member.company, name="My saved case", inputs={}, created_by=self.operator)
        for _ in range(2):
            self.client.logout()
            self.user_login()
            self.assertEqual(Membership.objects.get(user=self.operator).company_id, member.company_id)
            self.assertContains(self.client.get(reverse("dashboard")), case.name)
        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="workspace.provisioned").count(), 1)

    def test_existing_membership_role_and_expiry_are_preserved(self):
        company = Company.objects.create(name="Assigned company", status="active", access_until=timezone.localdate() + timedelta(days=30))
        member = Membership.objects.create(user=self.operator, company=company, role="viewer")
        self.user_login()
        member.refresh_from_db()
        company.refresh_from_db()
        self.assertEqual(member.company_id, company.pk)
        self.assertEqual(member.role, "viewer")
        self.assertEqual(company.access_until, timezone.localdate() + timedelta(days=30))
        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("scenario_create")).status_code, 403)

    def test_normal_login_cannot_redirect_into_admin_console(self):
        for target in (reverse("admin:index"), "/admin", "http://testserver/admin/"):
            with self.subTest(target=target):
                self.client.logout()
                self.assertRedirects(self.user_login(next=target), reverse("dashboard"))

    def test_normal_login_preserves_a_requested_calculator_page(self):
        self.assertRedirects(self.user_login(next=reverse("scenario_create")), reverse("scenario_create"))

    def test_console_login_opens_console_without_creating_a_workspace(self):
        response = self.client.post(reverse("admin:login"), {
            "username": self.operator.username, "password": "ExistingShipsPassword!7631", "next": reverse("admin:index"),
        })
        self.assertRedirects(response, reverse("admin:index"))
        self.assertFalse(Membership.objects.filter(user=self.operator).exists())

    def test_ordinary_and_staff_only_users_cannot_self_provision(self):
        for staff, superuser in ((False, False), (True, False), (False, True)):
            with self.subTest(staff=staff, superuser=superuser):
                self.customer.is_staff, self.customer.is_superuser = staff, superuser
                self.customer.save()
                self.client.logout()
                self.client.post(reverse("login"), {"username": self.customer.username, "password": "ExistingShipsPassword!7631"})
                self.assertFalse(Membership.objects.filter(user=self.customer).exists())
                self.assertFalse(Company.objects.exists())

    def test_provisioning_rechecks_current_operator_privileges(self):
        get_user_model().objects.filter(pk=self.operator.pk).update(is_superuser=False)
        self.assertIsNone(ensure_operator_workspace(self.operator))
        self.assertFalse(Company.objects.exists())
