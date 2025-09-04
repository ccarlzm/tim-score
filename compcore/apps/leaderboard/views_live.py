from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from compcore.apps.events.models import Event, Workout

try:
    # Estos helpers pueden no existir en tu repo; los hacemos opcionales
    from compcore.apps.events.services.heats import (
        participants_for_division,
        _workout_positions_for_individuals,
        _workout_positions_for_teams,
        _points_for_positions,
    )
except Exception:
    participants_for_division = None
    _workout_positions_for_individuals = None
    _workout_positions_for_teams = None
    _points_for_positions = None

def leaderboard_live_workout(request, event_slug: str, order: int):
    """Vista live por WOD. Renderiza una página básica aunque los servicios no estén disponibles."""
    event = get_object_or_404(Event, slug=event_slug)
    workout = get_object_or_404(Workout, event=event, order=order)

    if participants_for_division is None:
        # fallback muy simple para no romper
        return render(request, "leaderboard/event_leaderboard.html", {
            "event": event,
            "workouts": [{"order": workout.order, "title": getattr(workout, "title", None)}],
            "divisions": [],
            "live_warning": "Servicios de puntuación no disponibles; mostrando vista básica.",
        })

    # Si tienes servicios completos, aquí construirías la tabla en vivo por división
    # Dejamos placeholder para tu implementación específica.
    return render(request, "leaderboard/event_leaderboard.html", {
        "event": event,
        "workouts": [{"order": workout.order, "title": getattr(workout, "title", None)}],
        "divisions": [],
        "live_warning": "Vista LIVE en construcción.",
    })