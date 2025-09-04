from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from compcore.apps.events.models import Event, Workout, WorkoutHeat


class Command(BaseCommand):
    help = "Smoke test de rutas principales (home, events, detail, heats, leaderboard, judging)."

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, required=True, help="Slug del evento")
        parser.add_argument("--login", action="store_true", help="Probar rutas de jueces (requiere login)")
        parser.add_argument("--username", type=str, default="judge_v3", help="Usuario staff para login")
        parser.add_argument("--password", type=str, default="Pass1234!", help="Contraseña del usuario")

    def handle(self, *args, **opts):
        slug = opts["slug"]
        use_login = opts["login"]
        username = opts["username"]
        password = opts["password"]

        try:
            event = Event.objects.get(slug=slug)
        except Event.DoesNotExist:
            raise CommandError(f"No existe Event con slug={slug}")

        c = Client()

        if use_login:
            ok = c.login(username=username, password=password)
            if not ok:
                raise Comman