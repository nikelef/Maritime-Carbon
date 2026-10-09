"""Invitation registration, private workspaces and single-use access controls."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.schema import ScenarioInput
from portal.models import AuditEvent, Company, Membership, Scenario, TrialInvitation


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TrialRegistrationTests(TestCase):
    def setUp(self):
        self.invitation = TrialInvitation.objects.create(email="tester@example.test", company_name="Invited company", trial_days=14, max_vessels=2)
        self.url = reverse("register_trial", args=[self.invitation.pk])
        self.data = {"first_name": "Test person", "username": "trial_tester", "password1": "OrangesShips!8742", "password2": "OrangesShips!8742"}

    def test_registration_creates_isolated_trial_and_ready_example_without_privileged_access(self):
        response = self.client.post(self.url, self.data | {"email": "attacker@example.test", "is_staff": "1", "is_superuser": "1", "company_id": "999", "max_vessels": "20"})
        self.assertRedirects(response, reverse("dashboard"))
        user = get_user_model().objects.get(username="trial_tester")
        self.assertTrue(user.check_password(self.data["password1"]))
        self.assertEqual(user.email, self.invitation.email)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.membership.role, "admin")
        company = user.membership.company
        self.assertEqual(company.name, "Invited company")
        self.assertEqual(company.status, "trial")
        self.assertEqual(company.max_users, 1)
        self.assertEqual(company.max_vessels, 2)
        self.assertEqual(company.access_until, timezone.localdate() + timedelta(days=13))
        case = Scenario.objects.get(company=company)
        ScenarioInput.from_dict(case.inputs).validate()
        self.assertIn("Fictional", case.inputs["scope_notes"])
        self.assertTrue(AuditEvent.objects.filter(company=company, action="trial.registered").exists())
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.accepted_by, user)
        self.assertEqual(self.invitation.company, company)
        self.assertFalse(self.invitation.available)

    def test_get_displays_registration_but_does_not_redeem_invitation(self):
        self.assertContains(self.client.get(self.url), "No payment details are needed")
        self.assertEqual(Company.objects.count(), 0)
        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.available)

    def test_used_invitation_cannot_create_a_second_company(self):
        self.client.post(self.url, self.data)
        self.client.logout()
        before = Company.objects.count()
        self.assertEqual(self.client.post(self.url, self.data | {"username": "second_user"}).status_code, 410)
        self.assertEqual(Company.objects.count(), before)
        self.assertFalse(get_user_model().objects.filter(username="second_user").exists())

    def test_expired_and_revoked_invitations_do_not_disclose_recipient_or_create_accounts(self):
        for changes in ({"expires_at": timezone.now() - timedelta(seconds=1)}, {"expires_at": timezone.now() + timedelta(days=1), "revoked": True}):
            TrialInvitation.objects.filter(pk=self.invitation.pk).update(**changes)
            for method in (self.client.get, self.client.post):
                response = method(self.url, self.data) if method == self.client.post else method(self.url)
                self.assertEqual(response.status_code, 410)
                self.assertNotContains(response, self.invitation.email, status_code=410)
        self.assertEqual(Company.objects.count(), 0)

    def test_password_validation_and_case_insensitive_username_collision_leave_link_usable(self):
        weak = self.data | {"password1": "123", "password2": "123"}
        self.assertContains(self.client.post(self.url, weak), "at least 12 characters")
        get_user_model().objects.create_user("TRIAL_TESTER")
        self.assertContains(self.client.post(self.url, self.data), "This username is unavailable")
        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.available)
        self.assertEqual(Company.objects.count(), 0)

    def test_csrf_and_authenticated_account_cannot_redeem_invitation(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, self.data).status_code, 403)
        existing = get_user_model().objects.create_user("existing")
        self.client.force_login(existing)
        self.assertContains(self.client.get(self.url), "Sign out to register", status_code=403)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.available)

    def test_invitation_is_rechecked_under_lock_before_user_creation(self):
        original = TrialInvitation.available.fget
        readings = iter([True, False])
        with patch.object(TrialInvitation, "available", new=property(lambda obj: next(readings))):
            self.assertEqual(self.client.post(self.url, self.data).status_code, 410)
        self.assertEqual(Company.objects.count(), 0)
        self.assertFalse(get_user_model().objects.filter(username="trial_tester").exists())
        self.assertTrue(original(TrialInvitation.objects.get(pk=self.invitation.pk)))

    def test_failed_database_write_rolls_back_user_workspace_and_link_redemption(self):
        with patch("portal.trials.Scenario.objects.create", side_effect=IntegrityError("race")):
            self.assertEqual(self.client.post(self.url, self.data).status_code, 200)
        self.assertEqual(Company.objects.count(), 0)
        self.assertEqual(Membership.objects.count(), 0)
        self.assertFalse(get_user_model().objects.filter(username="trial_tester").exists())
        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.available)

    def test_deleted_invitation_during_registration_creates_nothing(self):
        with patch("portal.trials.TrialInvitation.objects.select_for_update") as locked:
            locked.return_value.filter.return_value.first.return_value = None
            self.assertEqual(self.client.post(self.url, self.data).status_code, 410)
        self.assertEqual(Company.objects.count(), 0)
        self.assertFalse(get_user_model().objects.filter(username="trial_tester").exists())

    def test_stale_operator_edit_cannot_reset_a_redeemed_invitation(self):
        stale = TrialInvitation.objects.get(pk=self.invitation.pk)
        self.client.post(self.url, self.data)
        operator = get_user_model().objects.create_superuser("operator", "operator@example.test", "LongOperator!6384")
        stale.company_name = "Stale edit"
        stale.revoked = True
        admin.site._registry[TrialInvitation].save_model(SimpleNamespace(user=operator), stale, None, change=True)
        stale.refresh_from_db()
        self.assertIsNotNone(stale.accepted_at)
        self.assertEqual(stale.accepted_by.username, "trial_tester")
        self.assertEqual(stale.company_name, "Invited company")
        self.assertEqual(stale.company, get_user_model().objects.get(username="trial_tester").membership.company)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, self.data | {"username": "second_user"}).status_code, 410)
        self.assertEqual(Company.objects.count(), 1)

    def test_other_workspace_and_expired_trial_remain_inaccessible(self):
        other = Company.objects.create(name="Other company", access_until=timezone.localdate() + timedelta(days=3))
        owner = get_user_model().objects.create_user("owner")
        case = Scenario.objects.create(company=other, created_by=owner, name="Private case", inputs={})
        self.client.post(self.url, self.data)
        self.assertEqual(self.client.get(reverse("scenario", args=[case.pk])).status_code, 404)
        trial = get_user_model().objects.get(username="trial_tester").membership.company
        trial.access_until = timezone.localdate() - timedelta(days=1)
        trial.save()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_only_operator_can_create_invitations(self):
        self.client.post(self.url, self.data)
        url = reverse("admin:portal_trialinvitation_add")
        self.assertEqual(self.client.get(url).status_code, 302)
        operator = get_user_model().objects.create_superuser("operator", "operator@example.test", "LongOperator!6384")
        self.client.force_login(operator)
        response = self.client.post(url, {"email": "new@example.test", "company_name": "New company", "trial_days": 30, "max_users": 1, "max_vessels": 3, "expires_at_0": "2050-01-01", "expires_at_1": "12:00:00", "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        invitation = TrialInvitation.objects.get(email="new@example.test")
        self.assertEqual(invitation.created_by, operator)
        self.assertContains(self.client.get(reverse("admin:portal_trialinvitation_change", args=[invitation.pk])), reverse("register_trial", args=[invitation.pk]))
