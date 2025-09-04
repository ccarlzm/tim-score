from django.shortcuts import render
from django.db.models import QuerySet
from compcore.apps.events.models import Event

def has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False

def index(request):
    """Lista de eventos para navegar a sus leaderboards."""
    qs: QuerySet[Event] = Event.objects.all().order_by("-id")
    if has_field(Event, "is_public"):
        qs = qs.filter(is_public=True)
    events = list(qs[:200])
    return render(request, "leaderboard/index.html", {"events": events, "title": "Leaderboards"})