import csv
import hashlib
import json
from dataclasses import asdict
from functools import wraps
from types import SimpleNamespace
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .engine.schema import ScenarioInput, Vessel, default_fuels
from .engine.calculator import compare, fuel_choice_notices, strategy_actions
from .engine.rules import ENGINE_VERSION, RULESET_VERSION, CHECKED_ON, SOURCES, REDUCTIONS, REFERENCE_G
from .forms import ScenarioForm, VesselForm, FuelForm, MemberForm, VesselImportForm
from .imports import COLUMNS, parse_vessels
from .models import Company, Membership, Scenario, AnalysisRun, AuditEvent


def workspace_required(edit=False, admin=False):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            member = Membership.objects.select_related("company").filter(user=request.user).first()
            if not member:
                return render(request, "portal/access.html", {"reason": "Your account has not been assigned to a company. Contact your service administrator."}, status=403)
            if not member.company.has_access:
                return render(request, "portal/access.html", {"reason": "Your company's access is inactive or has expired. Contact your service administrator to renew access."}, status=403)
            if (edit and member.role not in ("admin", "analyst")) or (admin and member.role != "admin"):
                return HttpResponseForbidden("Your role does not permit this action.")
            request.member = member
            request.company = member.company
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def audit(request, action, obj="", detail=""):
    AuditEvent.objects.create(company=request.company, actor=request.user, action=action, object_id=str(obj), detail=detail[:300])


def scenario_for(request, pk):
    return get_object_or_404(Scenario, pk=pk, company=request.company)


def save_inputs(request, scenario, data, revision, name=None):
    data.validate(for_run=False)
    if len(data.vessels) > min(20, request.company.max_vessels):
        raise ValueError("This case exceeds your company vessel limit.")
    with transaction.atomic():
        locked = Scenario.objects.select_for_update().get(pk=scenario.pk, company=request.company)
        if revision != locked.revision:
            raise ValueError("This case changed in another session. Reload it before saving; your changes were not applied.")
        locked.inputs = data.to_dict()
        locked.revision += 1
        if name is not None:
            locked.name = name
        locked.save()
        audit(request, "scenario.updated", locked.pk, f"Revision {locked.revision}")


@workspace_required()
def dashboard(request):
    scenarios = Scenario.objects.filter(company=request.company)
    runs = AnalysisRun.objects.filter(company=request.company)
    return render(request, "portal/dashboard.html", {"scenarios": scenarios[:30], "scenario_count": scenarios.count(), "run_count": runs.count(), "recent_runs": runs[:6], "active_nav": "overview"})


@workspace_required(edit=True)
def scenario_create(request):
    data = ScenarioInput()
    form = ScenarioForm(request.POST or None, initial=ScenarioForm.initial_for("Fleet compliance plan", data))
    if request.method == "POST" and form.is_valid():
        try:
            form.apply(data)
            with transaction.atomic():
                obj = Scenario.objects.create(company=request.company, name=form.cleaned_data["name"], inputs=data.to_dict(), created_by=request.user)
                audit(request, "scenario.created", obj.pk)
            messages.success(request, "Decision case created. Add your vessels next.")
            return redirect("scenario", pk=obj.pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "portal/scenario_form.html", {"form": form, "creating": True, "active_nav": "scenarios"})


@workspace_required()
def scenario_detail(request, pk):
    scenario = scenario_for(request, pk)
    data = ScenarioInput.from_dict(scenario.inputs)
    ready_errors = []
    try:
        data.validate()
    except ValueError as exc:
        ready_errors.append(str(exc))
    missing_fuels = [f.code for f in default_fuels() if f.code not in {f.code for f in data.fuels}]
    return render(request, "portal/scenario.html", {"scenario": scenario, "data": data, "missing_fuels": missing_fuels, "latest_run": scenario.runs.first(), "runs": scenario.runs.all()[:8], "ready_errors": ready_errors, "active_nav": "scenarios", "fuel_choice_notices": fuel_choice_notices(data)})


@workspace_required(edit=True)
def scenario_edit(request, pk):
    scenario = scenario_for(request, pk)
    data = ScenarioInput.from_dict(scenario.inputs)
    form = ScenarioForm(request.POST or None, initial=ScenarioForm.initial_for(scenario.name, data, scenario.revision))
    if request.method == "POST" and form.is_valid():
        try:
            save_inputs(request, scenario, form.apply(data), form.cleaned_data["revision"], form.cleaned_data["name"])
            messages.success(request, "Assumptions saved. Existing reports keep their original inputs.")
            return redirect("scenario", pk=pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "portal/scenario_form.html", {"form": form, "scenario": scenario, "active_nav": "scenarios"})


