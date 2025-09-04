from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse

from .models import Event, Division, Workout
from .services.heats import (
    propose_heats_for_division,
    seed_heats_from_ranking_for_division,
)


class ProposeForm(forms.Form):
    """
    Un único form que sirve tanto para GET (cargar dependientes)
    como para POST (generar propuesta). Se basa en self.data, así que
    funciona con request.GET y request.POST indistintamente.
    """
    MODE_CHOICES = (
        ("W1", "W1 · Propuesta secuencial"),
        ("W2PLUS", "W2+ · Sembrar por ranking"),
    )

    event = forms.ModelChoiceField(
        queryset=Event.objects.all().order_by("-start_date", "name"),
        required=True,
        label="Evento",
    )
    division = forms.ModelChoiceField(
        queryset=Division.objects.none(),
        required=True,
        label="División",
    )
    workout = forms.ModelChoiceField(
        queryset=Workout.objects.none(),
        required=True,
        label="Workout",
    )
    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="W1",
        required=True,
        label="Modo",
    )
    lane_count = forms.IntegerField(
        required=False,
        min_value=1,
        label="Carriles",
        help_text="Opcional. Si no se indica, se usa el cupo de la división o 8.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        ev = None
        # self.data funciona con GET o POST
        event_val = self.data.get("event") or self.initial.get("event")
        if event_val:
            try:
                ev = Event.objects.get(pk=event_val)
            except Event.DoesNotExist:
                ev = None

        if ev:
            self.fields["division"].queryset = Division.objects.filter(event=ev).order_by("name")
            self.fields["workout"].queryset = Workout.objects.filter(event=ev).order_by("order")
        else:
            self.fields["division"].queryset = Division.objects.none()
            self.fields["workout"].queryset = Workout.objects.none()


@staff_member_required
def admin_propose_heats(request):
    """
    Comportamiento:
    - GET sin 'event' => muestro solo selector de evento (para cargar dependientes).
    - GET con 'event' => muestro form con divisiones y workouts del evento elegido.
    - POST (con todo válido) => ejecuto propuesta y muestro mensaje.
    """
    if request.method == "POST":
        form = ProposeForm(request.POST)
        if form.is_valid():
            event = form.cleaned_data["event"]
            division = form.cleaned_data["division"]
            workout = form.cleaned_data["workout"]
            mode = form.cleaned_data["mode"]
            lane_count = form.cleaned_data.get("lane_count") or 0

            if mode == "W1":
                res = propose_heats_for_division(workout.id, division.id, default_lane_count=lane_count or 8)
                messages.success(
                    request,
                    f"Propuesta W1: {res['assignments']} asignaciones; {res['heats_touched']} heats (lane_count={res['lane_count_used']}).",
                )
            else:
                res = seed_heats_from_ranking_for_division(workout.id, division.id, default_lane_count=lane_count or 8)
                messages.success(
                    request,
                    f"Ranking W2+: {res['assignments']} asignaciones; {res['heats_touched']} heats (lane_count={res['lane_count_used']}).",
                )
            return redirect(reverse("admin_propose_heats"))
        # Si POST inválido, seguimos mostrando el form con errores
        return render(request, "events/admin_propose_heats.html", {"form": form, "event_selected": True})

    # GET
    form = ProposeForm(request.GET or None)
    event_selected = bool(request.GET.get("event"))
    return render(request, "events/admin_propose_heats.html", {"form": form, "event_selected": event_selected})