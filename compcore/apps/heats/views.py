# compcore/apps/heats/views.py
from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch

from compcore.apps.events.models import Event, Workout, WorkoutHeat, HeatAssignment
from compcore.apps.registration.models import Team, AthleteEntry

def public_heats(request, event_slug, order):
    """
    Vista pública de heats para un workout específico de un evento.
    Restaura el endpoint esperado por tus templates: name='public_heats'
    URL: /heats/<event_slug>/w<int:order>/
    """
    event = get_object_or_404(Event, slug=event_slug)
    workout = get_object_or_404(Workout, event=event, order=order)

    heats_qs = (
        WorkoutHeat.objects
        .filter(workout=workout)
        .select_related('division')
        .order_by('heat_number')
    )

    # Prefetch de assignments por heat (con team/athlete)
    assignments_qs = (
        HeatAssignment.objects
        .select_related('team', 'athlete_entry', 'heat')
        .order_by('lane')
    )
    heats = list(
        heats_qs.prefetch_related(
            Prefetch('heatassignment_set', queryset=assignments_qs, to_attr='assignments')
        )
    )

    ctx = {
        'event': event,
        'workout': workout,
        'heats': heats,
    }
    return render(request, 'heats/public_heats.html', ctx)