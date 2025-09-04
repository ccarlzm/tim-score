from __future__ import annotations
import math
from typing import Any, Dict, List, Tuple
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from compcore.apps.events.models import Event, Division, Workout, WorkoutHeat
from compcore.apps.judging.models import HeatResult
from compcore.apps.registration.models import Team, AthleteEntry


# ---------- Utilidades ----------

def _score_key(workout: Workout, r: HeatResult) -> Tuple:
    """
    Clave de ordenamiento según tipo de scoring:
      - TIME: menor tiempo mejor (tiebreak menor mejor, menos penalidades mejor)
      - REPS: mayor reps mejor (menos penalidades mejor)
      - WEIGHT: mayor peso mejor (menos penalidades mejor)
    """
    scoring = getattr(workout, "scoring", None)
    if scoring == "TIME":
        t = r.time_seconds if r.time_seconds is not None else 10**9
        tb = r.tiebreak_seconds if r.tiebreak_seconds is not None else 10**9
        return (t, tb, r.penalties or 0)
    if scoring == "REPS":
        reps = r.reps if r.reps is not None else 0
        return (-reps, r.penalties or 0)
    if scoring == "WEIGHT":
        w = r.weight_kg if r.weight_kg is not None else 0
        return (-w, r.penalties or 0)
    # Fallback si no hay métrica: por lane
    return (r.lane or 10**6,)


def _registered_participants_for_division(d: Division) -> List[Any]:
    """
    Participantes “de referencia” de la división (para N y para mostrar filas sin resultados):
      - team_size == 1 -> atletas individuales (AthleteEntry sin team)
      - team_size > 1  -> equipos (Team)
    """
    team_size = getattr(d, "team_size", 1)
    if team_size == 1:
        return list(AthleteEntry.objects.filter(division=d, team__isnull=True).select_related("user"))
    return list(Team.objects.filter(division=d))


# ---------- Vistas ----------

def leaderboard_index(request):
    events = Event.objects.all().order_by("-start_date")
    return render(request, "leaderboard/index.html", {"events": events})


