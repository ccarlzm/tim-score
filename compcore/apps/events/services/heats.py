# compcore/apps/events/services/heats.py
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple, Optional

from django.db import transaction
from django.db.models import Max

# Import relativo correcto (desde services → events)
from ..models import Event, Division, Workout, WorkoutHeat, HeatAssignment


# ------------------------------
# Capacidad de carriles
# ------------------------------
def _resolve_lane_capacity(event: Event, division: Division, lane_count_param: int | None) -> int:
    if lane_count_param and lane_count_param > 0:
        return int(lane_count_param)

    lc_div = getattr(division, "heat_capacity", None)
    if lc_div and lc_div > 0:
        return int(lc_div)

    lc_ev = getattr(event, "lanes_default", None)
    if lc_ev and lc_ev > 0:
        return int(lc_ev)

    return 8


def _get_entrants_for_division(division: Division) -> List[Tuple[str, int]]:
    """
    Devuelve [('team'|'athlete', pk)] en el ORDEN natural de registro.
    - team_size > 1 => equipos (Team)
    - team_size == 1 => atletas individuales (AthleteEntry sin team)
    """
    from compcore.apps.registration.models import Team, AthleteEntry  # import local para evitar ciclos

    if getattr(division, "team_size", 1) and division.team_size > 1:
        qs = Team.objects.filter(division=division).order_by("id")
        return [("team", t.pk) for t in qs]

    qs = AthleteEntry.objects.filter(division=division, team__isnull=True).order_by("id")
    return [("athlete", a.pk) for a in qs]


