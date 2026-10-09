"""Registration from operator-created invitations; no public account creation."""
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserCreationForm
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .engine.schema import ScenarioInput, Vessel
from .models import AuditEvent, Company, Membership, Scenario, TrialInvitation


class TrialRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label="Your name")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("first_name", "username")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
        self.fields["username"].help_text = "Choose the username you will use to sign in."
        self.fields["password1"].help_text = "At least 12 characters. Choose a unique password."

    def clean_username(self):
        username = self.cleaned_data["username"]
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is unavailable.")
        return username


def unavailable(request):
    return render(request, "registration/trial.html", {"unavailable": True}, status=410)


@require_http_methods(["GET", "POST"])
def register_trial(request, token):
    invitation = get_object_or_404(TrialInvitation, pk=token)
    if not invitation.available:
        return unavailable(request)
    if request.user.is_authenticated:
        return render(request, "registration/trial.html", {"already_signed_in": True}, status=403)
    form = TrialRegistrationForm(request.POST if request.method == "POST" else None)
    # The invitation determines email, company, privileges and limits. Submitted
    # tenant IDs, email overrides or staff flags cannot change those values.
    form.instance.email = invitation.email
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                invitation = TrialInvitation.objects.select_for_update().get(pk=token)
                if not invitation.available:
                    return unavailable(request)
                user = form.save(commit=False)
                user.email = invitation.email
                user.is_staff = user.is_superuser = False
                user.save()
                company = Company.objects.create(
                    name=invitation.company_name, status="trial",
                    access_until=timezone.localdate() + timedelta(days=invitation.trial_days - 1),
                    max_users=invitation.max_users, max_vessels=invitation.max_vessels,
                )
                Membership.objects.create(user=user, company=company, role="admin")
                year = min(2050, max(2025, timezone.localdate().year))
                data = ScenarioInput(
                    start_year=year, end_year=min(2050, year + 4), scope_confirmed=True,
                    scope_notes="Fictional example only. Replace the consumption, prices and EU scope with reviewed inputs before using a result.",
                    vessels=[Vessel(name="Example vessel · fictional", fuel="MGO", sea_t=1000, berth_t=30, max_blend=0)],
                )
                data.validate(for_run=False)
                Scenario.objects.create(company=company, name="Example fleet · fictional inputs", inputs=data.to_dict(), created_by=user)
                invitation.accepted_at = timezone.now()
                invitation.accepted_by = user
                invitation.company = company
                invitation.save(update_fields=["accepted_at", "accepted_by", "company"])
                AuditEvent.objects.create(company=company, actor=user, action="trial.registered", detail="Free trial created from a service-operator invitation.")
        except IntegrityError:
            form.add_error("username", "This username is unavailable. Please choose another.")
        else:
            login(request, user)
            messages.success(request, "Your free trial is ready. The example fleet uses fictional inputs; you can edit it or create your own case.")
            return redirect("dashboard")
    return render(request, "registration/trial.html", {"form": form, "invitation": invitation})