@workspace_required(edit=True)
def vessel_edit(request, pk, index=None):
    scenario = scenario_for(request, pk)
    data = ScenarioInput.from_dict(scenario.inputs)
    if index is not None and not 0 <= index < len(data.vessels):
        raise Http404
    vessel = data.vessels[index] if index is not None else Vessel()
    post_data = request.POST or None
    adding_fuel = request.method == "POST" and request.POST.get("add_sea_fuel") == "1"
    add_error = None
    if adding_fuel:
        post_data = request.POST.copy()
        row_prefix = "consumption" if "consumption-TOTAL_FORMS" in post_data else "sea_fuels"
        row_limit, absolute_limit = (100, 200) if row_prefix == "consumption" else (20, 40)
        try:
            total = int(post_data[f"{row_prefix}-TOTAL_FORMS"])
            initial = int(post_data[f"{row_prefix}-INITIAL_FORMS"])
            if not 0 <= initial <= total <= absolute_limit:
                raise ValueError
            active = sum(not post_data.get(f"{row_prefix}-{i}-DELETE") for i in range(total))
            if active >= row_limit or total >= absolute_limit:
                add_error = f"Use at most {row_limit} consumption rows. Save your changes before adding more rows."
            else:
                post_data[f"{row_prefix}-TOTAL_FORMS"] = str(total + 1)
        except (KeyError, TypeError, ValueError):
            add_error = "The fuel rows could not be read. Reload the vessel before adding a fuel."
    form = VesselForm(post_data, fuels=data.fuels, initial=VesselForm.initial_for(vessel, scenario.revision))
    if adding_fuel:
        # Adding a row only re-renders the user's draft, without saving or asking
        # them to complete unrelated required fields first.
        form.errors.clear()
        form.input_formset.non_form_errors().clear()
        for fuel_form in form.input_formset:
            fuel_form.errors.clear()
        if add_error:
            form.add_error(None, add_error)
    if request.method == "POST" and not adding_fuel and form.is_valid():
        try:
            candidate = form.vessel()
            if index is None:
                data.vessels.append(candidate)
            else:
                data.vessels[index] = candidate
            save_inputs(request, scenario, data, form.cleaned_data["revision"])
            messages.success(request, "Vessel saved.")
            return redirect("scenario", pk=pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "portal/vessel_form.html" if form._use_table else "portal/vessel_form_legacy.html", {"form": form, "scenario": scenario, "is_new": index is None, "active_nav": "scenarios"})


@workspace_required(edit=True)
def vessel_import(request, pk):
    scenario = scenario_for(request, pk)
    form = VesselImportForm(request.POST or None, request.FILES or None, initial={"revision": scenario.revision})
    if request.method == "POST" and form.is_valid():
        try:
            vessels = parse_vessels(form.cleaned_data["csv_file"])
            data = ScenarioInput.from_dict(scenario.inputs)
            data.vessels.extend(vessels)
            save_inputs(request, scenario, data, form.cleaned_data["revision"])
            messages.success(request, f"Imported {len(vessels)} vessels. Review fuel compatibility and any ship-specific FuelEU history before comparing.")
            return redirect("scenario", pk=pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "portal/vessel_import.html", {"scenario": scenario, "form": form, "active_nav": "scenarios"})


@workspace_required()
def vessel_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="fleet-input-template.csv"'
    writer = csv.writer(response)
    writer.writerow(COLUMNS)
    writer.writerow(["Example vessel", "", "cargo", 25000, "VLSFO", 4000, 150, 30, 60, "HVO", 30])
    return response