# -------------------------------------------
# Crear heats y asignar (común W1/W2+)
# -------------------------------------------
def _assign_to_heats(
    workout: Workout,
    division: Division,
    entrants: List[Tuple[str, int]],
    lane_count: int,
    start_heat_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    - Elimina heats BORRADOR existentes para (workout, division) y rehace con lane_count solicitado.
    - Crea heats en BORRADOR (is_published=False).
    - Numeración:
        * Por defecto continúa desde max(heat_number) del workout.
        * Si start_heat_number >= 1:
            - Si no hay colisión en el rango, comienza EXACTO ahí.
            - Si hay colisión, ajusta a (max_existente + 1) para evitar duplicados.
    """
    if lane_count <= 0:
        lane_count = 8

    touched = 0
    assignments = 0

    with transaction.atomic():
        # Borrar borradores previos de esta división para este workout
        WorkoutHeat.objects.filter(workout=workout, division=division, is_published=False).delete()

        total = len(entrants)
        if total == 0:
            return {
                "heats_touched": 0,
                "assignments": 0,
                "lane_count_used": lane_count,
                "start_requested": start_heat_number,
                "start_applied": None,
                "start_conflict": False,
            }

        needed_heats = (total + lane_count - 1) // lane_count

        current_max = WorkoutHeat.objects.filter(workout=workout).aggregate(m=Max("heat_number")).get("m") or 0
        start_conflict = False
        if start_heat_number and start_heat_number >= 1:
            rng = range(start_heat_number, start_heat_number + needed_heats)
            conflicts = WorkoutHeat.objects.filter(workout=workout, heat_number__in=list(rng)).exists()
            if conflicts:
                start_base = current_max  # ajustar al siguiente libre
                start_conflict = True
            else:
                start_base = start_heat_number - 1  # aplicar exacto
        else:
            start_base = current_max  # comportamiento previo

        created_heats: List[WorkoutHeat] = []
        for i in range(needed_heats):
            h = WorkoutHeat.objects.create(
                workout=workout,
                division=division,
                heat_number=start_base + i + 1,
                lane_count=lane_count,
                is_published=False,
            )
            created_heats.append(h)
            touched += 1

        # Asignar participantes lane por lane
        heat_idx = 0
        lane_cursor = 1
        current_heat = created_heats[heat_idx]

        for kind, pk in entrants:
            if lane_cursor > lane_count:
                heat_idx += 1
                current_heat = created_heats[heat_idx]
                lane_cursor = 1

            if kind == "team":
                HeatAssignment.objects.create(
                    heat=current_heat, team_id=pk, lane=lane_cursor, is_manual=False, locked=False
                )
            else:
                HeatAssignment.objects.create(
                    heat=current_heat, athlete_entry_id=pk, lane=lane_cursor, is_manual=False, locked=False
                )
            assignments += 1
            lane_cursor += 1

    return {
        "heats_touched": touched,
        "assignments": assignments,
        "lane_count_used": lane_count,
        "start_requested": start_heat_number,
        "start_applied": (start_base + 1) if touched > 0 else None,
        "start_conflict": start_conflict,
    }


# ------------------------------------------------------
# Ranking acumulado para W2+ (idéntico a tu ZIP original)
# ------------------------------------------------------
def _registered_participants_for_division(division: Division):
    """Participantes “base” de la división (Team o AthleteEntry)."""
    from compcore.apps.registration.models import Team, AthleteEntry
    if getattr(division, "team_size", 1) and division.team_size > 1:
        return list(Team.objects.filter(division=division))
    return list(AthleteEntry.objects.filter(division=division, team__isnull=True))


def _score_key(workout: Workout, result_obj: Any):
    """Clave de ordenación según el tipo de scoring del workout."""
    scoring = getattr(workout, "scoring", "").upper()
    if scoring == "TIME":
        return (
            int(getattr(result_obj, "time_seconds", 10**9) or 10**9),
            int(getattr(result_obj, "tiebreak_seconds", 10**9) or 10**9),
            int(getattr(result_obj, "penalties", 10**9) or 10**9),
        )
    elif scoring == "REPS":
        return (
            -(int(getattr(result_obj, "reps", 0) or 0)),
            int(getattr(result_obj, "penalties", 10**9) or 10**9),
        )
    elif scoring == "WEIGHT":
        return (
            -(int(getattr(result_obj, "weight_kg", 0) or 0)),
            int(getattr(result_obj, "penalties", 10**9) or 10**9),
        )
    elif scoring == "POINTS":
        return (
            -(int(getattr(result_obj, "points", 0) or 0)),
            int(getattr(result_obj, "penalties", 10**9) or 10**9),
        )
    return (10**9,)


def _ranking_for_division(workout: Workout, division: Division) -> List[Tuple[str, int]]:
    """
    Devuelve [('team'|'athlete', pk)] en orden PEOR→MEJOR usando puntaje acumulado.
    - Calcula puntos solo con workouts PUBLICADOS del mismo evento con order < actual.
    - 1º = 100; decremento step=ceil(100/N); piso 2 puntos.
    - Desempate: índice del último workout (peor primero) y luego nombre.

    🔧 Ajuste pedido: contar resultados de heats aunque NO estén publicados.
      → Se mantiene el filtro de workouts publicados,
        pero ya NO se exige is_published en los heats previos.
    """
    from compcore.apps.judging.models import HeatResult
    from compcore.apps.registration.models import Team, AthleteEntry

    participants = _registered_participants_for_division(division)
    N = len(participants)
    if N == 0:
        return []

    prev_workouts = list(
        Workout.objects.filter(event=workout.event, is_published=True, order__lt=workout.order).order_by("order")
    )

    heats_by_wod: Dict[int, List[int]] = {}
    for w in prev_workouts:
        # 🔧 AQUÍ EL CAMBIO: quitamos is_published=True en heats previos
        heats_by_wod[w.id] = list(
            WorkoutHeat.objects.filter(workout=w, division=division).values_list("id", flat=True)
        )

    total_points: Dict[Any, int] = {}
    last_ranking_index: Dict[Any, int] = {}

    for w in prev_workouts:
        heat_ids = heats_by_wod.get(w.id, [])
        if not heat_ids:
            continue

        results = list(HeatResult.objects.filter(heat_id__in=heat_ids).select_related("team", "athlete_entry"))
        if not results:
            continue

        ordered = sorted(results, key=lambda r: _score_key(w, r))
        step = math.ceil(100 / N) if N > 0 else 0

        by_entity: Dict[Any, int] = {}
        for idx, r in enumerate(ordered):
            ent = r.team or r.athlete_entry
            if not ent:
                continue
            pts = 100 - idx * step
            if pts < 2:
                pts = 2
            by_entity[ent] = int(pts)

        for ent, pts in by_entity.items():
            total_points[ent] = total_points.get(ent, 0) + int(pts)

        # índice de desempate: peor primero en el último workout
        for idx, r in enumerate(reversed(ordered)):
            ent = r.team or r.athlete_entry
            if ent is not None:
                last_ranking_index[ent] = idx

    enriched: List[Tuple[str, int, int, int, str]] = []
    for ent in participants:
        total = total_points.get(ent, 0)
        last_idx = last_ranking_index.get(ent, -1)

        if isinstance(ent, Team):
            nm = getattr(ent, "name", "") or ""
            enriched.append(("team", ent.pk, total, last_idx, nm))
        else:
            nm = ""
            if hasattr(ent, "athlete") and getattr(ent.athlete, "full_name", None):
                nm = ent.athlete.full_name or ""
            if not nm:
                nm = str(getattr(ent, "id", ""))
            enriched.append(("athlete", ent.pk, total, last_idx, nm))

    enriched.sort(key=lambda x: (x[2], -x[3], x[4]))  # total asc, peor últimoW primero, nombre asc
    return [(kind, pk) for (kind, pk, _total, _last_idx, _name) in enriched]


# ------------------------------
# Entradas públicas de servicio
# ------------------------------
def propose_heats_for_division(
    workout_id: int,
    division_id: int,
    default_lane_count: int = 0,
    start_heat_number: Optional[int] = None,
) -> Dict[str, Any]:
    workout = Workout.objects.select_related("event").get(pk=workout_id)
    division = Division.objects.select_related("event").get(pk=division_id)
    lane_count = _resolve_lane_capacity(workout.event, division, default_lane_count)
    entrants = _get_entrants_for_division(division)
    return _assign_to_heats(workout, division, entrants, lane_count, start_heat_number=start_heat_number)


def seed_heats_from_ranking_for_division(
    workout_id: int,
    division_id: int,
    default_lane_count: int = 0,
    start_heat_number: Optional[int] = None,
) -> Dict[str, Any]:
    workout = Workout.objects.select_related("event").get(pk=workout_id)
    division = Division.objects.select_related("event").get(pk=division_id)
    lane_count = _resolve_lane_capacity(workout.event, division, default_lane_count)
    entrants = _ranking_for_division(workout, division)
    return _assign_to_heats(workout, division, entrants, lane_count, start_heat_number=start_heat_number)