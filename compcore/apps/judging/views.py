# compcore/apps/judging/views.py
from __future__ import annotations
from typing import Dict, List, Any, Optional, Tuple

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.forms import modelformset_factory
from django.db import transaction
from django.urls import reverse

from compcore.apps.events.models import (
    Event, Division, Workout, WorkoutHeat, HeatAssignment
)
from .models import HeatResult
from .forms import LaneResultForm


# -------------------------------
# Utilidades
# -------------------------------
def _user_is_judge(request: HttpRequest) -> bool:
    u = request.user
    return bool(u.is_authenticated and (u.is_staff or u.is_superuser))


def judge_required(view_func):
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not _user_is_judge(request):
            return HttpResponseForbidden("Solo jueces.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def _fmt_seconds(sec: Optional[int]) -> str:
    if sec in (None, "",):
        return ""
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return ""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def _status_bad(status: Optional[str]) -> int:
    """
    Devuelve 0 si la marca es válida (OK/ok), 1 si no (para empujar al final).
    Si tu proyecto usa otros estados “buenos”, agrégalos aquí.
    """
    if not status:
        return 1
    return 0 if str(status).upper() == "OK" else 1


# -------------------------------
# Dashboard (compat)
# -------------------------------
@judge_required
def dashboard(request: HttpRequest, slug: Optional[str] = None):
    event = get_object_or_404(Event, slug=slug) if slug else None

    divisions_qs = Division.objects.filter(event=event).order_by("name") if event else Division.objects.none()
    workouts_qs = Workout.objects.filter(event=event).order_by("order") if event else Workout.objects.none()

    division_id = request.GET.get("division")
    current_division = None
    if division_id:
        try:
            current_division = divisions_qs.get(pk=int(division_id))
        except (Division.DoesNotExist, ValueError, TypeError):
            current_division = None

    workout_order_param = request.GET.get("workout")
    current_workout = None
    if workout_order_param:
        try:
            current_workout = workouts_qs.get(order=int(workout_order_param))
        except (Workout.DoesNotExist, ValueError, TypeError):
            current_workout = None

    heats_by_workout: Dict[int, List[WorkoutHeat]] = {}
    for w in workouts_qs:
        q = WorkoutHeat.objects.filter(workout=w)
        if current_division:
            q = q.filter(division=current_division)
        heats_by_workout[w.order] = list(q.order_by("heat_number"))

    heats = []
    if current_workout:
        q = WorkoutHeat.objects.filter(workout=current_workout)
        if current_division:
            q = q.filter(division=current_division)
        heats = list(q.order_by("heat_number"))

    ctx = {
        "event": event,
        "divisions": list(divisions_qs),
        "current_division": current_division,
        "workouts": list(workouts_qs),
        "current_workout": current_workout,
        "heats_by_workout": heats_by_workout,
        "heats": heats,
    }
    return render(request, "judging/dashboard.html", ctx)


# -------------------------------
# Editor de resultados por Heat (firma con division_id)
# URL: judging/<event_slug>/w<int:workout_order>/d<int:division_id>/heat/<int:heat_number>/
# -------------------------------
@judge_required
@transaction.atomic
def heat_results_edit(
    request: HttpRequest,
    event_slug: str,
    workout_order: int,
    division_id: int,
    heat_number: int,
):
    event = get_object_or_404(Event, slug=event_slug)
    workout = get_object_or_404(Workout, event=event, order=workout_order)
    division = get_object_or_404(Division, event=event, pk=division_id)
    heat = get_object_or_404(WorkoutHeat, workout=workout, division=division, heat_number=heat_number)

    # Asignaciones por lane
    assignments = list(
        HeatAssignment.objects.filter(heat=heat).select_related("team", "athlete_entry__user")
    )
    lane_to_assignment = {a.lane: a for a in assignments if a.lane}

    # Asegurar HeatResult 1..lane_count
    existing = {hr.lane for hr in HeatResult.objects.filter(heat=heat)}
    to_create: List[HeatResult] = []
    for lane in range(1, (heat.lane_count or 0) + 1):
        if lane not in existing:
            to_create.append(HeatResult(heat=heat, lane=lane))
    if to_create:
        HeatResult.objects.bulk_create(to_create)

    qs = HeatResult.objects.filter(heat=heat).select_related("team", "athlete_entry__user").order_by("lane")

    LaneFormSet = modelformset_factory(
        HeatResult,
        form=LaneResultForm,
        extra=0,
        can_delete=False,
    )

    if request.method == "POST":
        formset = LaneFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for inst in instances:
                a = lane_to_assignment.get(inst.lane)
                if a:
                    inst.team = a.team
                    inst.athlete_entry = a.athlete_entry
                if inst.penalties is None:
                    inst.penalties = 0
                inst.save()
            messages.success(request, "Resultados guardados.")
            return redirect(
                reverse(
                    "judging:judging_heat_results",
                    args=[event.slug, workout.order, division.id, heat.heat_number],
                )
            )
        else:
            messages.error(request, "Hay errores en el formulario. Revisa los campos.")
    else:
        formset = LaneFormSet(queryset=qs)

    # Filas para template (mostramos nombre aunque aún no haya resultado guardado)
    rows: List[Dict[str, Any]] = []
    for form in formset:
        lane = form.instance.lane
        a = lane_to_assignment.get(lane)
        rows.append(
            {
                "form": form,
                "lane": lane,
                "team": getattr(a, "team", None),
                "athlete_entry": getattr(a, "athlete_entry", None),
            }
        )

    ctx = {
        "event": event,
        "workout": workout,
        "division": division,
        "heat": heat,
        "formset": formset,
        "rows": rows,
    }
    return render(request, "judging/heat_results_edit.html", ctx)


# -------------------------------
# Resultados públicos (SIN divisiones)
# Orden de heats: WOD DESC + Heat DESC (como ya tienes)
# Orden interno de cada heat: mejor -> peor según scoring
# -------------------------------
def results_event(request: HttpRequest, event_slug: str):
    event = get_object_or_404(Event, slug=event_slug)

    # Traemos todo y armamos lista plana de heats
    results = (
        HeatResult.objects.filter(heat__workout__event=event)
        .select_related("heat", "heat__workout", "heat__division", "team", "athlete_entry__user")
        .order_by("-created_at")
    )

    # key: (workout_order, heat_number)
    heats_map: Dict[Tuple[int, int], Dict[str, Any]] = {}
    ordered_keys: List[Tuple[int, int]] = []

    for r in results:
        heat = r.heat
        w = heat.workout
        key = (w.order, heat.heat_number)
        if key not in heats_map:
            heats_map[key] = {
                "workout_order": w.order,
                "workout_name": w.name,
                "scoring": w.scoring,            # <- para ordenar filas según scoring
                "heat_number": heat.heat_number,
                "division_name": heat.division.name,
                "lane_count": heat.lane_count,
                "rows": [],
            }
            ordered_keys.append(key)

        # Participante mostrado (equipo o atleta)
        if r.team:
            participant = f"Equipo: {r.team.name}"
        elif r.athlete_entry and r.athlete_entry.user:
            full = r.athlete_entry.user.get_full_name() or r.athlete_entry.user.username
            participant = f"Atleta: {full}"
        else:
            participant = "—"

        heats_map[key]["rows"].append(
            {
                # visibles
                "lane": r.lane,
                "participant": participant,
                "time_display": _fmt_seconds(getattr(r, "time_seconds", None)),
                "reps": r.reps,
                "weight_kg": r.weight_kg,
                "tiebreak_display": _fmt_seconds(getattr(r, "tiebreak_seconds", None)),
                "penalties": r.penalties or 0,
                "status": r.status,
                "judge_name": r.judge_name,
                "notes": r.notes,
                # crudos (para ordenar internamente)
                "_time": getattr(r, "time_seconds", None),
                "_tiebreak": getattr(r, "tiebreak_seconds", None),
                "_reps": r.reps,
                "_weight": r.weight_kg,
                "_created": r.created_at,
            }
        )

    # Orden global de heats: Workout.order DESC, Heat.number DESC
    ordered_keys.sort(key=lambda k: (k[0], k[1]), reverse=True)

    # Orden interno por scoring
    def sort_rows(rows: List[Dict[str, Any]], scoring: Optional[str]) -> None:
        s = (scoring or "").upper()
        if s == "TIME":
            # Mejor: menor tiempo; desempate por penalidades (menor), luego tiebreak (menor)
            BIG = 10**9
            rows.sort(
                key=lambda r: (
                    _status_bad(r.get("status")),
                    r.get("_time") if r.get("_time") is not None else BIG,
                    r.get("penalties", 0),
                    r.get("_tiebreak") if r.get("_tiebreak") is not None else BIG,
                    r.get("_created")  # último recurso para estabilidad
                )
            )
        elif s == "WEIGHT":
            # Mejor: mayor peso
            INF = 10**9
            rows.sort(
                key=lambda r: (
                    _status_bad(r.get("status")),
                    -r.get("_weight") if r.get("_weight") is not None else INF,
                    r.get("penalties", 0),
                    -r.get("_reps") if r.get("_reps") is not None else 0,  # micro desempate
                    r.get("_created")
                )
            )
        elif s in ("REPS", "POINTS"):
            # Mejor: mayor reps
            INF = 10**9
            rows.sort(
                key=lambda r: (
                    _status_bad(r.get("status")),
                    -r.get("_reps") if r.get("_reps") is not None else INF,
                    r.get("penalties", 0),
                    r.get("_time") if r.get("_time") is not None else INF,  # opcional
                    r.get("_created")
                )
            )
        else:
            # Desconocido: mantener recientes primero
            rows.sort(key=lambda r: (r.get("_created"),), reverse=True)

    all_heats: List[Dict[str, Any]] = []
    for key in ordered_keys:
        bucket = heats_map[key]
        sort_rows(bucket["rows"], bucket.get("scoring"))
        all_heats.append(bucket)

    ctx = {
        "event": event,
        "all_heats": all_heats,  # lista plana sin divisiones; heats ya están DESC; filas ya están mejor->peor
    }
    return render(request, "judging/public_results.html", ctx)


# -------------------------------
# Detalle de heat (compat)
# -------------------------------
@judge_required
def heat_detail(request: HttpRequest, event_slug: str, workout_order: int, heat_number: int):
    event = get_object_or_404(Event, slug=event_slug)
    workout = get_object_or_404(Workout, event=event, order=workout_order)
    heat = get_object_or_404(WorkoutHeat, workout=workout, heat_number=heat_number)
    results = (
        HeatResult.objects
        .filter(heat=heat)
        .select_related("team", "athlete_entry__user")
        .order_by("lane")
    )
    ctx = {
        "event": event,
        "division": heat.division,
        "workout": workout,
        "heat": heat,
        "results": results,
    }
    return render(request, "judging/confirm.html", ctx)