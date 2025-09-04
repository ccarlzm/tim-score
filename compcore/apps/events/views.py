from __future__ import annotations

from typing import Dict, Any, List

from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch

from .models import Event, Workout, WorkoutHeat, Division, HeatAssignment


# -------- Utilidades --------

def _user_is_judge(request: HttpRequest) -> bool:
    u = request.user
    if not u.is_authenticated:
        return False
    # Permitimos staff o miembros del grupo "judges"
    return u.is_staff or u.groups.filter(name="judges").exists()


def _assignment_display_name(a: HeatAssignment) -> str:
    """
    Nombre legible del participante.
    """
    if a.team_id:
        try:
            return a.team.name
        except Exception:
            return str(a.team) if a.team else "Equipo"
    if a.athlete_entry_id:
        ae = a.athlete_entry
        for attr in ("full_name", "name"):
            if hasattr(ae, attr) and getattr(ae, attr):
                return getattr(ae, attr)
        if hasattr(ae, "user") and ae.user:
            if getattr(ae.user, "get_full_name", None):
                try:
                    return ae.user.get_full_name() or str(ae.user)
                except Exception:
                    return str(ae.user)
    return "Participante"


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


def event_list(request: HttpRequest) -> HttpResponse:
    # Lista de eventos (sin leaderboard global)
    events = Event.objects.all().order_by("-start_date", "name")
    return render(request, "events/list.html", {"events": events})


def event_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Página del evento:
      - Descripción
      - Categorías/Divisiones del evento
      - Botones: Ver WODs, Ver Heats (página plana del primer WOD publicado),
        Leaderboard, Jueces (solo si es juez)
      - Sección WODs: solo WODs publicados
      - Sección Heats: solo Heats publicados (ordenados por heat_number asc)
    """
    event = get_object_or_404(Event, slug=slug)

    # Heats publicados ordenados estrictamente por número
    published_heats_sorted = (
        WorkoutHeat.objects.filter(is_published=True)
        .select_related("division")
        .order_by("heat_number")
    )

    # WODs publicados con sus heats publicados (ya ordenados)
    workouts = (
        Workout.objects.filter(event=event, is_published=True)
        .order_by("order")
        .prefetch_related(
            Prefetch("workoutheat_set", queryset=published_heats_sorted, to_attr="published_heats")
        )
    )

    # Divisiones/Categorías del evento
    divisions = Division.objects.filter(event=event).order_by("name")

    # Primer workout publicado para botón grande "Ver Heats"
    first_workout = workouts.first()

    ctx: Dict[str, Any] = {
        "event": event,
        "workouts": workouts,
        "divisions": divisions,
        "is_judge": _user_is_judge(request),
        "first_workout": first_workout,
    }
    return render(request, "events/detail.html", ctx)


def public_heats(request: HttpRequest, event_slug: str, order: int) -> HttpResponse:
    """
    Tabla plana de heats publicados para un workout específico,
    SIEMPRE ordenados por heat_number ascendente.
    """
    event = get_object_or_404(Event, slug=event_slug)
    workout = get_object_or_404(Workout, event=event, order=order, is_published=True)

    heats = (
        WorkoutHeat.objects.filter(workout=workout, is_published=True)
        .select_related("division")
        .order_by("heat_number")
    )

    return render(
        request,
        "events/public_heats.html",
        {"event": event, "workout": workout, "heats": heats},
    )


def heat_detail(request: HttpRequest, event_slug: str, order: int, heat_number: int) -> HttpResponse:
    """
    Detalle público de un heat (read-only).
    """
    event = get_object_or_404(Event, slug=event_slug)
    workout = get_object_or_404(Workout, event=event, order=order, is_published=True)
    heat = get_object_or_404(
        WorkoutHeat, workout=workout, heat_number=heat_number, is_published=True
    )

    assignments = (
        HeatAssignment.objects.filter(heat=heat)
        .select_related("team", "athlete_entry")
        .order_by("lane")
    )
    rows: List[Dict[str, Any]] = []
    for a in assignments:
        rows.append(
            {
                "lane": a.lane,
                "name": _assignment_display_name(a),
                "is_manual": a.is_manual,
                "locked": a.locked,
            }
        )

    return render(
        request,
        "events/heat_detail.html",
        {"event": event, "workout": workout, "heat": heat, "rows": rows},
    )


def event_leaderboard(request: HttpRequest, slug: str) -> HttpResponse:
    event = get_object_or_404(Event, slug=slug)
    return render(request, "events/leaderboard.html", {"event": event})


def event_judges(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Herramientas/brief de jueces.
    Solo visible para staff o grupo 'judges'.
    - Si NO autenticado → redirige a login con ?next= la página.
    - Si autenticado sin permisos → 403.
    """
    if not request.user.is_authenticated:
        # Redirección a login preservando el destino
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    if not _user_is_judge(request):
        return HttpResponseForbidden("Solo jueces.")
    event = get_object_or_404(Event, slug=slug)
    return render(request, "events/judges.html", {"event": event})


# -------- Healthcheck simple --------
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True})