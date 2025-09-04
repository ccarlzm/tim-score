from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _

from .models import Event, Division, Workout, WorkoutHeat, HeatAssignment
from .services.heats import (
    propose_heats_for_division,
    seed_heats_from_ranking_for_division,
)

# -----------------------------
# Event
# -----------------------------
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "start_date", "end_date")
    search_fields = ("name",)
    list_filter = ("status",)

# -----------------------------
# Division
# -----------------------------
@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ("event", "name", "team_size", "gender", "heat_capacity")
    list_filter = ("event", "gender", "team_size")
    search_fields = ("name", "slug")

# -----------------------------
# Inline para asignaciones
# -----------------------------
class HeatAssignmentInline(admin.TabularInline):
    model = HeatAssignment
    extra = 0
    autocomplete_fields = ["athlete_entry", "team"]
    fields = ["athlete_entry", "team", "lane", "is_manual", "locked"]
    ordering = ("lane",)

# -----------------------------
# Workout (con la vista /propose/)
# -----------------------------
@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("event", "order", "name", "scoring", "is_published")
    list_filter = ("event", "is_published", "scoring")
    search_fields = ("name", "description")
    ordering = ("event", "order")
    actions = ["action_publish_workouts", "action_unpublish_workouts"]

    @admin.action(description=_("Publicar workouts seleccionados"))
    def action_publish_workouts(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f"{updated} workouts publicados.", level=messages.SUCCESS)

    @admin.action(description=_("Despublicar workouts seleccionados"))
    def action_unpublish_workouts(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated} workouts despublicados.", level=messages.SUCCESS)

    # === URL custom DENTRO de WorkoutAdmin ===
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "propose/",
                self.admin_site.admin_view(self.propose_view),
                name="events_workout_propose",
            ),
        ]
        return custom + urls  # primero las custom

    # === Vista: /admin/events/workout/propose/ ===
    def propose_view(self, request):
        class ProposeForm(forms.Form):
            MODE_CHOICES = (("W1", "W1 (secuencial)"), ("W2P", "W2+ (por ranking)"))

            event = forms.ModelChoiceField(queryset=Event.objects.all(), required=True, label="Evento")
            division = forms.ModelChoiceField(queryset=Division.objects.none(), required=True, label="División")
            workout = forms.ModelChoiceField(queryset=Workout.objects.none(), required=True, label="Workout")
            mode = forms.ChoiceField(choices=MODE_CHOICES, initial="W1", required=True, label="Modo")
            lane_count = forms.IntegerField(
                required=False, min_value=1, label="Carriles",
                help_text="Si lo dejas vacío: División.heat_capacity → Evento.lanes_default → 8."
            )
            # NUEVO
            heat_start = forms.IntegerField(required=False, min_value=1, label="Número inicial de heat")

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                ev = None
                val = self.data.get("event") or self.initial.get("event")
                if val:
                    try:
                        ev = Event.objects.get(pk=val)
                    except Event.DoesNotExist:
                        ev = None
                if ev:
                    self.fields["division"].queryset = Division.objects.filter(event=ev).order_by("name")
                    self.fields["workout"].queryset = Workout.objects.filter(event=ev).order_by("order")

        if request.method == "POST":
            form = ProposeForm(request.POST)
            if form.is_valid():
                event = form.cleaned_data["event"]
                division = form.cleaned_data["division"]
                workout = form.cleaned_data["workout"]
                mode = form.cleaned_data["mode"]
                lane_count = form.cleaned_data.get("lane_count")  # puede ser None
                heat_start = form.cleaned_data.get("heat_start")  # NUEVO

                if mode == "W1":
                    res = propose_heats_for_division(
                        workout.id,
                        division.id,
                        default_lane_count=lane_count or 0,
                        start_heat_number=heat_start or None,  # NUEVO
                    )
                    messages.success(
                        request,
                        f"Propuesta W1: {res.get('assignments', 0)} asignaciones; "
                        f"{res.get('heats_touched', 0)} heats (lane_count={res.get('lane_count_used', '-')}). "
                        "Los heats quedan en BORRADOR."
                    )
                else:
                    res = seed_heats_from_ranking_for_division(
                        workout.id,
                        division.id,
                        default_lane_count=lane_count or 0,
                        start_heat_number=heat_start or None,  # NUEVO
                    )
                    messages.success(
                        request,
                        f"Ranking W2+: {res.get('assignments', 0)} asignaciones; "
                        f"{res.get('heats_touched', 0)} heats (lane_count={res.get('lane_count_used', '-')}). "
                        "Los heats quedan en BORRADOR."
                    )

                # Aviso si hubo conflicto de numeración solicitada
                if res.get("start_requested"):
                    if res.get("start_conflict"):
                        messages.warning(
                            request,
                            (
                                "El número inicial solicitado "
                                f"({res.get('start_requested')}) ya estaba ocupado en este workout. "
                                f"Se ajustó automáticamente a {res.get('start_applied')} para evitar colisiones."
                            ),
                        )
                    else:
                        messages.info(
                            request,
                            "Numeración aplicada desde el número inicial solicitado: "
                            f"{res.get('start_applied')}."
                        )

                # Redirigir a la misma vista en el namespace del admin
                url = reverse("admin:events_workout_propose")
                if form.cleaned_data.get("event"):
                    return redirect(f"{url}?event={event.id}")
                return redirect(url)

            # POST inválido → mantener estado
            return render(request, "admin/events/workout/propose.html", {"form": form, "event_selected": True})

        # GET
        initial = {}
        if request.GET.get("event"):
            initial["event"] = request.GET["event"]
        form = ProposeForm(request.GET or None, initial=initial)
        event_selected = bool(request.GET.get("event"))
        return render(request, "admin/events/workout/propose.html", {"form": form, "event_selected": event_selected})


# -----------------------------
# WorkoutHeat
# -----------------------------
@admin.register(WorkoutHeat)
class WorkoutHeatAdmin(admin.ModelAdmin):
    list_display = ("workout", "division", "heat_number", "lane_count", "is_published")
    list_filter = ("workout__event", "division", "is_published")
    ordering = ("workout__event", "workout__order", "heat_number")
    inlines = [HeatAssignmentInline]
    readonly_fields = ("heat_number",)
    actions = ["publicar", "despublicar"]

    @admin.action(description=_("Publicar heats seleccionados"))
    def publicar(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f"{updated} heats publicados.", level=messages.SUCCESS)

    @admin.action(description=_("Despublicar heats seleccionados"))
    def despublicar(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated} heats despublicados.", level=messages.SUCCESS)