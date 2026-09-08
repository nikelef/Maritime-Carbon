import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


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
