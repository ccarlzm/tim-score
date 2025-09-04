from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone

from compcore.apps.events.models import Event


class Command(BaseCommand):
    help = "Crea/actualiza un evento demo con inscripción abierta y deadline futuro."

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="Slug del evento a crear/actualizar.")
        parser.add_argument("--name", default="Open Event Demo", help="Nombre del evento (si se crea).")
        parser.add_argument("--workouts", type=int, default=2, help="Cantidad de workouts.")
        parser.add_argument("--heats-per-division", dest="heats_per_division", type=int, default=2)
        parser.add_argument("--lanes", type=int, default=6)
        parser.add_argument("--teams-per-division", dest="teams_per_division", type=int, default=4)
        parser.add_argument("--seed-scores", dest="seed_scores", action="store_true")

    def handle(self, *args, **opts):
        slug = opts["slug"]
        name = opts["name"]

        # 1) Intentar sembrar datos base con seed_demo_event usando kwargs de Python
        try:
            seed_kwargs = dict(
                event=name,
                slug=slug,
                heats_per_division=opts["heats_per_division"],
                lanes=opts["lanes"],
                teams_per_division=opts["teams_per_division"],
                workouts=opts["workouts"],
            )
            if opts.get("seed_scores"):
                seed_kwargs["seed_scores"] = True

            # Llamada segura vía kwargs (no flags de texto)
            call_command("seed_demo_event", **seed_kwargs)
            self.stdout.write(self.style.SUCCESS("✓ seed_demo_event ejecutado correctamente"))
        except Exception as e:
            # No bloqueamos el flujo si no existe o falla; continuamos para abrir inscripción
            self.stdout.write(self.style.WARNING(f"seed_demo_event falló o no existe: {e} (continuo)"))

        # 2) Asegurar flags de inscripción abiertos y fechas coherentes
        event, _ = Event.objects.get_or_create(slug=slug, defaults={"name": name, "status": "open"})
        event.name = event.name or name
        event.status = event.status or "open"
        event.registration_open = True

        today = timezone.localdate()
        event.registration_deadline = today + timedelta(days=30)

        if not event.start_date:
            event.start_date = today
        if not event.end_date or event.end_date < event.start_date:
            event.end_date = event.start_date + timedelta(days=1)

        event.save()

        self.stdout.write(self.style.SUCCESS(
            f"✓ Evento '{event.slug}' con inscripción abierta hasta {event.registration_deadline}"
        ))