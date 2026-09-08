"""Create a company workspace without placing passwords in argv or logs."""
from datetime import timedelta
from getpass import getpass
import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from portal.models import Company, Membership, AuditEvent


class Command(BaseCommand):
    help = "Create a company and its first administrator. Prompts securely for the password."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--status", choices=["trial", "active"], default="trial")
        parser.add_argument("--seats", type=int, default=5)
        parser.add_argument("--vessels", type=int, default=20)
        parser.add_argument("--password-env", help="Optional environment variable containing the initial password, for automated provisioning.")

    def handle(self, **options):
        if not 1 <= options["days"] <= 3660 or not 1 <= options["seats"] <= 500 or not 1 <= options["vessels"] <= 20:
            raise CommandError("Use 1–3660 days, 1–500 seats and 1–20 vessels.")
        if not options["company"].strip() or len(options["company"]) > 160:
            raise CommandError("Enter a company name of 1–160 characters.")
        if Company.objects.filter(name__iexact=options["company"].strip()).exists():
            raise CommandError("Company already exists. Add its users through Company & team or the operator console.")
        if get_user_model().objects.filter(username__iexact=options["username"]).exists():
            raise CommandError("Username already exists.")
        user = get_user_model()(username=options["username"], email=options["email"])
        password = os.environ.get(options["password_env"], "") if options["password_env"] else getpass("Initial password: ")
        if not options["password_env"] and password != getpass("Confirm password: "):
            raise CommandError("Passwords did not match.")
        try:
            validate_email(user.email)
            validate_password(password, user)
            user.set_password(password)
            user.full_clean()
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        with transaction.atomic():
            company = Company.objects.create(name=options["company"].strip(), access_until=timezone.localdate() + timedelta(days=options["days"]), status=options["status"], max_users=options["seats"], max_vessels=options["vessels"])
            user.save()
            Membership.objects.create(user=user, company=company, role="admin")
            AuditEvent.objects.create(company=company, actor=user, action="company.provisioned", detail="Initial account created by service operator.")
        self.stdout.write(self.style.SUCCESS(f"Created {company.name}. Username: {user.username}. Access until {company.access_until}."))
