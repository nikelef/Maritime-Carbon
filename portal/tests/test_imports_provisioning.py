import csv
from datetime import timedelta
import io
import os
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from portal.models import Company, Membership, Scenario
from portal.engine.schema import ScenarioInput
from portal.imports import COLUMNS, parse_vessels


def csv_upload(rows):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return SimpleUploadedFile("fleet.csv", stream.getvalue().encode("utf-8"), "text/csv")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ImportAndProvisionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Importer", status="active", access_until=timezone.localdate() + timedelta(days=3))
        self.user = get_user_model().objects.create_user("importer", password="long-test-password")
        Membership.objects.create(user=self.user, company=self.company, role="analyst")
        self.scenario = Scenario.objects.create(company=self.company, name="CSV case", inputs=ScenarioInput().to_dict(), created_by=self.user)
        self.client.force_login(self.user)

    def test_csv_import_saves_validated_rows_and_requires_technical_review(self):
        response = self.client.post(reverse("vessel_import", args=[self.scenario.pk]), {"revision": 1, "csv_file": csv_upload([["Imported vessel", "", "tanker", 30000, "VLSFO", 2000, 120, 40, 50, "HVO", 30]])})
        self.assertEqual(response.status_code, 302)
        self.scenario.refresh_from_db()
        vessel = self.scenario.inputs["vessels"][0]
        self.assertEqual(vessel["intra_share"], .4)
        self.assertFalse(vessel["compatible"])
        self.assertFalse(vessel["ops_ready"])

    def test_invalid_row_rolls_back_entire_import(self):
        response = self.client.post(reverse("vessel_import", args=[self.scenario.pk]), {"revision": 1, "csv_file": csv_upload([["Good", "", "cargo", 30000, "VLSFO", 2000, 120, 40, 50, "HVO", 30], ["Bad", "", "cargo", 30000, "VLSFO", "nan", 120, 40, 50, "HVO", 30]])})
        self.assertContains(response, "finite number")
        self.scenario.refresh_from_db()
        self.assertEqual(self.scenario.inputs["vessels"], [])
        self.assertEqual(self.scenario.revision, 1)

    def test_template_and_headers_cannot_introduce_tenant_fields(self):
        self.assertEqual(self.client.get(reverse("vessel_template")).status_code, 200)
        with self.assertRaises(ValueError):
            parse_vessels(SimpleUploadedFile("evil.csv", b"name,company_id\nship,99"))
        with self.assertRaises(ValueError):
            parse_vessels(SimpleUploadedFile("big.csv", b"x" * 65537))

    def test_provision_command_sets_password_hash_and_company_entitlement(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"TEST_INITIAL_PASSWORD": "complex-passphrase-test-894!"}):
            call_command("provision_company", company="New subscriber", username="subscriber_admin", email="admin@example.test", status="active", days=365, password_env="TEST_INITIAL_PASSWORD", stdout=output)
        user = get_user_model().objects.get(username="subscriber_admin")
        self.assertTrue(user.check_password("complex-passphrase-test-894!"))
        self.assertNotEqual(user.password, "complex-passphrase-test-894!")
        self.assertEqual(user.membership.role, "admin")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.membership.company.has_access)
        self.assertNotIn("complex-passphrase", output.getvalue())

    def test_weak_password_cannot_provision_company(self):
        with patch.dict(os.environ, {"TEST_INITIAL_PASSWORD": "123"}), self.assertRaises(CommandError):
            call_command("provision_company", company="Rejected", username="rejected", email="x@example.test", password_env="TEST_INITIAL_PASSWORD")
        self.assertFalse(Company.objects.filter(name="Rejected").exists())