def event_leaderboard(request, slug: str):
    """
    Leaderboard por evento (una tabla por división) con puntaje entero:
      • TIME: menor tiempo mejor
      • REPS: mayor reps mejor
      • WEIGHT: mayor peso mejor
    Puntos:
      • 1º = 100; siguientes: decrementos de ceil(100 / N) donde N es el número de participantes de la división.
      • Puntos enteros (sin decimales). Límite inferior **2**.
    Compat:
      • Se entregan variables 'workouts' y 'divisions' (listas simples) para el panel superior del template global.
    """
    event = get_object_or_404(Event, slug=slug)

    # Solo WODs publicados, ordenados
    workouts_qs = Workout.objects.filter(event=event, is_published=True).order_by("order")
    divisions_qs = Division.objects.filter(event=event).order_by("name")

    workouts = list(workouts_qs)
    divisions = list(divisions_qs)

    # Datos simples para panel superior (compat)
    workouts_simple = [
        {
            "order": w.order,
            "name": getattr(w, "name", f"W{w.order}"),
            "title": getattr(w, "name", f"W{w.order}"),
            "live_url": reverse("leaderboard_live_workout", args=[event.slug, w.order]),
        }
        for w in workouts
    ]
    divisions_simple = [{"name": d.name, "slug": d.slug} for d in divisions]

    # Heats por (workout, division)
    heats_by_wod_div: Dict[Tuple[int, int], List[int]] = {}
    if workouts and divisions:
        for wh in WorkoutHeat.objects.filter(workout__in=workouts, division__in=divisions).only(
            "id", "workout_id", "division_id"
        ):
            heats_by_wod_div.setdefault((wh.workout_id, wh.division_id), []).append(wh.id)

    division_tables: List[Dict[str, Any]] = []

    for d in divisions:
        # Participantes base
        registered = _registered_participants_for_division(d)
        participants = set(registered)
        N = len(registered) if registered else 0

        # Puntos por workout order
        points_by_order: Dict[int, Dict[Any, int]] = {}

        for w in workouts:
            heat_ids = heats_by_wod_div.get((w.id, d.id), [])
            if not heat_ids:
                continue

            results = list(
                HeatResult.objects.filter(heat_id__in=heat_ids).select_related("team", "athlete_entry")
            )
            if not results:
                continue

            ordered = sorted(results, key=lambda r: _score_key(w, r))
            step = math.ceil(100 / N) if N and N > 0 else 0  # redondeo hacia arriba

            by_entity: Dict[Any, int] = {}
            for idx, r in enumerate(ordered):
                ent = r.team or r.athlete_entry
                if not ent:
                    continue
                participants.add(ent)
                pts = 100 - idx * step
                # --------- NUEVA REGLA: mínimo 2 puntos ---------
                if pts < 2:
                    pts = 2
                by_entity[ent] = int(pts)

            points_by_order[w.order] = by_entity

        # Construir filas (todas las entidades)
        workout_orders = [w.order for w in workouts]
        rows: List[Dict[str, Any]] = []
        for ent in list(participants):
            name = str(ent)
            cells: List[Any] = []
            total = 0
            for order in workout_orders:
                v = points_by_order.get(order, {}).get(ent)
                if v is None:
                    cells.append("-")
                else:
                    v_int = int(v)
                    cells.append(v_int)
                    total += v_int
            rows.append({"name": name, "cells": cells, "total": int(total)})

        # Orden por total desc
        rows.sort(key=lambda r: r["total"], reverse=True)

        division_tables.append(
            {
                "division": d,
                "workout_orders": workout_orders,
                "columns": workouts,  # para headers W1..Wn
                "rows": rows,
            }
        )

    ctx = {
        "event": event,
        "event_display_name": getattr(event, "name", None) or event.slug,
        "workouts": workouts_simple,
        "divisions": divisions_simple,
        "division_tables": division_tables,
    }
    return render(request, "leaderboard/event_leaderboard.html", ctx)


def leaderboard_live_workout(request, event_slug: str, order: int):
    """
    Vista simple para "live por WOD" que usa el mismo criterio de orden del leaderboard.
    Se deja minimalista para mantener compatibilidad de rutas y navegación.
    """
    event = get_object_or_404(Event, slug=event_slug)
    workout = get_object_or_404(Workout, event=event, order=order, is_published=True)

    # Todas las divisiones del evento
    divisions = list(Division.objects.filter(event=event).order_by("name"))

    # Heats para este workout
    heats = list(WorkoutHeat.objects.filter(workout=workout, division__in=divisions))

    # Resultados del workout, agrupados por división
    by_division: Dict[int, List[HeatResult]] = {}
    if heats:
        heat_ids = [h.id for h in heats]
        for r in HeatResult.objects.filter(heat_id__in=heat_ids).select_related("team", "athlete_entry", "heat__division"):
            by_division.setdefault(r.heat.division_id, []).append(r)

    # Ordenar cada división según _score_key
    live_tables: List[Dict[str, Any]] = []
    for d in divisions:
        rows: List[Dict[str, Any]] = []
        results = by_division.get(d.id, [])
        if results:
            ordered = sorted(results, key=lambda r: _score_key(workout, r))
            for r in ordered:
                ent = r.team or r.athlete_entry
                metric = "-"
                if workout.scoring == "TIME" and r.time_seconds is not None:
                    metric = r.time_seconds
                elif workout.scoring == "REPS" and r.reps is not None:
                    metric = r.reps
                elif workout.scoring == "WEIGHT" and r.weight_kg is not None:
                    metric = r.weight_kg
                rows.append({"name": str(ent) if ent else "-", "metric": metric})
        live_tables.append({"division": d, "rows": rows})

    return render(
        request,
        "leaderboard/live_workout.html",
        {
            "event": event,
            "workout": workout,
            "live_tables": live_tables,
        },
    )