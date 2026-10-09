from django.contrib import admin
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html
from .models import Company, Membership, Scenario, AnalysisRun, AuditEvent, TrialInvitation


@admin.register(TrialInvitation)
class TrialInvitationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "email", "expires_at", "accepted_at", "revoked")
    list_filter = ("revoked",)
    search_fields = ("company_name", "email")
    readonly_fields = ("registration_link", "accepted_at", "accepted_by", "company", "created_by", "created_at")

    @admin.display(description="Registration link (copy link address)")
    def registration_link(self, obj):
        if not obj or not obj.pk or obj._state.adding:
            return "Save this invitation to get its registration link."
        if not obj.available:
            return "This invitation is no longer available."
        return format_html('<a href="{}">Copy this invitation link address to send to the recipient</a>', reverse("register_trial", args=[obj.pk]))

    def save_model(self, request, obj, form, change):
        if change:
            # An operator may edit a form opened before its recipient registers.
            # Never write stale acceptance fields back over a redeemed link.
            with transaction.atomic():
                current = TrialInvitation.objects.select_for_update().get(pk=obj.pk)
                fields = ("revoked",) if current.accepted_at else (
                    "email", "company_name", "trial_days", "max_users", "max_vessels", "expires_at", "revoked",
                )
                obj.save(update_fields=fields)
                obj.refresh_from_db()
            return
        obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.accepted_at:
            return self.readonly_fields + ("email", "company_name", "trial_days", "max_users", "max_vessels", "expires_at")
        return self.readonly_fields


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "access_until", "max_users", "max_vessels")
    search_fields = ("name",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role")
    list_filter = ("role", "company")
    autocomplete_fields = ("user", "company")


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Scenario)
class ScenarioAdmin(ReadOnlyAdmin):
    list_display = ("name", "company", "revision", "updated_at")


@admin.register(AnalysisRun)
class RunAdmin(ReadOnlyAdmin):
    list_display = ("scenario_name", "company", "engine_version", "created_at")


@admin.register(AuditEvent)
class AuditAdmin(ReadOnlyAdmin):
    list_display = ("company", "actor", "action", "created_at")

admin.site.site_header = "Maritime Carbon · Operator console"
admin.site.site_title = "Maritime Carbon administration"
