from __future__ import annotations
from datetime import time
from typing import Optional

from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from compcore.apps.events.models import Event
from .forms import SchedulingParamsForm
from .services.scheduler import Scheduler, Params


def _get_event_from_query(value: Optional[str]) -> Optional[Event]:
    """
    Intenta resolver un evento a partir de un valor en querystring:
    - primero como slug (string),
    - si falla, intenta como PK (entero).
    """
    if not value:
        return None
    # Intento por slug
    try:
        return Event.objects.get(slug=value)
    except Event.DoesNotExist:
        pass
    # Intento por PK
    try:
        pk = int(value)
        return Event.objects.get(pk=pk)
    except Exception:
        return None


def dashboard(request):
    """
    Vista única: formulario de parámetros + render del cronograma propuesto.
    Soporta preselección por GET (?event=<slug|id>) y autogeneración con defaults (?autostart=1).
    """
    # Defaults iniciales
    initial = {
        "start_time": time.fromisoformat("08:00"),
        "end_time": time.fromisoformat("18:00"),
        "briefing_min": 2,
        "reset_min": 5,
        "validation_min": 1,
        "call_offset_min": 5,
        "rest_base_min": 30,
        "rest_factor": 2.0,
        "block_cushion_min": 5,
        # lunch_* opcionales → None por defecto
    }

    # Elegir evento por defecto (el más reciente) o por querystring
    ev_from_qs = _get_event_from_query(request.GET.get("event"))
    if ev_from_qs is not None:
        initial["event"] = ev_from_qs.id
    else:
        latest_event = Event.objects.order_by("-start_date", "name").first()
        if latest_event:
            initial["event"] = latest_event.id

    # POST = generar con los parámetros enviados por el usuario
    if request.method == "POST":
        form = SchedulingParamsForm(request.POST)
        plan = None
        if form.is_valid():
            ev = form.cleaned_data["event"]
            p = Params(
                start_time=form.cleaned_data["start_time"],
                end_time=form.cleaned_data["end_time"],
                lunch_start=form.cleaned_data.get("lunch_start"),
                lunch_end=form.cleaned_data.get("lunch_end"),
                briefing_min=form.cleaned_data["briefing_min"],
                reset_min=form.cleaned_data["reset_min"],
                validation_min=form.cleaned_data["validation_min"],
                call_offset_min=form.cleaned_data["call_offset_min"],
                rest_base_min=form.cleaned_data["rest_base_min"],
                rest_factor=form.cleaned_data["rest_factor"],
                block_cushion_min=form.cleaned_data["block_cushion_min"],
            )
            scheduler = Scheduler(ev, p)
            plan = scheduler.generate()
        ctx = {"form": form, "plan": plan, "now": timezone.now()}
        return render(request, "scheduling/dashboard.html", ctx)

    # GET = mostrar formulario (con posibilidad de autogenerar si ?autostart=1)
    form = SchedulingParamsForm(initial=initial)

    # ¿Autogenerar con defaults?
    plan = None
    autostart = request.GET.get("autostart")
    if autostart and initial.get("event"):
        ev = get_object_or_404(Event, pk=initial["event"])
        p = Params(
            start_time=initial["start_time"],
            end_time=initial["end_time"],
            lunch_start=None,
            lunch_end=None,
            briefing_min=initial["briefing_min"],
            reset_min=initial["reset_min"],
            validation_min=initial["validation_min"],
            call_offset_min=initial["call_offset_min"],
            rest_base_min=initial["rest_base_min"],
            rest_factor=initial["rest_factor"],
            block_cushion_min=initial["block_cushion_min"],
        )
        scheduler = Scheduler(ev, p)
        plan = scheduler.generate()

    ctx = {"form": form, "plan": plan, "now": timezone.now()}
    return render(request, "scheduling/dashboard.html", ctx)