@require_POST
@workspace_required(edit=True)
def vessel_remove(request, pk, index):
    scenario = scenario_for(request, pk)
    data = ScenarioInput.from_dict(scenario.inputs)
    if not 0 <= index < len(data.vessels):
        raise Http404
    try:
        revision = int(request.POST.get("revision", ""))
        data.vessels.pop(index)
        save_inputs(request, scenario, data, revision)
        messages.success(request, "Vessel removed from this case. Previous calculation snapshots retain it.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("scenario", pk=pk)


@workspace_required(edit=True)
def fuel_edit(request, pk, code):
    scenario = scenario_for(request, pk)
    data = ScenarioInput.from_dict(scenario.inputs)
    fuel = next((f for f in data.fuels if f.code == code), None)
    if fuel is None:
        raise Http404
    form = FuelForm(request.POST or None, fuel=fuel, initial=asdict(fuel) | {"revision": scenario.revision, "ets_eligible": fuel.ets_zero_rated})
    if request.method == "POST" and form.is_valid():
        try:
            for key, value in form.cleaned_data.items():
                if key != "revision":
                    setattr(fuel, key, value)
            save_inputs(request, scenario, data, form.cleaned_data["revision"])
            messages.success(request, "Fuel assumptions saved for this case.")
            return redirect("scenario", pk=pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "portal/fuel_form.html", {"form": form, "scenario": scenario, "fuel": fuel, "active_nav": "scenarios"})


@require_POST
@workspace_required(edit=True)
def fuel_library_extend(request, pk):
    """Explicitly extend an old case; never silently reinterpret a saved report."""
    scenario = scenario_for(request, pk)
    data = ScenarioInput.from_dict(scenario.inputs)
    existing = {f.code for f in data.fuels}
    additions = [f for f in default_fuels() if f.code not in existing]
    try:
        revision = int(request.POST.get("revision", ""))
        if not additions:
            messages.info(request, "This case already includes the current fuel library.")
        else:
            data.fuels.extend(additions)
            save_inputs(request, scenario, data, revision)
            messages.success(request, "New fuel pathways added. Existing assumptions and saved reports are unchanged. Review evidence and vessel settings before use.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("scenario", pk=pk)


@require_POST
@workspace_required(edit=True)
def scenario_duplicate(request, pk):
    original = scenario_for(request, pk)
    with transaction.atomic():
        duplicate = Scenario.objects.create(company=request.company, name=(original.name[:130] + " · copy")[:140], inputs=original.inputs, created_by=request.user)
        audit(request, "scenario.duplicated", duplicate.pk, f"Source {original.pk}")
    return redirect("scenario", pk=duplicate.pk)


@require_POST
@workspace_required(edit=True)
def run_analysis(request, pk):
    scenario = scenario_for(request, pk)
    try:
        if request.POST.get("revision") != str(scenario.revision):
            raise ValueError("This case changed. Reload before running the comparison.")
        data = ScenarioInput.from_dict(scenario.inputs)
        if len(data.vessels) > min(20, request.company.max_vessels):
            raise ValueError("This case exceeds the current company vessel limit.")
        results = compare(data)
        snapshot = data.to_dict()
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        with transaction.atomic():
            run = AnalysisRun.objects.create(company=request.company, scenario=scenario, scenario_name=scenario.name, scenario_revision=scenario.revision, inputs=snapshot, results=results, input_digest=digest, engine_version=ENGINE_VERSION, ruleset_version=RULESET_VERSION, created_by=request.user)
            audit(request, "analysis.created", run.pk, f"Input SHA256 {digest}")
        return redirect("report", pk=run.pk)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("scenario", pk=pk)


def report_context(run, request):
    results = run.results
    # Older snapshots get an explanation from their own recorded inputs. Neither
    # the saved result nor the current editable case is changed or recalculated.
    notices = results.get("fuel_choice_notices")
    if notices is None:
        notices = fuel_choice_notices(ScenarioInput.from_dict(run.inputs))
    maximum = max(s["npv"] for s in results["strategies"]) or 1
    strategies = [s | {"bar_width": max(1, s["npv"] / maximum * 100),
                       "actions": s.get("actions") or strategy_actions(s)} for s in results["strategies"]]
    selected = next((s for s in strategies if s["key"] == request.GET.get("strategy")), strategies[0])
    baseline = next(s for s in strategies if s["key"] == "baseline")
    chart = {"annual": selected["annual"], "baseline": baseline["annual"], "strategies": [{"name": s["name"], "npv": s["npv"]} for s in strategies], "rows": selected["rows"]}
    return {"run": run, "result": results, "selected": selected, "strategies": strategies, "baseline": baseline, "chart_data": chart, "sources": results.get("sources", SOURCES), "checked_on": results.get("checked_on", CHECKED_ON), "savings_percent": selected["savings"] / results["baseline_npv"] * 100 if results["baseline_npv"] else 0, "active_nav": "reports", "fuel_choice_notices": notices}


@workspace_required()
def report(request, pk):
    run = get_object_or_404(AnalysisRun, pk=pk, company=request.company)
    return render(request, "portal/report.html", report_context(run, request))


def safe_csv(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


@workspace_required()
def export_run(request, pk, kind):
    run = get_object_or_404(AnalysisRun, pk=pk, company=request.company)
    if kind == "json":
        payload = {"schema_version": 1, "run_id": str(run.pk), "scenario": run.scenario_name, "scenario_revision": run.scenario_revision, "created_at": run.created_at.isoformat(), "engine_version": run.engine_version, "ruleset_version": run.ruleset_version, "input_sha256": run.input_digest, "inputs": run.inputs, "results": run.results, "sources": run.results.get("sources", SOURCES), "purpose": "Planning estimate; not a verified compliance submission."}
        response = HttpResponse(json.dumps(payload, indent=2, allow_nan=False), content_type="application/json")
    elif kind == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response.write("\ufeff")
        writer = csv.writer(response)
        extra_columns = [("baseline_fuel", "baseline_fuel"), ("alternative_fuel", "alternative"), ("baseline_fuel_t", "baseline_t"), ("alternative_fuel_t", "alternative_t"), ("sea_MGO_pilot_t", "pilot_t"), ("baseline_LNG_slip_pct", "baseline_slip_pct"), ("alternative_LNG_slip_pct", "alternative_slip_pct"), ("scoped_CH4_t", "scoped_ch4_t"), ("physical_energy_MJ", "energy_mj"), ("rewarded_energy_MJ", "rewarded_energy_mj"), ("RFNBO_energy_MJ", "rfnbo_energy_mj"), ("RFNBO_share", "rfnbo_share"), ("RFNBO_potential_shortfall_MJ", "rfnbo_deficit_mj"), ("GHG_penalty_EUR", "ghg_penalty_cost"), ("RFNBO_assumed_penalty_EUR", "rfnbo_penalty_cost"), ("current_sea_fuels_json", "baseline_fuels"), ("total_fuel_tonnes_json", "fuel_tonnes"), ("berth_fuels_json", "berth_fuels"), ("non_EU_berth_tonnes", "non_eu_berth_t"), ("sea_fuel_replacements_json", "fuel_replacements")]
        writer.writerow(["run_id", "engine_version", "ruleset_version", "scenario_revision", "strategy", "vessel", "reporting_year", "attained_gCO2e_MJ", "target_gCO2e_MJ", "balance_tCO2e", "ets_tCO2e", "fuel_EUR", "electricity_EUR", "ETS_EUR", "FuelEU_penalty_EUR", "pool_EUR", "implementation_EUR", "total_EUR", "NPV_EUR", "bank_open_tCO2e", "bank_used_tCO2e", "bank_close_tCO2e", "pool_transfer_tCO2e", "pool_buy_tCO2e", "residual_deficit_tCO2e"] + [name for name, _ in extra_columns])
        keys = ("vessel", "year", "attained_g", "target_g", "balance_t", "ets_t", "fuel_cost", "electricity_cost", "ets_cost", "penalty_cost", "pool_cost", "implementation_cost", "total_cost", "npv_cost", "bank_open_t", "bank_used_t", "bank_close_t", "pool_transfer_t", "pool_buy_t", "residual_deficit_t")
        for strategy in run.results["strategies"]:
            for row in strategy["rows"]:
                writer.writerow([str(run.pk), run.engine_version, run.ruleset_version, run.scenario_revision, safe_csv(strategy["name"])] + [safe_csv(row[k]) for k in keys] + [safe_csv(json.dumps(row[key], ensure_ascii=False, allow_nan=False) if isinstance(row.get(key), (dict, list)) else row.get(key, "")) for _, key in extra_columns])
            # Company-level other costs are explicit rows so export totals reconcile.
            for year in strategy["annual"]:
                writer.writerow([str(run.pk), run.engine_version, run.ruleset_version, run.scenario_revision, safe_csv(strategy["name"]), "Company other costs", year["year"], "", "", "", "", 0, 0, 0, 0, 0, year["other_cost"], year["other_cost"], year["other_cost"] / (1 + run.inputs["discount_rate"]) ** (year["year"] - run.inputs["start_year"]), "", "", "", "", "", ""] + [""] * len(extra_columns))
    else:
        raise Http404
    response["Content-Disposition"] = f'attachment; filename="maritime-carbon-{run.pk}.{kind}"'
    audit(request, "analysis.exported", run.pk, kind)
    return response


@workspace_required()
def reports(request):
    return render(request, "portal/reports.html", {"runs": AnalysisRun.objects.filter(company=request.company)[:100], "active_nav": "reports"})


@workspace_required(admin=True)
def team(request):
    form = MemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            company = Company.objects.select_for_update().get(pk=request.company.pk)
            if company.memberships.filter(user__is_active=True).count() >= company.max_users:
                form.add_error(None, "Your subscription's user limit has been reached.")
            else:
                from django.db import IntegrityError
                try:
                    with transaction.atomic():
                        user = get_user_model().objects.create_user(username=form.cleaned_data["username"], email=form.cleaned_data["email"], password=form.cleaned_data["password"])
                        Membership.objects.create(user=user, company=company, role=form.cleaned_data["role"])
                        audit(request, "member.created", user.pk, form.cleaned_data["role"])
                    messages.success(request, "User created. Share credentials through your approved secure channel.")
                    return redirect("team")
                except IntegrityError:
                    form.add_error("username", "This username is unavailable.")
    return render(request, "portal/team.html", {"form": form, "members": request.company.memberships.select_related("user"), "events": AuditEvent.objects.filter(company=request.company)[:30], "active_nav": "team"})


@require_POST
@workspace_required(admin=True)
def deactivate_member(request, pk):
    member = get_object_or_404(Membership, pk=pk, company=request.company)
    if member.user_id == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
    elif member.user.is_superuser or member.user.is_staff:
        return HttpResponseForbidden("Operator accounts must be managed by the service operator.")
    else:
        member.user.is_active = False
        member.user.save(update_fields=["is_active"])
        audit(request, "member.deactivated", member.user_id)
        messages.success(request, "User deactivated. Their previous reports remain available.")
    return redirect("team")


def methodology(request):
    return render(request, "portal/methodology.html", {"sources": SOURCES, "checked_on": CHECKED_ON, "engine_version": ENGINE_VERSION, "ruleset": RULESET_VERSION, "pathway": [(year, reduction * 100, REFERENCE_G * (1 - reduction)) for year, reduction in REDUCTIONS.items()], "active_nav": "methodology"})


def demo(request):
    # No customer records, account, write endpoints or stored results are used here.
    data = ScenarioInput(scope_confirmed=True, scope_notes="Illustrative ordinary EU voyage mix.", pool_enabled=True, pool_reference="Illustrative pool offer; not an executable quotation.")
    for fuel in data.fuels:
        if fuel.code in ("HVO", "FAME"):
            fuel.eligible = True
            fuel.evidence = "DEMO ONLY: hypothetical eligible non-food/feed supplier pathway. No real certificate is claimed."
            fuel.supply_t = 3500
    data.vessels = [Vessel(name="Vessel 1", gt=57000, sea_t=5200, berth_t=160, compatible=True), Vessel(name="Vessel 2", ship_type="tanker", gt=42000, sea_t=4100, berth_t=210, intra_share=.65, extra_share=.3, compatible=True, alternative="FAME"), Vessel(name="Vessel 3", gt=63000, sea_t=6100, berth_t=120, intra_share=.1, extra_share=.8, compatible=True)]
    scenario_name = "European fleet · illustrative case"
    if request.GET.get("fuels") == "transition":
        data.start_year, data.end_year = 2031, 2035
        scenario_name = "LNG & RFNBO transition · illustrative case"
        for fuel in data.fuels:
            if fuel.code in ("E_LNG", "E_METHANOL"):
                fuel.eligible = fuel.ets_eligible = True
                fuel.evidence = "DEMO ONLY: hypothetical RFNBO production, adjusted WtT and measured-factor evidence; no real certificate."
                fuel.wtt = -45 if fuel.code == "E_LNG" else -55
                if fuel.code == "E_METHANOL":
                    fuel.ch4, fuel.n2o, fuel.factors_confirmed = .00002, .0001, True
        reviewed = {"compatible": True, "max_blend": 1, "fuel_systems_confirmed": True, "technical_reference": "DEMO ONLY: hypothetical system, pilot, efficiency and cost review."}
        data.vessels = [
            Vessel(name="Vessel 1", fuel="LNG", fuel_consumer="diesel_slow", sea_t=3500, pilot_t=50, berth_t=100, alternative="E_LNG", alternative_consumer="diesel_slow", alternative_pilot_share=.015, **reviewed),
            Vessel(name="Vessel 2", sea_t=4500, berth_t=160, alternative="E_METHANOL", alternative_pilot_share=.03, alternative_energy_ratio=1.03, fuel_capex=5000000, fuel_annual=100000, **reviewed),
        ]
    result = compare(data)
    run = SimpleNamespace(results=result, scenario_name=scenario_name, inputs=data.to_dict(), engine_version=ENGINE_VERSION, ruleset_version=RULESET_VERSION, created_at=timezone.now(), input_digest="Illustrative example — no saved customer calculation", scenario_revision=1)
    context = report_context(run, request) | {"demo": True}
    return render(request, "portal/report.html", context)


def health(request):
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return HttpResponse("unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
