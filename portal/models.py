import uuid
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


def invitation_expiry():
    return timezone.now() + timedelta(days=7)


class Company(models.Model):
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=12, choices=[("trial", "Trial"), ("active", "Active"), ("suspended", "Suspended")], default="trial")
    access_until = models.DateField(help_text="Inclusive expiry date; invoices/payment confirmation are managed by the operator.")
    max_users = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(500)])
    max_vessels = models.PositiveIntegerField(default=20, validators=[MinValueValidator(1), MaxValueValidator(20)])
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def has_access(self):
        return self.status in ("trial", "active") and self.access_until >= timezone.localdate()

    def __str__(self):
        return self.name


class Membership(models.Model):
    ROLES = [("admin", "Company administrator"), ("analyst", "Analyst"), ("viewer", "Read-only viewer")]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=12, choices=ROLES, default="analyst")


class TrialInvitation(models.Model):
    """A private, single-use registration link created by the service operator."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    company_name = models.CharField(max_length=160)
    trial_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(90)])
    max_users = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    max_vessels = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(20)])
    expires_at = models.DateTimeField(default=invitation_expiry)
    revoked = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="accepted_trial_invitations", editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_trial_invitations", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def available(self):
        return not self.revoked and self.accepted_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f"{self.company_name} · {self.email}"


class Scenario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    name = models.CharField(max_length=140)
    inputs = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["company", "-updated_at"])]


class AnalysisRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name="runs")
    scenario_name = models.CharField(max_length=140)
    scenario_revision = models.PositiveIntegerField()
    inputs = models.JSONField()
    results = models.JSONField()
    input_digest = models.CharField(max_length=64)
    engine_version = models.CharField(max_length=40)
    ruleset_version = models.CharField(max_length=40)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "-created_at"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Calculation snapshots cannot be edited. Create a new run.")
        if self.scenario.company_id != self.company_id:
            raise ValidationError("Scenario and run must belong to the same company.")
        super().save(*args, **kwargs)


class AuditEvent(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    object_id = models.CharField(max_length=60, blank=True)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LoginBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
