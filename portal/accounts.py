"""Normal app login and private calculator workspaces for service operators."""
from datetime import date
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.urls import reverse

from .models import AuditEvent, Company, Membership


def ensure_operator_workspace(user):
    """Give an active platform operator their own workspace, preserving any existing membership."""
    if not (user.is_active and user.is_staff and user.is_superuser):
        return None
    with transaction.atomic():
        # Serialize first logins and recheck privileges from the current row.
        operator = get_user_model().objects.select_for_update().get(pk=user.pk)
        if not (operator.is_active and operator.is_staff and operator.is_superuser):
            return None
        member = Membership.objects.select_related("company").filter(user=operator).first()
        if member:
            return member
        company = Company.objects.create(
            name=("My workspace · " + operator.get_username())[:160],
            status="active", access_until=date(2099, 12, 31),
            max_users=5, max_vessels=20,
        )
        member = Membership.objects.create(user=operator, company=company, role="admin")
        AuditEvent.objects.create(
            company=company, actor=operator, action="workspace.provisioned",
            detail="Private calculator workspace created for the service administrator.",
        )
        return member


class WorkspaceLoginView(LoginView):
    """The user login opens the calculator, while /admin/ keeps its own login."""
    template_name = "registration/login.html"

    def form_valid(self, form):
        ensure_operator_workspace(form.get_user())
        return super().form_valid(form)

    def get_success_url(self):
        target = self.get_redirect_url()
        if target:
            path = urlsplit(target).path
            admin_root = reverse("admin:index")
            if path != admin_root.rstrip("/") and not path.startswith(admin_root):
                return target
        return self.get_default_redirect_url()
