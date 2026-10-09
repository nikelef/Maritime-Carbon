"""Create the initial operator from temporary hosting secrets, without a shell."""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction


class Command(BaseCommand):
    help = "Create the initial operator from BOOTSTRAP_ADMIN_* environment variables. Never resets an existing account."

    def handle(self, **options):
        username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        if not any((username, email, password)):
            return
        if not all((username, email, password)):
            raise CommandError("Set all three BOOTSTRAP_ADMIN_* variables, or remove all three after initial setup.")
        user_model = get_user_model()
        with transaction.atomic():
            existing = user_model.objects.filter(username__iexact=username).first()
            if existing:
                if not (existing.is_active and existing.is_staff and existing.is_superuser
                        and existing.email.casefold() == email.casefold()):
                    raise CommandError("Bootstrap username belongs to an existing account. Choose a different operator username.")
                self.stdout.write("Operator already exists; credentials unchanged.")
                return
            user = user_model(username=username, email=email, is_staff=True, is_superuser=True)
            try:
                validate_email(email)
                validate_password(password, user)
                user.set_password(password)
                user.full_clean()
            except ValidationError as exc:
                raise CommandError("; ".join(exc.messages)) from exc
            user.save()
        self.stdout.write(self.style.SUCCESS("Initial operator created. Remove BOOTSTRAP_ADMIN_* variables from the host."))
