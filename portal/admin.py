from django.contrib import admin
from .models import Company, Membership, Scenario, AnalysisRun, AuditEvent


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
