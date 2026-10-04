from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from portal import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/login/", auth.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth.LogoutView.as_view(), name="logout"),
    path("accounts/password/", auth.PasswordChangeView.as_view(template_name="registration/password_change.html", success_url="/accounts/password/done/"), name="password_change"),
    path("accounts/password/done/", auth.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
    path("admin/", admin.site.urls),
    path("cases/new/", views.scenario_create, name="scenario_create"),
    path("fleet-template.xlsx", views.vessel_template, name="vessel_template"),
    path("fleet-template.csv", views.vessel_template, name="vessel_template_csv"),
    path("cases/<uuid:pk>/", views.scenario_detail, name="scenario"),
    path("cases/<uuid:pk>/edit/", views.scenario_edit, name="scenario_edit"),
    path("cases/<uuid:pk>/delete/", views.scenario_delete, name="scenario_delete"),
    path("cases/<uuid:pk>/duplicate/", views.scenario_duplicate, name="scenario_duplicate"),
    path("cases/<uuid:pk>/vessels/add/", views.vessel_edit, name="vessel_add"),
    path("cases/<uuid:pk>/vessels/import/", views.vessel_import, name="vessel_import"),
    path("cases/<uuid:pk>/vessels/<int:index>/", views.vessel_edit, name="vessel_edit"),
    path("cases/<uuid:pk>/vessels/<int:index>/remove/", views.vessel_remove, name="vessel_remove"),
    path("cases/<uuid:pk>/fuels/extend/", views.fuel_library_extend, name="fuel_library_extend"),
    path("cases/<uuid:pk>/fuels/restore-defaults/", views.fossil_defaults_restore, name="fossil_defaults_restore"),
    path("cases/<uuid:pk>/fuels/<str:code>/", views.fuel_edit, name="fuel_edit"),
    path("cases/<uuid:pk>/run/", views.run_analysis, name="run_analysis"),
    path("reports/", views.reports, name="reports"),
    path("reports/<uuid:pk>/", views.report, name="report"),
    path("reports/<uuid:pk>/delete/", views.report_delete, name="report_delete"),
    path("reports/<uuid:pk>/export/<str:kind>/", views.export_run, name="export_run"),
    path("team/", views.team, name="team"),
    path("team/<int:pk>/deactivate/", views.deactivate_member, name="deactivate_member"),
    path("methodology/", views.methodology, name="methodology"),
    path("demo/", views.demo, name="demo"),
    path("health/", views.health, name="health"),
]
